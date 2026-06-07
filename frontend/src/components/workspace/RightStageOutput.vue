<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import InlineEntityCard from '../chat/InlineEntityCard.vue'
import WebSourceCard from '../chat/WebSourceCard.vue'
import PanelToggleButton from './PanelToggleButton.vue'

/**
 * Right-column main agent panel: conversation stream.
 */
defineEmits<{ collapse: [] }>()

const chat = useChatStore()
const {
  messages,
  streamingReply,
  streamingWebSources,
  isStreaming,
  progressLabel,
  error,
} = storeToRefs(chat)

const streamRef = ref<HTMLElement | null>(null)

const AGENT_LABELS: Record<string, string> = {
  inspiration: 'Inspiration',
  research: 'Research',
  structure: 'Structure',
  simulation: 'Simulation',
  small_talk: 'Chat',
}

async function scrollToBottom() {
  await nextTick()
  if (streamRef.value) {
    streamRef.value.scrollTop = streamRef.value.scrollHeight
  }
}

watch([messages, streamingReply], scrollToBottom, { deep: true })
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
        <div class="chat-msg__bubble">{{ message.content }}</div>
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
      </div>

      <div v-if="streamingReply" class="chat-msg chat-msg--assistant">
        <div class="chat-msg__bubble">{{ streamingReply }}</div>
        <div v-if="streamingWebSources.length" class="chat-msg__sources">
          <WebSourceCard
            v-for="(source, index) in streamingWebSources"
            :key="`stream-src-${index}`"
            :source="source"
          />
        </div>
      </div>
      <p v-else-if="isStreaming" class="right-stage__progress">{{ progressLabel }}</p>
      <p v-if="error" class="right-stage__error">{{ error }}</p>
    </div>
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

.right-stage__chat {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.right-stage__empty {
  margin: 0;
  color: var(--muted, #888);
  font-size: 13px;
  line-height: 1.6;
}

.right-stage__progress {
  margin: 0;
  color: var(--muted, #888);
  font-size: 12px;
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
  font-size: 10px;
  color: var(--accent-deep);
  font-weight: 600;
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

.chat-msg--assistant .chat-msg__bubble {
  background: #f3f4f6;
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
</style>
