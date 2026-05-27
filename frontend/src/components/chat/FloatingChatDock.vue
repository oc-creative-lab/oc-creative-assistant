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
  type ChatMessageDto,
} from '../../api/chatApi'
import { useDraggableDock } from '../../composables/useDraggableDock'
import StagingPanel from './StagingPanel.vue'

marked.use({ gfm: true, breaks: true })

/**
 * 极简悬浮对话栏。
 *
 * 一根可拖动的圆角长条作为输入门户, 流式回复在条上方淡入展开,
 * staging 用条内小药丸 + 弹层呈现; 折叠后是同样可拖的悬浮球。
 * 流式呈现当前用前端 setInterval 节流的"打字机"实现, 视觉与真 SSE 一致;
 * 拖动 / 视窗约束 / 位置持久化的复杂度都收到 useDraggableDock。
 */
const props = defineProps<{
  projectId: string
  selectedNodeIds: string[]
}>()

const emit = defineEmits<{
  graphRefreshNeeded: []
}>()

const SESSION_KEY = 'oc-creative.chat-session-id'
const OPEN_KEY = 'oc-creative.chat-dock-open'
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

let revealTimer: ReturnType<typeof setInterval> | null = null

function toggleOpen() {
  isOpen.value = !isOpen.value
  localStorage.setItem(OPEN_KEY, String(isOpen.value))
  showStaging.value = false
}

const { barStyle, ballStyle, onBarMouseDown, onBallMouseDown } = useDraggableDock({
  onBallClick: toggleOpen,
})

const pendingCount = computed(() =>
  stagingBatches.value.reduce((sum, batch) => sum + batch.items.length, 0),
)

const canSend = computed(
  () => !!sessionId.value && inputValue.value.trim().length > 0 && !isSending.value,
)

const agentLabel = computed(() => AGENT_LABELS[lastAgent.value] ?? '')

const renderedReply = computed(() => {
  /* marked 同步返回 string, 这里强制类型避免被推断成 string | Promise */
  return marked.parse(streamingReply.value) as string
})

/* ---------- session / 消息 ---------- */

async function ensureSession(projectId: string) {
  const cached = localStorage.getItem(SESSION_KEY)
  if (cached) {
    try {
      const messages = await listSessionMessages(cached)
      sessionId.value = cached
      restoreLastAssistantReply(messages)
      return
    } catch {
      localStorage.removeItem(SESSION_KEY)
    }
  }
  const session = await createChatSession(projectId, '当前会话')
  localStorage.setItem(SESSION_KEY, session.id)
  sessionId.value = session.id
}

function restoreLastAssistantReply(messages: ChatMessageDto[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === 'assistant') {
      streamingReply.value = message.content
      lastAgent.value = message.meta.agent_type ?? ''
      return
    }
  }
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

  if (props.projectId) {
    await ensureSession(props.projectId)
    await reloadStaging()
  }
})

onBeforeUnmount(() => {
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

<style scoped src="./FloatingChatDock.scoped.css"></style>