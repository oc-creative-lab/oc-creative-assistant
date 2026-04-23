<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type HealthPayload = {
  service: string
  status: string
}

const desktopConfig = window.ocDesktop?.config ?? null
const desktopRuntime = window.ocDesktop?.runtime ?? null
const rendererUrl = window.location.origin
const backendBaseUrl = (
  desktopConfig?.backendUrl ||
  import.meta.env.VITE_BACKEND_URL ||
  'http://127.0.0.1:9000'
).replace(/\/$/, '')

const healthState = ref<'checking' | 'online' | 'offline'>('checking')
const healthMessage = ref('Checking local backend...')
const healthPayload = ref<HealthPayload | null>(null)
const lastCheckedAt = ref<string | null>(null)

const rendererLabel = computed(() => {
  if (!desktopRuntime) {
    return 'Browser dev server'
  }

  return `Electron ${desktopRuntime.versions.electron}`
})

const rendererDetails = computed(() => {
  if (!desktopRuntime) {
    return 'Running in the Vite renderer. Launch the same frontend through Electron to validate the desktop shell.'
  }

  return `${desktopRuntime.platform} | Chrome ${desktopRuntime.versions.chrome} | Node ${desktopRuntime.versions.node}`
})

async function checkBackend() {
  healthState.value = 'checking'
  healthMessage.value = 'Checking local backend...'

  try {
    const response = await fetch(`${backendBaseUrl}/health`)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const payload = (await response.json()) as HealthPayload

    healthPayload.value = payload
    healthState.value = 'online'
    healthMessage.value = 'Backend responded successfully'
    lastCheckedAt.value = new Date().toLocaleTimeString()
  } catch (error) {
    healthPayload.value = null
    healthState.value = 'offline'
    healthMessage.value =
      error instanceof Error
        ? `Backend unavailable: ${error.message}`
        : 'Backend unavailable'
    lastCheckedAt.value = new Date().toLocaleTimeString()
  }
}

onMounted(() => {
  void checkBackend()
})
</script>

<template>
  <main class="app-shell">
    <section class="hero-panel">
      <p class="eyebrow">OC Creative Assistant PoC</p>
      <h1>Local desktop shell is wired and ready for the next modules.</h1>
      <p class="hero-copy">
        This page only validates the current minimal loop: Vue renderer, Electron shell,
        and a local FastAPI service.
      </p>

      <div class="cta-row">
        <button
          class="primary-button"
          type="button"
          @click="checkBackend"
          :disabled="healthState === 'checking'"
        >
          {{ healthState === 'checking' ? 'Checking backend...' : 'Recheck backend' }}
        </button>
        <a
          class="secondary-link"
          :href="`${backendBaseUrl}/docs`"
          target="_blank"
          rel="noreferrer"
        >
          Open FastAPI docs
        </a>
      </div>
    </section>

    <section class="status-grid">
      <article class="status-card">
        <p class="card-label">Renderer</p>
        <h2>{{ rendererLabel }}</h2>
        <p>{{ rendererDetails }}</p>
      </article>

      <article class="status-card">
        <p class="card-label">Frontend entry</p>
        <h2>{{ rendererUrl }}</h2>
        <p>Electron dev mode will load this URL directly instead of bootstrapping a second frontend.</p>
      </article>

      <article class="status-card">
        <p class="card-label">Backend health</p>
        <h2 class="status-value" :data-state="healthState">{{ healthMessage }}</h2>
        <p v-if="healthPayload">
          {{ healthPayload.service }} returned <code>{{ healthPayload.status }}</code>
          <span v-if="lastCheckedAt">at {{ lastCheckedAt }}</span>
        </p>
        <p v-else>
          Expecting <code>{{ backendBaseUrl }}/health</code>
          <span v-if="lastCheckedAt">at {{ lastCheckedAt }}</span>
        </p>
      </article>

      <article class="status-card">
        <p class="card-label">Next integration surface</p>
        <h2>Desktop shell only</h2>
        <p>
          Vue Flow, SQLite, ChromaDB, LangGraph, and Agent Sidebar modules can be added on top
          of this base without replacing the existing frontend or backend stack.
        </p>
      </article>
    </section>
  </main>
</template>
