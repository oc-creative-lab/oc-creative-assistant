const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { app, BrowserWindow, shell } = require('electron')

let backendProcess = null

function resolvePort(rawPort, fallback) {
  const parsedPort = Number(rawPort)

  if (Number.isInteger(parsedPort) && parsedPort > 0) {
    return parsedPort
  }

  return fallback
}

function resolveRendererUrl() {
  const host = process.env.FRONTEND_DEV_HOST ?? '127.0.0.1'
  const port = process.env.FRONTEND_DEV_PORT ?? '5173'

  return process.env.ELECTRON_RENDERER_URL ?? `http://${host}:${port}`
}

function buildHttpUrl(host, port) {
  return `http://${host}:${port}`
}

function buildHealthUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/health`
}

async function isPortFree(host, port) {
  return new Promise((resolve) => {
    const server = net.createServer()

    server.once('error', () => {
      resolve(false)
    })

    server.once('listening', () => {
      server.close(() => resolve(true))
    })

    server.listen(port, host)
  })
}

async function findAvailablePort(host, preferredPort, maxAttempts = 20) {
  for (let offset = 0; offset < maxAttempts; offset += 1) {
    const candidatePort = preferredPort + offset

    if (await isPortFree(host, candidatePort)) {
      return candidatePort
    }
  }

  throw new Error(
    `Could not find an available port for ${host} starting from ${preferredPort}.`,
  )
}

async function waitForUrl(url, timeoutMs = 30_000, intervalMs = 500) {
  const startedAt = Date.now()

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url)

      if (response.ok) {
        return
      }
    } catch {
      // Keep polling until the endpoint is ready or the timeout expires.
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  throw new Error(`Timed out waiting for ${url}`)
}

function getBundledFrontendEntry() {
  return path.join(process.resourcesPath, 'frontend', 'index.html')
}

function getBundledBackendExecutable() {
  const executableName = process.platform === 'win32'
    ? 'oc-creative-backend.exe'
    : 'oc-creative-backend'

  return path.join(process.resourcesPath, 'backend', executableName)
}

function stopBundledBackend() {
  if (!backendProcess || backendProcess.killed) {
    return
  }

  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(backendProcess.pid), '/t', '/f'], { stdio: 'ignore' })
  } else {
    backendProcess.kill('SIGTERM')
  }
}

async function startBundledBackend() {
  const backendHost = process.env.BACKEND_HOST ?? '127.0.0.1'
  const preferredBackendPort = resolvePort(process.env.BACKEND_PORT, 9000)
  const selectedBackendPort = await findAvailablePort(backendHost, preferredBackendPort)
  const backendUrl = buildHttpUrl(backendHost, selectedBackendPort)
  const backendHealthUrl = buildHealthUrl(backendUrl)
  const executablePath = getBundledBackendExecutable()

  if (!fs.existsSync(executablePath)) {
    throw new Error(`Bundled backend executable not found at ${executablePath}`)
  }

  backendProcess = spawn(
    executablePath,
    ['--host', backendHost, '--port', String(selectedBackendPort)],
    {
      stdio: 'ignore',
      windowsHide: true,
    },
  )

  backendProcess.on('exit', (code, signal) => {
    backendProcess = null

    if (app.isQuitting) {
      return
    }

    const reason = signal ? `signal ${signal}` : `code ${code ?? 0}`
    console.error(`[electron] Bundled backend exited unexpectedly with ${reason}`)
  })

  await waitForUrl(backendHealthUrl)

  return backendUrl
}

async function resolveRuntimeConfig() {
  if (!app.isPackaged) {
    return {
      backendUrl: process.env.BACKEND_BASE_URL ?? null,
      rendererUrl: resolveRendererUrl(),
    }
  }

  const backendUrl = await startBundledBackend()

  return {
    backendUrl,
    rendererUrl: null,
  }
}

async function loadRenderer(mainWindow, rendererUrl) {
  try {
    console.log(`[electron] Loading renderer from ${rendererUrl}`)
    await mainWindow.loadURL(rendererUrl)
    console.log('[electron] Renderer loaded successfully')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown renderer error'
    const fallbackHtml = `
      <!doctype html>
      <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <title>Renderer not available</title>
          <style>
            body {
              margin: 0;
              min-height: 100vh;
              display: grid;
              place-items: center;
              font: 16px/1.5 "Segoe UI", sans-serif;
              background: #f7f2eb;
              color: #2e2419;
            }
            main {
              width: min(640px, calc(100% - 48px));
              padding: 32px;
              border-radius: 24px;
              border: 1px solid rgba(74, 58, 39, 0.12);
              background: rgba(255, 255, 255, 0.95);
              box-shadow: 0 20px 50px rgba(74, 58, 39, 0.1);
            }
            code {
              padding: 0.16rem 0.45rem;
              border-radius: 999px;
              background: rgba(46, 36, 25, 0.07);
            }
          </style>
        </head>
        <body>
          <main>
            <h1>Renderer not available</h1>
            <p>Electron could not load the frontend entry at <code>${rendererUrl}</code>.</p>
            <p>Details: ${message}</p>
          </main>
        </body>
      </html>
    `

    await mainWindow.loadURL(`data:text/html;charset=UTF-8,${encodeURIComponent(fallbackHtml)}`)
  }
}

function isHttpUrl(url) {
  return /^https?:/i.test(url)
}

function hasSameOrigin(url, rendererOrigin) {
  try {
    return new URL(url).origin === rendererOrigin
  } catch {
    return false
  }
}

function wireExternalNavigation(mainWindow, rendererUrl) {
  const rendererOrigin = rendererUrl ? new URL(rendererUrl).origin : null

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (rendererOrigin && hasSameOrigin(url, rendererOrigin)) {
      return { action: 'allow' }
    }

    if (isHttpUrl(url)) {
      void shell.openExternal(url)
    }

    return { action: 'deny' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url === mainWindow.webContents.getURL()) {
      return
    }

    if (!rendererOrigin && isHttpUrl(url)) {
      event.preventDefault()
      void shell.openExternal(url)
      return
    }

    if (rendererOrigin && !hasSameOrigin(url, rendererOrigin)) {
      event.preventDefault()
      void shell.openExternal(url)
    }
  })
}

async function createWindow(runtimeConfig) {
  const mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: '#f6efe6',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      additionalArguments: runtimeConfig.backendUrl
        ? [`--backend-url=${runtimeConfig.backendUrl}`]
        : [],
    },
  })

  wireExternalNavigation(mainWindow, runtimeConfig.rendererUrl)

  if (runtimeConfig.rendererUrl) {
    await loadRenderer(mainWindow, runtimeConfig.rendererUrl)
    return
  }

  const bundledFrontendEntry = getBundledFrontendEntry()
  console.log(`[electron] Loading packaged renderer from ${bundledFrontendEntry}`)
  await mainWindow.loadFile(bundledFrontendEntry)
}

app.on('before-quit', () => {
  app.isQuitting = true
  stopBundledBackend()
})

app.whenReady().then(async () => {
  if (process.platform === 'win32') {
    app.setAppUserModelId('com.occreativeassistant.app')
  }

  const runtimeConfig = await resolveRuntimeConfig()
  await createWindow(runtimeConfig)

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow(runtimeConfig)
    }
  })
})

app.on('window-all-closed', () => {
  stopBundledBackend()

  if (process.platform !== 'darwin') {
    app.quit()
  }
})
