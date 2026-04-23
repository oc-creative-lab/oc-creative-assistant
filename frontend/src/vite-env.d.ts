/// <reference types="vite/client" />

interface Window {
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
