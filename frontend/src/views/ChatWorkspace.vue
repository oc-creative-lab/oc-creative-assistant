<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../stores/useChatStore'
import { rebuildProjectSeed } from '../api/projectApi'
import InlineEntityCard from '../components/chat/InlineEntityCard.vue'
import StagingPanel from '../components/chat/StagingPanel.vue'

marked.use({ gfm: true, breaks: true })

function renderMarkdown(text: string): string {
  return marked.parse(text) as string
}

/**
 * Full-screen chat workspace (first_revision stage 4, the core innovation).
 *
 * Left: the conversation stream (the user freely shares ideas, Chat Agent A
 * streams replies and naturally raises questions).
 * Right: StagingPanel (reused), showing in real time the pending entities that
 * the background structured_extractor pulls out.
 * Top: Exit back to home; bottom: the input box. Turning on extraction_enabled
 * lets the B-agent step in.
 */
const props = defineProps<{ projectId: string }>()
const router = useRouter()

const chat = useChatStore()
const { messages, streamingReply, isStreaming, progressLabel, stagingBatches, error } =
  storeToRefs(chat)

const draft = ref('')
const streamRef = ref<HTMLElement | null>(null)

const AGENT_LABELS: Record<string, string> = {
  inspiration: 'Inspiration',
  research: 'Research',
  structure: 'Structure',
  simulation: 'Simulation',
  small_talk: 'Chat',
}

onMounted(() => {
  void chat.init(props.projectId)
})

async function scrollToBottom() {
  await nextTick()
  if (streamRef.value) streamRef.value.scrollTop = streamRef.value.scrollHeight
}

watch([messages, streamingReply], scrollToBottom, { deep: true })

async function handleSend() {
  const text = draft.value
  draft.value = ''
  await chat.send(text)
}

/** Exiting chat = the session ends, triggering one seed rebuild (one of the first_revision stage 5 triggers). */
async function handleExit() {
  try {
    await rebuildProjectSeed(props.projectId)
  } catch {
    /* A failed seed rebuild should not block exiting */
  }
  router.push('/')
}
</script>

<template>
  <div class="chat-workspace">
    <header class="chat-workspace__top">
      <button type="button" class="chat-workspace__exit" @click="handleExit">← Exit</button>
      <span class="chat-workspace__title">Chat</span>
      <button
        type="button"
        class="chat-workspace__go-workspace"
        @click="router.push(`/workspace/${projectId}`)"
      >
        Open workspace
      </button>
    </header>

    <main class="chat-workspace__body">
      <section class="chat-workspace__chat">
        <div ref="streamRef" class="chat-workspace__stream">
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
            <div v-if="message.applied?.length" class="chat-msg__applied">
              <InlineEntityCard
                v-for="item in message.applied"
                :key="item.node_id"
                :item="item"
                @edit="(id, patch) => chat.editAppliedNode(id, patch)"
                @remove="(id) => chat.removeAppliedNode(id)"
              />
            </div>
          </div>

          <div v-if="streamingReply" class="chat-msg chat-msg--assistant">
            <div class="chat-msg__bubble chat-msg__bubble--md" v-html="renderMarkdown(streamingReply)"></div>
          </div>
          <p v-else-if="isStreaming" class="chat-workspace__progress">{{ progressLabel }}</p>
          <p v-if="error" class="chat-workspace__error">{{ error }}</p>
        </div>

        <form class="chat-workspace__input" @submit.prevent="handleSend">
          <textarea
            v-model="draft"
            rows="2"
            placeholder="Say what you're thinking — ideas get organised in the background…"
            @keydown.enter.exact.prevent="handleSend"
          ></textarea>
          <button type="submit" :disabled="isStreaming || !draft.trim()">Send</button>
        </form>
      </section>

      <aside class="chat-workspace__staging">
        <h3 class="chat-workspace__staging-title">Pending entities</h3>
        <p v-if="stagingBatches.length === 0" class="chat-workspace__staging-hint">
          Mention a character, place or beat and pending cards appear here.
        </p>
        <StagingPanel
          :batches="stagingBatches"
          @resolve-batch="(id, action) => chat.resolveBatch(id, action)"
          @resolve-item="(id, action) => chat.resolveItem(id, action)"
        />
      </aside>
    </main>
  </div>
</template>

<style scoped>
.chat-workspace {
  height: 100vh;
  display: grid;
  grid-template-rows: 52px minmax(0, 1fr);
  background: var(--app-bg, #fff);
}
.chat-workspace__top {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.chat-workspace__title {
  flex: 1;
  font-weight: 600;
}
.chat-workspace__exit,
.chat-workspace__go-workspace {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border, #ddd);
  background: var(--app-bg, #fff);
  cursor: pointer;
}
.chat-workspace__body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
}
.chat-workspace__chat {
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  border-right: 1px solid var(--border, #e5e7eb);
}
.chat-workspace__stream {
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 80%;
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
  padding: 10px 14px;
  border-radius: 12px;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 14px;
}
.chat-msg--assistant .chat-msg__bubble {
  background: #f3f4f6;
}
.chat-msg--user .chat-msg__bubble {
  background: var(--accent);
  color: #fff;
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
.chat-msg__applied {
  width: 100%;
}
.chat-workspace__progress {
  color: var(--muted, #888);
  font-size: 13px;
}
.chat-workspace__error {
  color: #dc2626;
  font-size: 13px;
}
.chat-workspace__input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border, #e5e7eb);
}
.chat-workspace__input textarea {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
  resize: none;
}
.chat-workspace__input button {
  padding: 0 20px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}
.chat-workspace__input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.chat-workspace__staging {
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}
.chat-workspace__staging-title {
  font-size: 14px;
  margin-bottom: 10px;
}
.chat-workspace__staging-hint {
  color: var(--muted, #888);
  font-size: 13px;
}
</style>
