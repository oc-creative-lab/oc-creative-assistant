<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { usePanelResize } from '../../composables/usePanelResize'
import { marked } from 'marked'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useChatStore } from '../../stores/useChatStore'
import { useNodeNavStore } from '../../stores/useNodeNavStore'
import InlineEntityCard from '../chat/InlineEntityCard.vue'
import WebSourceCard from '../chat/WebSourceCard.vue'
import PanelToggleButton from './PanelToggleButton.vue'

marked.use({ gfm: true, breaks: true })

function renderMarkdown(text: string): string {
  return marked.parse(text) as string
}

defineEmits<{ collapse: [] }>()

const chat = useChatStore()
const {
  messages,
  streamingReply,
  streamingWebSources,
  isStreaming,
  progressLabel,
  lastAgent,
  error,
  sessions,
  sessionId,
} = storeToRefs(chat)

const router = useRouter()
const nodeNav = useNodeNavStore()

function goToNode(node: { id: string; title: string; node_type: string }) {
  const pid = chat.projectId
  if (!pid) return
  if (node.node_type === 'character') {
    router.push(`/workspace/${pid}/characters/${node.id}`)
    return
  }
  // plot / worldbuilding: jump to the board and focus the node on its canvas
  nodeNav.request(node.id)
  router.push(
    node.node_type === 'worldbuilding'
      ? `/workspace/${pid}/world`
      : `/workspace/${pid}/plot`,
  )
}

const AGENT_LABELS: Record<string, string> = {
  inspiration: 'Inspiration',
  research: 'Research',
  structure: 'Structure',
  simulation: 'Simulation',
  small_talk: 'Chat',
}

/* ---- chat auto-scroll ---- */
const streamRef = ref<HTMLElement | null>(null)
async function scrollToBottom() {
  await nextTick()
  if (streamRef.value) streamRef.value.scrollTop = streamRef.value.scrollHeight
}
watch([messages, streamingReply], scrollToBottom, { deep: true })

/* ---- session column resize (same mechanism as the shell panels) ---- */
const SESSION_MIN = 130
const SESSION_MAX = 300
const sessionWidth = ref(Number(localStorage.getItem('oc.sessionWidth')) || 170)
watch(sessionWidth, (v) => localStorage.setItem('oc.sessionWidth', String(v)))
const sessionResize = usePanelResize({
  min: SESSION_MIN,
  max: SESSION_MAX,
  direction: -1, // handle sits on the column's left edge: drag left → wider
  getWidth: () => sessionWidth.value,
  setWidth: (w) => {
    sessionWidth.value = w
  },
})

/* ---- ⋯ menu (fixed-positioned so it escapes the scroll container) ---- */
const menuOpenId = ref<string | null>(null)
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

/* ---- inline rename ---- */
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const editInput = ref<HTMLInputElement | null>(null)
async function startRename(s: { id: string; title: string }) {
  closeMenu()
  editingId.value = s.id
  editingTitle.value = s.title
  await nextTick()
  editInput.value?.focus()
  editInput.value?.select()
}
function commitRename() {
  const id = editingId.value
  if (!id) return
  const title = editingTitle.value.trim()
  editingId.value = null
  const current = sessions.value.find((s) => s.id === id)
  if (title && title !== current?.title) void chat.renameSession(id, title)
}
function cancelRename() {
  editingId.value = null
}
function onTitleClick(s: { id: string; title: string }) {
  if (s.id === sessionId.value) startRename(s)
  else void chat.switchSession(s.id)
}

/* ---- actions ---- */
function onNewChat() {
  void chat.newSession()
}
async function onDeleteSession(id: string) {
  closeMenu()
  if (!window.confirm('Delete this chat and its history?')) return
  await chat.deleteSession(id)
}
</script>

