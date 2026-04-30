/// <reference types="vite/client" />

interface Window {
  /** Electron preload 注入的最小运行时桥，浏览器开发态下可能不存在。 */
  ocDesktop?: {
    config: {
      backendUrl: string | null
    }
    runtime: {
      platform: string
      versions: {
        chrome: string
        electron: string
        node: string
      }
    }
  }
}
