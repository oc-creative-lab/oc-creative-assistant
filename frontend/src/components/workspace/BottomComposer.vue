<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useComposerStore } from '../../stores/useComposerStore'
import { useChatStore } from '../../stores/useChatStore'
import QuotedNodeChip from './QuotedNodeChip.vue'

/**
 * 底部常驻对话框：驱动完整 Agent（streamChat）。
 *
 * 输入 + 引用节点发给主对话 StateGraph，历史与流式回复、staging 都由
 * useChatStore 持有，右栏 RightStageOutput 读取同一份状态渲染。
 * 关闭自动抽取，画布增删改一律走显式 staging（HITL）。
 */
const route = useRoute()
const composer = useComposerStore()
const chat = useChatStore()
const { references, input } = storeToRefs(composer)
const { isStreaming } = storeToRefs(chat)

onMounted(() => void chat.init(String(route.params.projectId)))
watch(
  () => route.params.projectId,
  (id) => {
    if (id) void chat.init(String(id))
  },
)

async function handleSend() {
  const message = input.value.trim()
  const quotedIds = references.value.map((r) => r.id)
  if ((!message && quotedIds.length === 0) || isStreaming.value) return
  composer.clear()
  await chat.send(message, quotedIds, false)
}
</script>

<template>
  <div class="composer">
    <div v-if="references.length" class="composer__refs">
      <QuotedNodeChip
        v-for="ref in references"
        :key="ref.id"
        :node="ref"
        @remove="composer.removeReference"
      />
    </div>
    <form class="composer__bar" @submit.prevent="handleSend">
      <input
        v-model="input"
        class="composer__input"
        type="text"
        placeholder="Ask anything — or copy nodes here to send with your message…"
        :disabled="isStreaming"
      />
      <button type="submit" class="composer__send" :disabled="isStreaming">
        {{ isStreaming ? '…' : 'Send' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.composer {
  border-top: 1px solid var(--border, #e5e7eb);
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background:
    radial-gradient(circle at 80% 0%, rgba(167, 139, 250, 0.1), transparent 60%),
    var(--panel);
}
.composer__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.composer__bar {
  display: flex;
  gap: 8px;
}
.composer__input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
}
.composer__send {
  padding: 0 18px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}
.composer__send:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>