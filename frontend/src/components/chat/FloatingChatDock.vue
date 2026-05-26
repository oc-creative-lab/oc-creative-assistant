<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import {
  createChatSession,
  listSessionMessages,
  listSessionStaging,
  postChat,
  resolveStagingBatch,
  resolveStagingItem,
  type AgentStagingBatchDto,
} from '../../api/chatApi'
import StagingPanel from './StagingPanel.vue'

marked.use({ gfm: true, breaks: true })

/**
 * 极简悬浮对话栏。
 *
 * 一根可拖动的圆角长条作为输入门户, 流式回复在条上方淡入展开,
 * staging 用条内小药丸 + 弹层呈现; 折叠后是同样可拖的悬浮球。
 * 流式呈现当前用前端 setInterval 节流的"打字机"实现, 视觉与真 SSE 一致;
 * 后续若接入后端流式接口, 把 startReveal 内部替换成 token 推送即可。
 */
const props = defineProps<{
  projectId: string
  selectedNodeIds: string[]
}>()

const emit = defineEmits<{
  graphRefreshNeeded: []
}>()

interface DockPosition {
  x: number
  y: number
}

interface DragState {
  mode: 'bar' | 'ball'
  pointerStartX: number
  pointerStartY: number
  initialX: number
  initialY: number
  moved: boolean
}

const SESSION_KEY = 'oc-creative.chat-session-id'
const OPEN_KEY = 'oc-creative.chat-dock-open'
const BAR_POSITION_KEY = 'oc-creative.chat-dock-bar-position'
const BALL_POSITION_KEY = 'oc-creative.chat-dock-ball-position'

const DRAG_THRESHOLD_PX = 5
const VIEWPORT_MARGIN = 8
const BAR_SIZE = { width: 720, height: 64 }
const BALL_SIZE = { width: 56, height: 56 }
/* 25ms/字符 ≈ 40 字符/秒, 接近自然阅读速度 */
const REVEAL_INTERVAL_MS = 25

const AGENT_LABELS: Record<string, string> = {
  inspiration: '灵感发散',
  research: '资料检索',
  structure: '结构搭建',
  simulation: '推演假设',
  small_talk: '日常对话',
}

const isOpen = ref(true)
const showStaging = ref(false)
const sessionId = ref('')
const inputValue = ref('')
const isSending = ref(false)
const errorText = ref('')
const stagingBatches = ref<AgentStagingBatchDto[]>([])

const streamingReply = ref('')
const isStreaming = ref(false)
const lastAgent = ref('')

const barPosition = ref<DockPosition | null>(null)
const ballPosition = ref<DockPosition | null>(null)

let dragState: DragState | null = null
let revealTimer: ReturnType<typeof setInterval> | null = null

const pendingCount = computed(() =>
  stagingBatches.value.reduce(
    (sum, batch) => sum + batch.items.filter((item) => item.status === 'pending').length,
    0,
  ),
)

const canSend = computed(
  () => Boolean(sessionId.value) && !isSending.value && inputValue.value.trim().length > 0,
)

const agentLabel = computed(() => AGENT_LABELS[lastAgent.value] ?? '')

const CURSOR_PLACEHOLDER = '\uE000'

const renderedReply = computed(() => {
  const source = isStreaming.value
    ? `${streamingReply.value}${CURSOR_PLACEHOLDER}`
    : streamingReply.value
  const html = marked.parse(source) as string
  return html.replace(
    CURSOR_PLACEHOLDER,
    '<span class="bar-dock__cursor">▌</span>',
  )
})

const barStyle = computed(() => {
  if (barPosition.value) {
    return {
      left: `${barPosition.value.x}px`,
      top: `${barPosition.value.y}px`,
      transform: 'none',
    }
  }
  return {
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)',
  }
})

const ballStyle = computed(() => {
  if (ballPosition.value) {
    return {
      left: `${ballPosition.value.x}px`,
      top: `${ballPosition.value.y}px`,
      right: 'auto',
      bottom: 'auto',
    }
  }
  return {}
})

/* ---------- session / 消息 ---------- */

async function ensureSession(projectId: string) {
  const cached = localStorage.getItem(SESSION_KEY)
  if (cached) {
    try {
      await listSessionMessages(cached)
      sessionId.value = cached
      return
    } catch {
      localStorage.removeItem(SESSION_KEY)
    }
  }
  const session = await createChatSession(projectId, '当前会话')
  localStorage.setItem(SESSION_KEY, session.id)
  sessionId.value = session.id
}

