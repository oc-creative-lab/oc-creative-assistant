/// <reference types="vite/client" />

interface Window {
  /** Minimal runtime bridge injected by the Electron preload; may be absent during browser-based development. */
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
