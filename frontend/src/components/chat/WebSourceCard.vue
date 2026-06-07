<script setup lang="ts">
import { computed } from 'vue'
import type { WebSourceDto } from '../../api/chatApi'

const props = defineProps<{ source: WebSourceDto }>()

const host = computed(() => {
  try {
    return new URL(props.source.url).hostname.replace(/^www\./, '')
  } catch {
    return props.source.url
  }
})

const displayTitle = computed(() => props.source.title?.trim() || host.value)
</script>

<template>
  <a
    class="web-source-card"
    :href="source.url"
    target="_blank"
    rel="noopener noreferrer"
  >
    <span class="web-source-card__icon" aria-hidden="true">🔗</span>
    <span class="web-source-card__body">
      <span class="web-source-card__title">{{ displayTitle }}</span>
      <span class="web-source-card__url">{{ host }}</span>
      <span v-if="source.snippet" class="web-source-card__snippet">{{ source.snippet }}</span>
    </span>
  </a>
</template>

<style scoped>
.web-source-card {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: inherit;
  text-decoration: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.web-source-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.12);
}

.web-source-card__icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1.4;
}

.web-source-card__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.web-source-card__title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text, #111827);
}

.web-source-card__url {
  font-size: 11px;
  color: #6366f1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.web-source-card__snippet {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--muted, #6b7280);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