async function reloadStaging() {
  if (!sessionId.value) return
  stagingBatches.value = await listSessionStaging(sessionId.value, 'pending')
}

/* ---------- 流式打字机 ---------- */

function clearReveal() {
  if (revealTimer) {
    clearInterval(revealTimer)
    revealTimer = null
  }
  isStreaming.value = false
}

function startReveal(fullText: string) {
  clearReveal()
  let index = 0
  streamingReply.value = ''
  isStreaming.value = true
  revealTimer = setInterval(() => {
    if (index >= fullText.length) {
      clearReveal()
      return
    }
    streamingReply.value += fullText[index]
    index += 1
  }, REVEAL_INTERVAL_MS)
}

/* ---------- 发送 ---------- */

async function handleSend() {
  if (!canSend.value) return

  const text = inputValue.value.trim()
  inputValue.value = ''
  errorText.value = ''
  isSending.value = true
  streamingReply.value = ''
  clearReveal()

  try {
    const response = await postChat(sessionId.value, text, props.selectedNodeIds)
    lastAgent.value = response.intent
    startReveal(response.reply_text)
    await reloadStaging()
    /* 有新建议自动展开 staging 弹层, 让 HITL 入口对用户显式可见 */
    if (response.staging_count > 0) {
      showStaging.value = true
    }
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '发送失败'
  } finally {
    isSending.value = false
  }
}

/* ---------- staging ---------- */

async function handleResolveItem(stagingId: string, action: 'accept' | 'reject') {
  try {
    await resolveStagingItem(stagingId, action)
    await reloadStaging()
    if (action === 'accept') emit('graphRefreshNeeded')
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : 'staging 操作失败'
  }
}

async function handleResolveBatch(batchId: string, action: 'accept_all' | 'reject_all') {
  try {
    await resolveStagingBatch(batchId, action)
    await reloadStaging()
    if (action === 'accept_all') emit('graphRefreshNeeded')
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : 'staging 操作失败'
  }
}

function toggleStaging() {
  showStaging.value = !showStaging.value
}

/* ---------- 开合 ---------- */

function toggleOpen() {
  isOpen.value = !isOpen.value
  localStorage.setItem(OPEN_KEY, String(isOpen.value))
  showStaging.value = false
}

/* ---------- 拖动 ---------- */

function clampToViewport(x: number, y: number, width: number, height: number): DockPosition {
  return {
    x: Math.max(VIEWPORT_MARGIN, Math.min(x, window.innerWidth - width - VIEWPORT_MARGIN)),
    y: Math.max(VIEWPORT_MARGIN, Math.min(y, window.innerHeight - height - VIEWPORT_MARGIN)),
  }
}

function readInitialPosition(mode: 'bar' | 'ball', el: HTMLElement): DockPosition {
  const stored = mode === 'bar' ? barPosition.value : ballPosition.value
  if (stored) return stored
  const rect = el.getBoundingClientRect()
  return { x: rect.left, y: rect.top }
}

function onBarMouseDown(event: MouseEvent) {
  const target = event.target as HTMLElement
  /* 输入框 / 按钮 / 上下浮层都不应该触发拖动, 让交互归交互 */
  if (target.closest('input, textarea, button, .bar-dock__reply, .bar-dock__staging-pop')) {
    return
  }
  const dockEl = event.currentTarget as HTMLElement
  const initial = readInitialPosition('bar', dockEl)
  dragState = {
    mode: 'bar',
    pointerStartX: event.clientX,
    pointerStartY: event.clientY,
    initialX: initial.x,
    initialY: initial.y,
    moved: false,
  }
  event.preventDefault()
}

function onBallMouseDown(event: MouseEvent) {
  const ballEl = event.currentTarget as HTMLElement
  const initial = readInitialPosition('ball', ballEl)
  dragState = {
    mode: 'ball',
    pointerStartX: event.clientX,
    pointerStartY: event.clientY,
    initialX: initial.x,
    initialY: initial.y,
    moved: false,
  }
  event.preventDefault()
}

