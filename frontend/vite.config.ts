import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 允许桌面启动脚本通过环境变量指定端口，非法输入回退到默认值。
function resolvePort(rawPort: string | undefined, fallback: number) {
  const parsedPort = Number(rawPort)

  if (Number.isInteger(parsedPort) && parsedPort > 0) {
    return parsedPort
  }

  return fallback
}

const frontendHost = process.env.FRONTEND_DEV_HOST ?? '127.0.0.1'
const frontendPort = resolvePort(process.env.FRONTEND_DEV_PORT ?? process.env.VITE_PORT, 5174)

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // Electron 打包后通过 file:// 加载 dist，因此构建产物需要使用相对路径。
  base: command === 'build' ? './' : '/',
  plugins: [vue()],
  server: {
    host: frontendHost,
    port: frontendPort,
    strictPort: true,
  },
}))
