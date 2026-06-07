import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './style.css'
import App from './App.vue'
import { router } from './router'

/**
 * Frontend application entry point.
 *
 * After the multi-page refactor, the root component only mounts <router-view>;
 * cross-route shared state goes through Pinia, while fine-grained operations
 * within a single canvas remain the responsibility of individual composables
 * (see first_revision decision 6).
 */
const scrollHideTimers = new WeakMap<EventTarget, ReturnType<typeof setTimeout>>()

document.addEventListener(
  'scroll',
  (event) => {
    const target = event.target
    if (!(target instanceof Element)) return

    target.classList.add('is-scrolling')

    const existing = scrollHideTimers.get(target)
    if (existing) clearTimeout(existing)

    scrollHideTimers.set(
      target,
      setTimeout(() => {
        target.classList.remove('is-scrolling')
        scrollHideTimers.delete(target)
      }, 700),
    )
  },
  true,
)

createApp(App).use(createPinia()).use(router).mount('#app')