function onMouseMove(event: MouseEvent) {
  if (!dragState) return
  const dx = event.clientX - dragState.pointerStartX
  const dy = event.clientY - dragState.pointerStartY
  if (!dragState.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
    dragState.moved = true
  }
  if (dragState.mode === 'ball' && !dragState.moved) return

  const size = dragState.mode === 'bar' ? BAR_SIZE : BALL_SIZE
  const next = clampToViewport(
    dragState.initialX + dx,
    dragState.initialY + dy,
    size.width,
    size.height,
  )
  if (dragState.mode === 'bar') {
    barPosition.value = next
  } else {
    ballPosition.value = next
  }
}

function onMouseUp() {
  if (!dragState) return
  const { mode, moved } = dragState
  dragState = null

  if (mode === 'bar' && barPosition.value) {
    localStorage.setItem(BAR_POSITION_KEY, JSON.stringify(barPosition.value))
    return
  }
  if (mode === 'ball') {
    if (ballPosition.value) {
      localStorage.setItem(BALL_POSITION_KEY, JSON.stringify(ballPosition.value))
    }
    if (!moved) toggleOpen()
  }
}

function readStored<T>(key: string): T | null {
  const raw = localStorage.getItem(key)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

watch(
  () => props.projectId,
  async (next) => {
    if (!next) return
    await ensureSession(next)
    await reloadStaging()
  },
)

onMounted(async () => {
  const cachedOpen = localStorage.getItem(OPEN_KEY)
  if (cachedOpen !== null) isOpen.value = cachedOpen === 'true'
  barPosition.value = readStored<DockPosition>(BAR_POSITION_KEY)
  ballPosition.value = readStored<DockPosition>(BALL_POSITION_KEY)

  /* 监听挂在 window 上, 拖动过程鼠标离开 dock 也仍能跟手 */
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)

  if (props.projectId) {
    await ensureSession(props.projectId)
    await reloadStaging()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  clearReveal()
})
</script>

<template>
  <button
    v-if="!isOpen"
    type="button"
    class="dock-fab"
    :style="ballStyle"
    aria-label="打开创作助手"
    @mousedown="onBallMouseDown"
  >
  <svg
      class="dock-fab__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
    <span v-if="pendingCount > 0" class="dock-fab__badge">{{ pendingCount }}</span>
  </button>

  <section
    v-else
    class="bar-dock"
    :style="barStyle"
    role="dialog"
    aria-label="创作助手"
    @mousedown="onBarMouseDown"
  >
  <transition name="reply">
      <div v-if="streamingReply" class="bar-dock__reply">
        <span
          v-if="agentLabel"
          class="bar-dock__agent-chip"
          :class="`bar-dock__agent-chip--${lastAgent}`"
        >
        {{ agentLabel }}
        </span>
        <div class="bar-dock__reply-body" v-html="renderedReply"></div>
      </div>
    </transition>

    <div class="bar-dock__bar">
      <input
        v-model="inputValue"
        type="text"
        class="bar-dock__input"
        :placeholder="isSending ? '思考中...' : '问问创作助手'"
        :disabled="isSending"
        @keydown.enter.prevent="handleSend"
      />

      <button
        v-if="pendingCount > 0"
        type="button"
        class="bar-dock__pill"
        :class="{ 'is-active': showStaging }"
        @click="toggleStaging"
      >
        ✨ {{ pendingCount }} 待确认
      </button>

      <button
        type="button"
        class="bar-dock__send"
        :disabled="!canSend"
        aria-label="发送"
        @click="handleSend"
      >
        ➤
      </button>

      <button
        type="button"
        class="bar-dock__close"
        aria-label="收起"
        @click="toggleOpen"
      >
        ─
      </button>
    </div>

    <transition name="staging">
      <div
        v-if="showStaging && stagingBatches.length > 0"
        class="bar-dock__staging-pop"
      >
        <StagingPanel
          :batches="stagingBatches"
          @resolve-item="handleResolveItem"
          @resolve-batch="handleResolveBatch"
        />
      </div>
    </transition>

    <transition name="reply">
      <p v-if="errorText" class="bar-dock__error">{{ errorText }}</p>
    </transition>
  </section>
</template>

<style scoped>
.dock-fab {
  position: fixed;
  right: 24px;
  bottom: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  /* 磨砂玻璃: 半透明白底 + 背后高斯模糊, 让画布颜色透出来又不抢戏 */
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  color: var(--accent);
  cursor: grab;
  user-select: none;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.10);
  transition: background 0.18s ease, box-shadow 0.18s ease;
  z-index: 1000;
}

