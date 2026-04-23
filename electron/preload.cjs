const { contextBridge } = require('electron')

function readAdditionalArgument(name) {
  const prefix = `--${name}=`
  const entry = process.argv.find((argument) => argument.startsWith(prefix))

  if (!entry) {
    return null
  }

  return entry.slice(prefix.length)
}

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
})