<template>
  <aside class="right-stage">
    <header class="right-stage__head">
      <span class="right-stage__title">Agent</span>
      <PanelToggleButton
        direction="right"
        expanded
        label="Collapse agent panel"
        @click="$emit('collapse')"
      />
    </header>

    <div
      class="right-stage__body"
      :style="{ gridTemplateColumns: `minmax(0, 1fr) ${sessionWidth}px` }"
    >
    <div
        class="resize-handle"
        :class="{ 'is-dragging': sessionResize.isDragging.value }"
        :style="{ right: `${sessionWidth}px` }"
        title="Drag to resize"
        @mousedown="sessionResize.startDrag"
      ></div>

      <!-- chat main -->
      <div ref="streamRef" class="right-stage__chat">
        <p v-if="messages.length === 0 && !streamingReply && !isStreaming" class="right-stage__empty">
          Ask in the composer below — the agent can guide, extract entities, and suggest structure.
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
          <div v-if="message.webSources?.length" class="chat-msg__sources">
            <WebSourceCard
              v-for="(source, index) in message.webSources"
              :key="`${message.id}-src-${index}`"
              :source="source"
            />
          </div>
          <div v-if="message.applied?.length" class="chat-msg__applied">
            <InlineEntityCard
              v-for="item in message.applied"
              :key="item.node_id"
              :item="item"
              @edit="(id, patch) => chat.editAppliedNode(id, patch)"
              @remove="(id) => chat.removeAppliedNode(id)"
            />
          </div>
          <div v-if="message.relatedNodes?.length" class="chat-msg__related">
            <span class="chat-msg__related-label">Related nodes</span>
            <button
              v-for="rn in message.relatedNodes"
              :key="rn.id"
              type="button"
              class="chat-msg__related-chip"
              @click="goToNode(rn)"
            >
              {{ rn.title }}
            </button>
          </div>
        </div>

        <div v-if="streamingReply" class="chat-msg chat-msg--assistant">
          <div class="chat-msg__bubble chat-msg__bubble--md" v-html="renderMarkdown(streamingReply)"></div>
          <div v-if="streamingWebSources.length" class="chat-msg__sources">
            <WebSourceCard
              v-for="(source, index) in streamingWebSources"
              :key="`stream-src-${index}`"
              :source="source"
            />
          </div>
        </div>
        <div v-else-if="isStreaming" class="right-stage__thinking">
          <span v-if="lastAgent" class="right-stage__thinking-agent">
            {{ AGENT_LABELS[lastAgent] ?? lastAgent }}
          </span>
          <span class="right-stage__thinking-label">{{ progressLabel || 'Thinking' }}</span>
          <span class="right-stage__dots" aria-hidden="true"><i></i><i></i><i></i></span>
        </div>
        <p v-if="error" class="right-stage__error">{{ error }}</p>
      </div>

      <!-- session column -->
      <div class="right-stage__sessions">
        <div class="right-stage__sessions-head">
          <span>Chats</span>
          <button type="button" class="right-stage__new" title="New chat" @click="onNewChat">+</button>
        </div>
        <div class="right-stage__sessions-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="right-stage__session"
            :class="{ 'is-active': s.id === sessionId }"
          >
            <input
              v-if="editingId === s.id"
              ref="editInput"
              v-model="editingTitle"
              class="right-stage__session-edit"
              @keyup.enter="commitRename"
              @keyup.esc="cancelRename"
              @blur="commitRename"
            />
            <button
              v-else
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
          </div>
        </div>
      </div>
    </div>

    <!-- ⋯ menu (fixed) -->
    <template v-if="menuOpenId">
      <div class="session-menu__backdrop" @click="closeMenu"></div>
      <div
        class="session-menu"
        :style="{ top: menuPos.top + 'px', left: menuPos.left + 'px' }"
      >
        <button
          type="button"
          class="session-menu__item session-menu__item--danger"
          @click.stop="onDeleteSession(menuOpenId)"
        >
          Delete
        </button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.right-stage {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border, #e5e7eb);
  overflow: hidden;
}

.right-stage__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  font-weight: 600;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.right-stage__title {
  font-size: 14px;
}

