const { contextBridge, ipcRenderer } = require('electron')

const PDF_EXPORT_CHANNEL = 'oc:export-project-pdf'

// Read a single argument passed in by the main process via additionalArguments.
function readAdditionalArgument(name) {
  const prefix = `--${name}=`
  const entry = process.argv.find((argument) => argument.startsWith(prefix))

  if (!entry) {
    return null
  }

  return entry.slice(prefix.length)
}

// Expose only the minimal necessary runtime information to the renderer process.
// Note: do not expose arbitrary Node/Electron APIs here, to avoid widening the frontend attack surface.
contextBridge.exposeInMainWorld('ocDesktop', {
  config: {
    backendUrl: readAdditionalArgument('backend-url') ?? process.env.BACKEND_BASE_URL ?? null,
  },
  runtime: {
    platform: process.platform,
    versions: {
      chrome: process.versions.chrome,
      electron: process.versions.electron,
      node: process.versions.node,
    },
  },
  exportProjectPdf: (payload) => ipcRenderer.invoke(PDF_EXPORT_CHANNEL, payload),
})
