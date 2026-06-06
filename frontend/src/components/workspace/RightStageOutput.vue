<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { marked } from 'marked'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import { injectWorkspaceGraphRefresh } from '../../composables/useWorkspaceChatContext'
import StagingPanel from '../chat/StagingPanel.vue'

marked.use({ gfm: true, breaks: true })

/** marked 同步返回 string, 强转避免被推断成 string | Promise。 */
function renderMarkdown(text: string): string {
  return marked.parse(text) as string
}

/**
 * 右栏对话流：复用 useChatStore，展示历史消息 + 流式回复 +
 * 待确认 staging。接受变更后通过注入的刷新器重载当前画布。
 */
const chat = useChatStore()
const graphRefresh = injectWorkspaceGraphRefresh()
const { messages, streamingReply, isStreaming, progressLabel, lastAgent, stagingBatches, error, sessions, sessionId } =
  storeToRefs(chat)

defineProps<{ collapsed?: boolean }>()
const emit = defineEmits<{ toggle: [] }>()

const AGENT_LABELS: Record<string, string> = {
  inspiration: 'Inspiration',
  research: 'Research',
  structure: 'Structure',
  simulation: 'Simulation',
  small_talk: 'Chat',
}

const streamRef = ref<HTMLElement | null>(null)
watch([messages, streamingReply], async () => {
  await nextTick()
  if (streamRef.value) streamRef.value.scrollTop = streamRef.value.scrollHeight
}, { deep: true })

const sessionWidth = ref(160)
let sessionDragging = false
let sessionStartX = 0
let sessionStartWidth = 0

function startSessionResize(event: MouseEvent) {
  event.preventDefault()
  sessionDragging = true
  sessionStartX = event.clientX
  sessionStartWidth = sessionWidth.value
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onSessionResize)
  window.addEventListener('mouseup', stopSessionResize)
}
function onSessionResize(event: MouseEvent) {
  if (!sessionDragging) return
  sessionWidth.value = Math.min(320, Math.max(100, sessionStartWidth - (event.clientX - sessionStartX)))
}
function stopSessionResize() {
  sessionDragging = false
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onSessionResize)
  window.removeEventListener('mouseup', stopSessionResize)
}
onBeforeUnmount(stopSessionResize)

const menuOpenId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const editingTitle = ref('')

async function resolveItem(stagingId: string, action: 'accept' | 'reject') {
  await chat.resolveItem(stagingId, action)
  if (action === 'accept') await graphRefresh?.trigger()
}

async function resolveBatch(batchId: string, action: 'accept_all' | 'reject_all') {
  await chat.resolveBatch(batchId, action)
  if (action === 'accept_all') await graphRefresh?.trigger()
}
const menuPos = ref({ top: 0, left: 0 })

