import { ref } from 'vue'
import type { IndexingStatusDto } from '../api/graphApi'

/**
 * Centralizes the translation and display of the backend embedding / ChromaDB sync status.
 *
 * The status bar (indexState) gives a short phrase; the alert banner (indexingAlert) translates the detailed reason and
 * condenses the backend's raw exception into a hint the user can act on directly, avoiding exposing the entire API-error JSON to the UI.
 */
export function useIndexingStatus() {
  const indexingStatus = ref<IndexingStatusDto | undefined>()
  const indexingAlert = ref('')
  const indexState = ref('Vector index not checked')

  function simplifyError(error?: string | null) {
    if (!error) {
      return 'Please check the embedding configuration in backend/.env.'
    }
    if (error.includes('invalid_api_key') || error.includes('Incorrect API key') || error.includes('401')) {
      return 'Invalid API Key.'
    }
    if (error.toLowerCase().includes('timeout')) {
      return 'The embedding service request timed out, please try again later.'
    }
    if (error.includes('Connection') || error.includes('connect') || error.includes('network')) {
      return 'Cannot connect to the embedding service, please check the network or base_url.'
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
    const missingText = missingCount > 0 ? `There are currently ${missingCount} nodes still missing a usable vector.` : ''
    return `SQLite was saved, but the vector index ${indexing.status === 'failed' ? 'failed' : 'is incomplete'}. ${problem} ${missingText}`.trim()
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