/* body = chat | session column, with a draggable handle on the divider */
.right-stage__body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
}
.resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  z-index: 5;
  cursor: col-resize;
  transform: translateX(50%);
  touch-action: none;
}
.resize-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 2px;
  width: 2px;
  height: 32px;
  transform: translateY(-50%);
  border-radius: 2px;
  background: transparent;
  transition: background 0.15s ease;
}
.resize-handle:hover::after,
.resize-handle.is-dragging::after {
  background: var(--accent, #8b5cf6);
}
.resize-handle:hover,
.resize-handle.is-dragging {
  background: linear-gradient(
    to right,
    transparent,
    var(--accent-soft, rgba(139, 92, 246, 0.12)),
    transparent
  );
}

.right-stage__chat {
  min-width: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* session column */
.right-stage__sessions {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border, #e5e7eb);
}
.right-stage__sessions-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted, #888);
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.right-stage__new {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.right-stage__sessions-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.right-stage__session {
  display: flex;
  align-items: center;
  border-radius: 6px;
}
.right-stage__session:hover {
  background: #f3f4f6;
}
.right-stage__session.is-active {
  background: var(--accent);
}
.right-stage__session.is-active .right-stage__session-title {
  color: #fff;
}
.right-stage__session-title {
  flex: 1;
  min-width: 0;
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
.right-stage__session-edit {
  flex: 1;
  min-width: 0;
  margin: 3px 6px;
  padding: 3px 6px;
  border: 1px solid var(--accent);
  border-radius: 5px;
  font-size: 13px;
}
.right-stage__session-more {
  border: none;
  background: transparent;
  color: var(--muted, #999);
  padding: 4px 9px;
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
}
.right-stage__session:hover .right-stage__session-more {
  opacity: 1;
}
.right-stage__session.is-active .right-stage__session-more {
  color: rgba(255, 255, 255, 0.85);
  opacity: 1;
}

/* ⋯ dropdown */
.session-menu__backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
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
  cursor: pointer;
}
.session-menu__item:hover {
  background: #f3f4f6;
}
.session-menu__item--danger {
  color: #dc2626;
}

/* messages */
.right-stage__empty {
  margin: 0;
  color: var(--muted, #888);
  font-size: 13px;
  line-height: 1.6;
}
.right-stage__thinking {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 2px 0;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--accent, #8b5cf6);
  background: var(--accent-soft, rgba(139, 92, 246, 0.1));
  animation: thinking-pulse 1.8s ease-in-out infinite;
}
.right-stage__thinking-agent {
  font-weight: 700;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--accent, #8b5cf6);
  color: #fff;
}
.right-stage__thinking-label {
  font-weight: 500;
}
.right-stage__dots {
  display: inline-flex;
  gap: 3px;
}
.right-stage__dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  animation: thinking-bounce 1.2s ease-in-out infinite;
}
.right-stage__dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.right-stage__dots i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes thinking-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}
@keyframes thinking-pulse {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}
.right-stage__error {
  margin: 0;
  color: #dc2626;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 100%;
}
.chat-msg--user {
  align-items: flex-end;
}
.chat-msg__agent {
  display: inline-flex;
  align-self: flex-start;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--accent, #8b5cf6);
  color: #fff;
}
.chat-msg__bubble {
  padding: 8px 11px;
  border-radius: 10px;
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 13px;
  max-width: 100%;
  word-break: break-word;
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
.chat-msg--assistant .chat-msg__bubble {
  background: var(--accent-soft, rgba(139, 92, 246, 0.08));
  color: var(--text);
}
.chat-msg--user .chat-msg__bubble {
  background: var(--accent);
  color: #fff;
}
.chat-msg__applied,
.chat-msg__sources {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chat-msg__related {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.chat-msg__related-label {
  font-size: 11px;
  color: var(--muted, #888);
}
.chat-msg__related-chip {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid var(--accent-border, rgba(139, 92, 246, 0.3));
  background: var(--accent-soft, rgba(139, 92, 246, 0.1));
  color: var(--accent-deep, #6d28d9);
  cursor: pointer;
}
.chat-msg__related-chip:hover {
  background: var(--accent, #8b5cf6);
  color: #fff;
}
</style>