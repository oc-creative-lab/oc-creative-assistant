<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useComposerStore } from '../../stores/useComposerStore'
import { useChatStore } from '../../stores/useChatStore'
import QuotedNodeChip from './QuotedNodeChip.vue'

/**
 * Persistent bottom composer — sends to the main LangGraph agent (chat stream + extraction).
 */
const composer = useComposerStore()
const chat = useChatStore()
const { references, input, collapsed, webSearchMode } = storeToRefs(composer)
const { isStreaming, progressLabel } = storeToRefs(chat)

const isSending = ref(false)

const webSearchTitle = computed(() => {
  if (webSearchMode.value === 'on') return '联网搜索：强制开启（点击切换）'
  if (webSearchMode.value === 'off') return '联网搜索：已关闭（点击切换）'
  return '联网搜索：自动判断（点击切换）'
})

function toggleCollapsed() {
  composer.setCollapsed(!collapsed.value)
}

async function handleSend() {
  const message = input.value.trim()
  const quotedIds = references.value.map((r) => r.id)
  if ((!message && quotedIds.length === 0) || isSending.value || isStreaming.value) return

  isSending.value = true
  try {
    const text =
      message ||
      `Please consider these ${quotedIds.length} quoted node(s) and help me develop them further.`
    await chat.send(text, quotedIds, webSearchMode.value)
    composer.$patch({ input: '', references: [] })
  } finally {
    isSending.value = false
  }
}
</script>

<template>
  <div class="composer-wrap" :class="{ 'is-collapsed': collapsed }">
    <button
      type="button"
      class="composer-handle"
      :aria-label="collapsed ? 'Expand composer' : 'Collapse composer'"
      :title="collapsed ? 'Expand composer' : 'Collapse composer'"
      @click="toggleCollapsed"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <polyline
          v-if="collapsed"
          points="6 15 12 9 18 15"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <polyline
          v-else
          points="6 9 12 15 18 9"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div v-show="!collapsed" class="composer-body">
      <p v-if="isStreaming && progressLabel" class="composer__status">{{ progressLabel }}</p>

      <div v-if="references.length" class="composer__refs">
        <QuotedNodeChip
          v-for="ref in references"
          :key="ref.id"
          :node="ref"
          @remove="composer.removeReference"
        />
      </div>

      <form class="composer__bar" @submit.prevent="handleSend">
        <button
          type="button"
          class="composer__web"
          :class="{
            'is-on': webSearchMode === 'on',
            'is-off': webSearchMode === 'off',
          }"
          :title="webSearchTitle"
          :aria-label="webSearchTitle"
          :disabled="isStreaming"
          @click="composer.cycleWebSearchMode()"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" class="composer__web-icon">
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.75" />
            <path
              d="M3 12h18M12 3c2.5 2.8 4 6 4 9s-1.5 6.2-4 9M12 3c-2.5 2.8-4 6-4 9s1.5 6.2 4 9"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
            />
            <path
              v-if="webSearchMode === 'off'"
              d="M5 5l14 14"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </button>
        <input
          v-model="input"
          class="composer__input"
          type="text"
          placeholder="Talk to the agent — quote nodes from the canvas with Ctrl+C…"
          :disabled="isStreaming"
        />
        <button
          type="submit"
          class="composer__send"
          aria-label="Send"
          :disabled="isSending || isStreaming"
        >
          {{ isSending || isStreaming ? '…' : '↵' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.composer-wrap {
  position: relative;
  flex-shrink: 0;
  border-top: 1px solid var(--border, #e5e7eb);
  background: var(--app-bg, #fff);
  padding: 12px 16px 12px;
}

.composer-wrap.is-collapsed {
  padding: 0;
  height: 0;
  border-top: 1px solid var(--border, #e5e7eb);
}

/* Small chevron sitting on the top divider — no box, no extra row */
.composer-handle {
  position: absolute;
  top: 0;
  left: 50%;
  z-index: 2;
  transform: translate(-50%, -50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 12px;
  padding: 0;
  border: none;
  background: var(--app-bg, #fff);
  color: var(--muted, #888);
  cursor: pointer;
  line-height: 0;
  transition: color 0.15s ease;
}

.composer-handle:hover {
  color: var(--accent);
}

.composer-handle svg {
  width: 11px;
  height: 11px;
}

.composer-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.composer__status {
  margin: 0;
  font-size: 11px;
  color: var(--muted, #888);
}

.composer__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.composer__bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.composer__web {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid var(--border, #ddd);
  background: #fff;
  color: var(--muted, #888);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.composer__web:hover:not(:disabled) {
  color: var(--accent);
  border-color: #c7d2fe;
}

.composer__web.is-on {
  color: #fff;
  background: var(--accent, #6366f1);
  border-color: var(--accent, #6366f1);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.composer__web.is-off {
  color: #9ca3af;
  background: #f9fafb;
  opacity: 0.85;
}

.composer__web:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.composer__web-icon {
  width: 18px;
  height: 18px;
}

.composer__input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
}

.composer__input:disabled {
  opacity: 0.7;
}

.composer__send {
  flex-shrink: 0;
  width: 36px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.composer__send:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
