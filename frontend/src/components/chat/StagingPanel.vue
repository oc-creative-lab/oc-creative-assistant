<script setup lang="ts">
import type { AgentStagingBatchDto } from '../../api/chatApi'
import StagingItemCard from './StagingItemCard.vue'

/**
 * staging 批次列表。
 *
 * 同一 Agent turn 产生的变更聚合在一个 batch 里, 提供"接受全部"和
 * "拒绝全部"快捷操作; 也允许用户对单条做更精细的处理。
 */
defineProps<{
  batches: AgentStagingBatchDto[]
}>()

const emit = defineEmits<{
  resolveItem: [stagingId: string, action: 'accept' | 'reject']
  resolveBatch: [batchId: string, action: 'accept_all' | 'reject_all']
}>()
</script>

<template>
  <section v-if="batches.length > 0" class="staging-panel">
    <header class="staging-panel__head">
      <h3>Pending changes</h3>
      <span class="staging-panel__count">{{ batches.length }} batch(es)</span>
    </header>

    <div v-for="batch in batches" :key="batch.batch_id" class="staging-batch">
      <header class="staging-batch__head">
        <span>{{ batch.items.length }} item(s)</span>
        <div class="staging-batch__actions">
          <button type="button" @click="emit('resolveBatch', batch.batch_id, 'accept_all')">
            Accept all
          </button>
          <button type="button" class="ghost" @click="emit('resolveBatch', batch.batch_id, 'reject_all')">
            Reject all
          </button>
        </div>
      </header>
      <div class="staging-batch__items">
        <StagingItemCard
          v-for="item in batch.items"
          :key="item.id"
          :item="item"
          @resolve="(id, action) => emit('resolveItem', id, action)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.staging-panel {
  display: grid;
  gap: 10px;
}

.staging-panel__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.staging-panel__head h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text);
}

.staging-panel__count {
  font-size: 0.78rem;
  color: var(--muted);
}

.staging-batch {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--app-bg);
}

.staging-batch__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--muted);
}

.staging-batch__actions {
  display: flex;
  gap: 6px;
}

.staging-batch__actions button {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--accent-border);
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.78rem;
  cursor: pointer;
}

.staging-batch__actions .ghost {
  color: var(--muted);
  background: #ffffff;
  border-color: var(--border);
}

.staging-batch__items {
  display: grid;
  gap: 8px;
}
</style>