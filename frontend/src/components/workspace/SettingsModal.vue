<script setup lang="ts">
import { ref, watch } from 'vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; export: []; import: [] }>()

const APP_VERSION = '0.1.0'

/** localStorage 支持的布尔开关。 */
function useFlag(key: string, fallback = false) {
  const stored = localStorage.getItem(key)
  const r = ref(stored === null ? fallback : stored === 'true')
  watch(r, (v) => localStorage.setItem(key, String(v)))
  return r
}

const zoom = ref(Number(localStorage.getItem('oc.canvasZoom')) || 0.8)
watch(zoom, (v) => localStorage.setItem('oc.canvasZoom', String(v)))

const snapToGrid = useFlag('oc.snapToGrid', false)
const leftCollapsedDefault = useFlag('oc.leftCollapsed', false)
const rightCollapsedDefault = useFlag('oc.rightCollapsed', false)

function resetWidths() {
  localStorage.removeItem('oc.leftWidth')
  localStorage.removeItem('oc.rightWidth')
  window.location.reload()
}

function requestImport() {
  emit('import')
  emit('close')
}
</script>

<template>
  <div v-if="open" class="settings-mask" @click.self="emit('close')">
    <div class="settings-modal" role="dialog" aria-modal="true">
      <header class="settings-modal__head">
        <strong>Settings</strong>
        <button type="button" class="settings-modal__close" @click="emit('close')">✕</button>
      </header>

      <div class="settings-modal__body">
        <section class="settings-group">
          <h4 class="settings-group__title">Canvas</h4>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Default canvas zoom</span>
              <span class="settings-row__desc">Zoom level used when a canvas first loads.</span>
            </div>
            <div class="settings-row__control">
              <input type="range" min="0.4" max="1.2" step="0.1" v-model.number="zoom" />
              <em>{{ zoom.toFixed(1) }}×</em>
            </div>
          </div>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Snap to grid</span>
              <span class="settings-row__desc">Align nodes to a grid while dragging.</span>
            </div>
            <button type="button" class="settings-switch" :class="{ 'is-on': snapToGrid }"
              role="switch" :aria-checked="snapToGrid" @click="snapToGrid = !snapToGrid">
              <span class="settings-switch__dot" />
            </button>
          </div>
        </section>

        <section class="settings-group">
          <h4 class="settings-group__title">Layout</h4>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Collapse navigation on startup</span>
              <span class="settings-row__desc">Start with the left sidebar minimized.</span>
            </div>
            <button type="button" class="settings-switch" :class="{ 'is-on': leftCollapsedDefault }"
              role="switch" :aria-checked="leftCollapsedDefault"
              @click="leftCollapsedDefault = !leftCollapsedDefault">
              <span class="settings-switch__dot" />
            </button>
          </div>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Collapse Agent panel on startup</span>
              <span class="settings-row__desc">Start with the right sidebar minimized.</span>
            </div>
            <button type="button" class="settings-switch" :class="{ 'is-on': rightCollapsedDefault }"
              role="switch" :aria-checked="rightCollapsedDefault"
              @click="rightCollapsedDefault = !rightCollapsedDefault">
              <span class="settings-switch__dot" />
            </button>
          </div>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Reset sidebar widths</span>
              <span class="settings-row__desc">Restore the default left/right panel sizes.</span>
            </div>
            <button type="button" class="settings-btn" @click="resetWidths">Reset</button>
          </div>
        </section>

        <section class="settings-group">
          <h4 class="settings-group__title">Data</h4>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Export project</span>
              <span class="settings-row__desc">Download all three boards as one .oc file.</span>
            </div>
            <button type="button" class="settings-btn" @click="emit('export')">Export</button>
          </div>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">Import project</span>
              <span class="settings-row__desc">Replace all three boards from a .oc file.</span>
            </div>
            <button type="button" class="settings-btn" @click="requestImport">Import</button>
          </div>
        </section>

        <section class="settings-group">
          <h4 class="settings-group__title">About</h4>
          <div class="settings-row">
            <div class="settings-row__text">
              <span class="settings-row__title">OC Creative Assistant</span>
              <span class="settings-row__desc">Version {{ APP_VERSION }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 14, 28, 0.38);
  display: grid;
  place-items: center;
  z-index: 50;
}
.settings-modal {
  width: 460px;
  max-width: 92vw;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  background: var(--panel, #fff);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}
.settings-modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.settings-modal__close {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: var(--muted);
}
.settings-modal__body {
  padding: 8px 16px 16px;
  overflow: auto;
}
.settings-group {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.settings-group:last-child {
  border-bottom: none;
}
.settings-group__title {
  margin: 0 0 8px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
}
.settings-row__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.settings-row__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.settings-row__desc {
  font-size: 12px;
  color: var(--muted);
}
.settings-row__control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.settings-row__control input[type='range'] {
  accent-color: var(--accent);
}
.settings-row__control em {
  font-style: normal;
  color: var(--accent);
}
.settings-btn {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--app-bg, #fff);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
.settings-switch {
  position: relative;
  width: 40px;
  height: 22px;
  border: none;
  border-radius: 999px;
  background: var(--border);
  cursor: pointer;
  transition: background 0.18s;
  flex: none;
}
.settings-switch.is-on {
  background: var(--accent);
}
.settings-switch__dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.18s;
}
.settings-switch.is-on .settings-switch__dot {
  transform: translateX(18px);
}
</style>