function toggleMenu(id: string, event: MouseEvent) {
  if (menuOpenId.value === id) {
    menuOpenId.value = null
    return
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menuPos.value = { top: rect.bottom + 4, left: rect.right - 120 }
  menuOpenId.value = id
}
function closeMenu() {
  menuOpenId.value = null
}
function startRename(s: { id: string; title: string }) {
  editingId.value = s.id
  editingTitle.value = s.title || ''
  menuOpenId.value = null
  void nextTick(() => {
    const el = document.querySelector<HTMLInputElement>('.right-stage__session-input')
    el?.focus()
    el?.select()
  })
}
function onTitleClick(s: { id: string; title: string }) {
  if (s.id === sessionId.value) {
    startRename(s)
  } else {
    void chat.selectSession(s.id)
  }
}
async function commitRename() {
  const id = editingId.value
  if (!id) return
  editingId.value = null
  await chat.renameSession(id, editingTitle.value)
}
function cancelRename() {
  editingId.value = null
}
async function onDeleteSession(id: string) {
  menuOpenId.value = null
  if (!window.confirm('Delete this chat and its history?')) return
  await chat.deleteSession(id)
}

</script>

<template>
  <aside class="right-stage" :class="{ 'is-collapsed': collapsed }">
    <header class="right-stage__head">
      <button
        type="button"
        class="right-stage__toggle"
        :title="collapsed ? 'Expand' : 'Collapse'"
        @click="emit('toggle')"
      >{{ collapsed ? '‹' : '›' }}</button>
      <template v-if="!collapsed">
        <span>OC Assistant Output</span>
        <button type="button" class="right-stage__new" @click="chat.startNewSession()">+ New</button>
      </template>
    </header>

    <div
      v-if="!collapsed"
      class="right-stage__body"
      :style="{ gridTemplateColumns: sessions.length ? `minmax(0, 1fr) ${sessionWidth}px` : 'minmax(0, 1fr)' }"
    >
      <div
        v-if="sessions.length"
        class="right-stage__sessions-resizer"
        :style="{ right: `${sessionWidth}px` }"
        @mousedown="startSessionResize"
      ></div>
      <div class="right-stage__main">
        <div ref="streamRef" class="right-stage__stream">
          <p v-if="messages.length === 0 && !isStreaming" class="right-stage__empty">
            Ask in the composer below — the assistant can also add or remove nodes on the canvas after you accept.
          </p>

          <div
            v-for="message in messages"
            :key="message.id"
            class="chat-msg"
            :class="`chat-msg--${message.role}`"
          >
            <span v-if="message.role === 'assistant' && message.agentType" class="chat-msg__agent">
              {{ AGENT_LABELS[message.agentType] ?? message.agentType }}
            </span>
            <div
              v-if="message.role === 'assistant'"
              class="chat-msg__bubble chat-msg__bubble--md"
              v-html="renderMarkdown(message.content)"
            ></div>
            <div v-else class="chat-msg__bubble">{{ message.content }}</div>
          </div>

          <div v-if="streamingReply" class="chat-msg chat-msg--assistant">
            <span v-if="lastAgent" class="chat-msg__agent">{{ AGENT_LABELS[lastAgent] ?? lastAgent }}</span>
            <div class="chat-msg__bubble chat-msg__bubble--md" v-html="renderMarkdown(streamingReply)"></div>
          </div>
          <div v-else-if="isStreaming" class="thinking">
            <span class="thinking__pulse"></span>
            <span v-if="lastAgent" class="thinking__agent">{{ AGENT_LABELS[lastAgent] ?? lastAgent }}</span>
            <span class="thinking__label">{{ progressLabel || 'Thinking' }}</span>
            <span class="thinking__dots"><i></i><i></i><i></i></span>
          </div>
          <p v-if="error" class="right-stage__error">{{ error }}</p>
        </div>

        <div v-if="stagingBatches.length" class="right-stage__staging">
          <StagingPanel
            :batches="stagingBatches"
            @resolve-item="resolveItem"
            @resolve-batch="resolveBatch"
          />
        </div>
      </div>

      <div v-if="sessions.length" class="right-stage__sessions">
        <div v-if="menuOpenId" class="session-menu__backdrop" @click="closeMenu"></div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="right-stage__session"
          :class="{ 'is-active': s.id === sessionId }"
        >
          <input
            v-if="editingId === s.id"
            v-model="editingTitle"
            class="right-stage__session-input"
            @keyup.enter="commitRename"
            @keyup.esc="cancelRename"
            @blur="commitRename"
          />
          <template v-else>
            <button
              type="button"
              class="right-stage__session-title"
              :title="s.id === sessionId ? 'Click to rename' : 'Open chat'"
              @click="onTitleClick(s)"
            >
              {{ s.title || 'Untitled chat' }}
            </button>
            <button
              type="button"
              class="right-stage__session-more"
              title="More"
              @click.stop="toggleMenu(s.id, $event)"
            >
              ⋯
            </button>
          </template>

          <div
            v-if="menuOpenId === s.id"
            class="session-menu"
            :style="{ top: menuPos.top + 'px', left: menuPos.left + 'px' }"
          >
            <button
              type="button"
              class="session-menu__item session-menu__item--danger"
              @click.stop="onDeleteSession(s.id)"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.right-stage__toggle {
  width: 24px;
  height: 26px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--muted);
  cursor: pointer;
  line-height: 1;
}
.right-stage__toggle:hover {
  color: var(--accent);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.right-stage.is-collapsed .right-stage__head {
  justify-content: center;
  padding: 12px 6px;
}
.chat-msg__bubble--md {
  white-space: normal;
}
.chat-msg__bubble--md :deep(p) {
  margin: 0 0 8px;
}
.chat-msg__bubble--md :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-msg__bubble--md :deep(ul),
.chat-msg__bubble--md :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 18px;
}
.chat-msg__bubble--md :deep(strong) {
  font-weight: 600;
}
.chat-msg__bubble--md :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.chat-msg__bubble--md :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: 8px 10px;
  border-radius: 8px;
  overflow-x: auto;
}
.chat-msg__bubble--md :deep(h1),
.chat-msg__bubble--md :deep(h2),
.chat-msg__bubble--md :deep(h3) {
  font-size: 14px;
  margin: 8px 0 4px;
}

