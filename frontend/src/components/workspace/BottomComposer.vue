<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useComposerStore } from '../../stores/useComposerStore'
import { useAiOutputStore } from '../../stores/useAiOutputStore'
import { streamWorkspaceChat } from '../../api/workspaceChatApi'
import QuotedNodeChip from './QuotedNodeChip.vue'

/**
 * 底部常驻对话框（second_revision 改点 B/C / W5）。
 *
 * 引用节点卡片区（选中节点 → 复制到对话框）+ 单行输入框。发送时把输入 + 引用
 * 节点 id 发给工作台被动 agent（SSE），输出 push 进右栏 useAiOutputStore。
 * Enter 发送，无 Shift+Enter 换行（保持单行简单）。
 */
const route = useRoute()
const composer = useComposerStore()
const aiOutput = useAiOutputStore()
const { references, input } = storeToRefs(composer)

const isSending = ref(false)

async function handleSend() {
  const message = input.value.trim()
  const quotedIds = references.value.map((r) => r.id)
  if ((!message && quotedIds.length === 0) || isSending.value) return

  const projectId = String(route.params.projectId)
  isSending.value = true
  try {
    await streamWorkspaceChat(projectId, message, quotedIds, (event) => {
      if (event.type === 'output') {
        aiOutput.push({ type: event.output_type, content: event.content })
      }
    })
    composer.clear()
  } catch {
    aiOutput.push({ type: 'feedback', content: '(The assistant could not respond. Try again.)' })
  } finally {
    isSending.value = false
  }
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
      />
      <button type="submit" class="composer__send" :disabled="isSending">
        {{ isSending ? '…' : 'Send' }}
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
  background: var(--app-bg, #fff);
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
