import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Let the desktop launch script specify the port via an environment variable; invalid input falls back to the default.
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
  // After Electron packaging, dist is loaded via file://, so the build output must use relative paths.
  base: command === 'build' ? './' : '/',
  plugins: [vue()],
  server: {
    host: frontendHost,
    port: frontendPort,
    strictPort: true,
  },
}))