.dock-fab:hover {
  background: rgba(255, 255, 255, 0.62);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
}

.dock-fab:active {
  cursor: grabbing;
}

.dock-fab__icon {
  width: 22px;
  height: 22px;
  display: block;
}

.dock-fab__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #ef4444;
  color: #ffffff;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
  box-shadow: 0 0 0 2px var(--app-bg);
}

.bar-dock {
  position: fixed;
  width: min(720px, calc(100vw - 32px));
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 1000;
  cursor: grab;
  user-select: none;
}

.bar-dock:active {
  cursor: grabbing;
}

.bar-dock__reply {
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  max-height: 240px;
  overflow-y: auto;
  cursor: default;
  user-select: text;
}

   .bar-dock__reply-body {
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--text);
  word-break: break-word;
}

.bar-dock__reply-body :deep(p) {
  margin: 0;
}

.bar-dock__reply-body :deep(p + p),
.bar-dock__reply-body :deep(ul),
.bar-dock__reply-body :deep(ol),
.bar-dock__reply-body :deep(blockquote),
.bar-dock__reply-body :deep(pre) {
  margin-top: 8px;
}

.bar-dock__reply-body :deep(ul),
.bar-dock__reply-body :deep(ol) {
  margin-bottom: 0;
  padding-left: 1.4em;
}

.bar-dock__reply-body :deep(li + li) {
  margin-top: 4px;
}

.bar-dock__reply-body :deep(strong) {
  font-weight: 700;
  color: var(--text);
}

.bar-dock__reply-body :deep(em) {
  font-style: italic;
}

.bar-dock__reply-body :deep(code) {
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.08);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.86em;
}

.bar-dock__reply-body :deep(pre) {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.06);
  overflow-x: auto;
}

.bar-dock__reply-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.bar-dock__reply-body :deep(blockquote) {
  margin-left: 0;
  padding-left: 12px;
  border-left: 3px solid var(--accent-border);
  color: var(--muted);
}

.bar-dock__reply-body :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}

.bar-dock__reply-body :deep(.bar-dock__cursor) {
  display: inline-block;
  margin-left: 2px;
  color: var(--accent);
  animation: cursorBlink 0.9s steps(1) infinite;
}

@keyframes cursorBlink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.bar-dock__bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px 8px 24px;
  height: 64px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.10);
}

.bar-dock__input {
  flex: 1;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 1rem;
  cursor: text;
  user-select: text;
}

.bar-dock__input::placeholder {
  color: var(--muted);
}

.bar-dock__input:disabled {
  cursor: not-allowed;
  color: var(--muted);
}

.bar-dock__pill {
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--accent-border);
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.bar-dock__pill:hover {
  filter: brightness(0.97);
}

.bar-dock__pill.is-active {
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}

.bar-dock__send {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: var(--accent);
  color: #ffffff;
  font-size: 1.05rem;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.bar-dock__send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bar-dock__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  color: var(--muted);
  font-size: 0.9rem;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.bar-dock__close:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.65);
}

.bar-dock__staging-pop {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  max-height: 360px;
  overflow-y: auto;
  cursor: default;
  user-select: text;
}

.bar-dock__error {
  margin: 0;
  padding: 8px 16px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.82rem;
  border-radius: 10px;
  cursor: default;
}

.reply-enter-active,
.reply-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.reply-enter-from,
.reply-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.staging-enter-active,
.staging-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.staging-enter-from,
.staging-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.bar-dock__agent-chip {
  display: inline-flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 2px 10px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.4px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid var(--accent-border);
}

.bar-dock__agent-chip--inspiration {
  background: #fef3c7;
  color: #92400e;
  border-color: #fcd34d;
}

.bar-dock__agent-chip--research {
  background: #dbeafe;
  color: #1e40af;
  border-color: #93c5fd;
}

.bar-dock__agent-chip--structure {
  background: #d1fae5;
  color: #065f46;
  border-color: #6ee7b7;
}

.bar-dock__agent-chip--simulation {
  background: #ede9fe;
  color: #5b21b6;
  border-color: #c4b5fd;
}

.bar-dock__agent-chip--small_talk {
  background: #f1f5f9;
  color: #475569;
  border-color: #cbd5e1;
}

@media (max-width: 640px) {
  .bar-dock {
    width: calc(100vw - 24px);
  }
}
</style>