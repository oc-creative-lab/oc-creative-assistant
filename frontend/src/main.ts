import { createApp } from 'vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './style.css'
import App from './App.vue'

// 前端唯一入口，业务状态从 AppShell 开始向下分发。
createApp(App).mount('#app')