.right-stage {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border, #e5e7eb);
  background:
    radial-gradient(circle at 80% 0%, rgba(167, 139, 250, 0.1), transparent 60%),
    var(--panel);
  overflow: hidden;
}
.right-stage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-weight: 600;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.right-stage__body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
}
.right-stage__sessions-resizer {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 7px;
  transform: translateX(50%);
  cursor: col-resize;
  z-index: 4;
}
.right-stage__sessions-resizer:hover {
  background: var(--accent-soft);
}
.right-stage__main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.right-stage__new {
  font-size: 12px;
  padding: 3px 10px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
}
.right-stage__sessions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  padding: 6px;
  border-left: 1px solid var(--border, #e5e7eb);
}
.right-stage__session {
  display: flex;
  align-items: center;
  border-radius: 11px;
}
.right-stage__session:hover {
  background: var(--accent-soft);
}
.right-stage__session:hover .right-stage__session-title {
  color: var(--accent-deep);
}
.right-stage__session.is-active {
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  box-shadow: 0 6px 16px rgba(124, 92, 255, 0.32);
}
.right-stage__session.is-active .right-stage__session-title {
  color: #fff;
}
.right-stage__session-title {
  flex: 1;
  text-align: left;
  padding: 6px 10px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text, #111);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.right-stage__session {
  position: relative;
}
.right-stage__session-more {
  border: none;
  background: transparent;
  color: var(--muted, #999);
  padding: 4px 9px;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  border-radius: 6px;
  opacity: 0;
}
.right-stage__session:hover .right-stage__session-more {
  opacity: 1;
}
.right-stage__session.is-active .right-stage__session-more {
  color: rgba(255, 255, 255, 0.85);
  opacity: 1;
}
.right-stage__session-input {
  flex: 1;
  margin: 2px 6px;
  padding: 5px 8px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  font: inherit;
  font-size: 13px;
}
.session-menu {
  position: fixed;
  z-index: 1001;
  min-width: 120px;
  background: #fff;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
  padding: 4px;
  display: flex;
  flex-direction: column;
}
.session-menu__item {
  text-align: left;
  padding: 7px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text, #111);
  cursor: pointer;
}
.session-menu__item:hover {
  background: #f3f4f6;
}
.session-menu__item--danger {
  color: #dc2626;
}
.session-menu__backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
}
.right-stage__stream {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.right-stage__empty {
  color: var(--muted, #888);
  font-size: 13px;
  line-height: 1.6;
}
.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 92%;
}
.chat-msg--user {
  align-self: flex-end;
  align-items: flex-end;
}
.chat-msg__agent {
  font-size: 11px;
  color: var(--accent);
}
.chat-msg__bubble {
  padding: 8px 12px;
  border-radius: 12px;
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 13px;
}
.chat-msg--assistant .chat-msg__bubble {
  background: #f3f4f6;
}
.chat-msg--user .chat-msg__bubble {
  background: var(--accent);
  color: #fff;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted, #888);
}
.thinking__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: thinking-pulse 1s ease-in-out infinite;
}
.thinking__label {
  background: linear-gradient(90deg, var(--muted, #999) 25%, #111 50%, var(--muted, #999) 75%);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: thinking-shimmer 1.6s linear infinite;
}
.thinking__agent {
  padding: 1px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}
.thinking__dots {
  display: inline-flex;
  gap: 3px;
}
.thinking__dots i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--muted, #999);
  animation: thinking-bounce 1.2s ease-in-out infinite;
}
.thinking__dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.thinking__dots i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes thinking-pulse {
  0%, 100% { transform: scale(0.7); opacity: 0.5; }
  50% { transform: scale(1.1); opacity: 1; }
}
@keyframes thinking-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@keyframes thinking-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-3px); opacity: 1; }
}
.right-stage__error {
  color: #dc2626;
  font-size: 13px;
}
.right-stage__staging {
  border-top: 1px solid var(--border, #e5e7eb);
  max-height: 45%;
  overflow-y: auto;
  padding: 10px;
}
</style>