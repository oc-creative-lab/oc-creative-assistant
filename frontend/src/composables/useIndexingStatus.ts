import { ref } from 'vue'
import type { IndexingStatusDto } from '../api/graphApi'

/**
 * 集中处理后端 embedding / ChromaDB 同步状态的翻译与展示。
 *
 * 状态栏 (indexState) 给短句; 告警条 (indexingAlert) 翻译详细原因, 并把后端
 * 原始异常压成用户能直接处理的提示, 避免 API 报错的整段 JSON 暴露给界面。
 */
export function useIndexingStatus() {
  const indexingStatus = ref<IndexingStatusDto | undefined>()
  const indexingAlert = ref('')
  const indexState = ref('Vector index not checked')

  function simplifyError(error?: string | null) {
    if (!error) {
      return 'Check the embedding configuration in backend/.env.'
    }
    if (error.includes('invalid_api_key') || error.includes('Incorrect API key') || error.includes('401')) {
      return 'Invalid API key.'
    }
    if (error.toLowerCase().includes('timeout')) {
      return 'Embedding service request timed out, please retry later.'
    }
    if (error.includes('Connection') || error.includes('connect') || error.includes('network')) {
      return 'Cannot reach the embedding service, check the network or base_url.'
    }
    return error.length > 120 ? `${error.slice(0, 120)}...` : error
  }

  function formatState(indexing?: IndexingStatusDto) {
    if (!indexing || indexing.status === 'not_checked') {
      return 'Vector index not checked'
    }
    if (indexing.status === 'synced') {
      return `Vector index synced ${indexing.indexed_nodes}/${indexing.expected_nodes}`
    }
    return indexing.status === 'failed'
      ? `Vector index failed ${indexing.indexed_nodes}/${indexing.expected_nodes}`
      : `Vector index incomplete ${indexing.indexed_nodes}/${indexing.expected_nodes}`
  }

  function formatAlert(indexing: IndexingStatusDto) {
    const problem = simplifyError(indexing.error)
    const missingCount = indexing.missing_node_ids.length
    const missingText = missingCount > 0 ? `${missingCount} node(s) still lack a usable vector.` : ''
    return `Saved to SQLite, but the vector index ${indexing.status === 'failed' ? 'failed' : 'is incomplete'}. ${problem} ${missingText}`.trim()
  }

  function applyIndexingStatus(indexing?: IndexingStatusDto) {
    indexingStatus.value = indexing
    indexState.value = formatState(indexing)
    if (!indexing || indexing.status === 'not_checked' || indexing.status === 'synced') {
      indexingAlert.value = ''
      return
    }
    indexingAlert.value = formatAlert(indexing)
  }

  function dismissAlert() {
    indexingAlert.value = ''
  }

  return {
    indexingStatus,
    indexingAlert,
    indexState,
    applyIndexingStatus,
    dismissAlert,
  }
}