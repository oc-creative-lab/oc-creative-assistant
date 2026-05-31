import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './style.css'
import App from './App.vue'
import { router } from './router'

/**
 * 前端应用入口。
 *
 * 多页架构重构后，根组件只挂载 <router-view>；跨路由共享状态走 Pinia，
 * 单画布内的细粒度操作仍由各 composable 负责（见 first_revision 决策 6）。
 */
createApp(App).use(createPinia()).use(router).mount('#app')
