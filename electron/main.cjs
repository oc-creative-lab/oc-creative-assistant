const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron')

// In packaged mode the Electron main process hosts the backend process; in dev mode it usually reuses an external uvicorn.
let backendProcess = null
const PDF_EXPORT_CHANNEL = 'oc:export-project-pdf'

// Normalize the port input, falling back to the default value when it is invalid.
function resolvePort(rawPort, fallback) {
  const parsedPort = Number(rawPort)

  if (Number.isInteger(parsedPort) && parsedPort > 0) {
    return parsedPort
  }

  return fallback
}

// Resolve the frontend entry URL to load in development mode.
function resolveRendererUrl() {
  const host = process.env.FRONTEND_DEV_HOST ?? '127.0.0.1'
  const port = process.env.FRONTEND_DEV_PORT ?? '5174'

  return process.env.ELECTRON_RENDERER_URL ?? `http://${host}:${port}`
}

// Build the local HTTP base URL from the host and port.
function buildHttpUrl(host, port) {
  return `http://${host}:${port}`
}

// Build the health endpoint URL from the backend base URL.
function buildHealthUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/health`
}

// Check whether a given local port is currently available.
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

// Search upward from the preferred port for an available one.
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

// Poll until a given HTTP URL becomes reachable.
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

// Resolve the location of the packaged frontend entry file within resources.
function getBundledFrontendEntry() {
  return path.join(process.resourcesPath, 'frontend', 'index.html')
}

// Resolve the location of the packaged backend executable within resources.
function getBundledBackendExecutable() {
  const executableName = process.platform === 'win32'
    ? 'oc-creative-backend.exe'
    : 'oc-creative-backend'

  return path.join(process.resourcesPath, 'backend', executableName)
}

// Resolve the desktop app icon in development and packaged builds.
function getAppIconPath() {
  const iconPath = path.join(__dirname, 'assets', 'icon.png')

  if (fs.existsSync(iconPath)) {
    return iconPath
  }

  return path.join(__dirname, 'assets', 'logo.png')
}

// Keep desktop PDF exports independent from renderer pop-up permissions.
function sanitizePdfFileName(value) {
  const rawName = String(value || 'project').trim() || 'project'
  const safeName = rawName
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/[. ]+$/g, '')
    .slice(0, 120) || 'project'

  return safeName.toLowerCase().endsWith('.pdf') ? safeName : `${safeName}.pdf`
}

async function exportHtmlToPdf(parentWindow, payload) {
  if (!payload || typeof payload.html !== 'string') {
    throw new Error('Invalid PDF export payload.')
  }

  const defaultPath = sanitizePdfFileName(payload.defaultFileName)
  const saveDialogOptions = {
    title: 'Export PDF',
    defaultPath,
    filters: [{ name: 'PDF', extensions: ['pdf'] }],
  }
  const saveResult = parentWindow
    ? await dialog.showSaveDialog(parentWindow, saveDialogOptions)
    : await dialog.showSaveDialog(saveDialogOptions)

  if (saveResult.canceled || !saveResult.filePath) {
    return { canceled: true }
  }

  const pdfWindow = new BrowserWindow({
    show: false,
    parent: parentWindow ?? undefined,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  try {
    const htmlUrl = `data:text/html;charset=UTF-8,${encodeURIComponent(payload.html)}`
    await pdfWindow.loadURL(htmlUrl)

    await pdfWindow.webContents.executeJavaScript(
      'document.fonts && document.fonts.ready ? document.fonts.ready.then(() => true) : true',
      true,
    ).catch(() => true)

    const pdf = await pdfWindow.webContents.printToPDF({
      printBackground: true,
      preferCSSPageSize: true,
    })

    await fs.promises.writeFile(saveResult.filePath, pdf)

    return { canceled: false, filePath: saveResult.filePath }
  } finally {
    if (!pdfWindow.isDestroyed()) {
      pdfWindow.close()
    }
  }
}

// Resolve the packaged backend data directory; portable follows the exe, the installed version follows the current user.
function resolveBundledBackendDataDir() {
  const portableExecutableDir = process.env.PORTABLE_EXECUTABLE_DIR

  if (portableExecutableDir) {
    return path.join(portableExecutableDir, 'data')
  }

  return app.getPath('userData')
}

// Stop the started backend process when the app exits.
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

// Start the packaged backend and wait for the health check to pass.
async function startBundledBackend() {
  const backendHost = process.env.BACKEND_HOST ?? '127.0.0.1'
  const preferredBackendPort = resolvePort(process.env.BACKEND_PORT, 9000)
  const selectedBackendPort = await findAvailablePort(backendHost, preferredBackendPort)
  const backendUrl = buildHttpUrl(backendHost, selectedBackendPort)
  const backendHealthUrl = buildHealthUrl(backendUrl)
  const executablePath = getBundledBackendExecutable()
  const backendDataDir = resolveBundledBackendDataDir()

  if (!fs.existsSync(executablePath)) {
    throw new Error(`Bundled backend executable not found at ${executablePath}`)
  }

  // The backend's actual port may shift if it is occupied; the final URL is injected into the frontend via preload.
  // The data directory is passed explicitly by Electron to prevent the backend from writing into the portable build's temporary extraction directory.
  backendProcess = spawn(
    executablePath,
    ['--host', backendHost, '--port', String(selectedBackendPort)],
    {
      stdio: 'ignore',
      windowsHide: true,
      env: {
        ...process.env,
        OC_CREATIVE_DATA_DIR: backendDataDir,
      },
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

// Select the appropriate runtime config based on development or packaged mode.
async function resolveRuntimeConfig() {
  if (!app.isPackaged) {
    // In dev mode the backend is not auto-started; its URL is provided by scripts/dev-desktop.mjs or an external service.
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

// Load the development frontend, falling back to an inline error page on failure.
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

// Determine whether a URL is an external HTTP(S) link.
function isHttpUrl(url) {
  return /^https?:/i.test(url)
}

// Determine whether a link still belongs to the current frontend origin.
function hasSameOrigin(url, rendererOrigin) {
  try {
    return new URL(url).origin === rendererOrigin
  } catch {
    return false
  }
}

// Hand external links to the system browser and limit in-app navigation scope.
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

// Create the main window and inject the backend URL into the renderer process.
async function createWindow(runtimeConfig) {
  const mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    icon: getAppIconPath(),
    backgroundColor: '#f6efe6',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      // The renderer process keeps the browser isolation model, exposing only the necessary config via preload.
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

// Clean up the backend child process before the process exits.
app.on('before-quit', () => {
  app.isQuitting = true
  stopBundledBackend()
})

ipcMain.handle(PDF_EXPORT_CHANNEL, async (event, payload) => {
  const parentWindow = BrowserWindow.fromWebContents(event.sender)
  return exportHtmlToPdf(parentWindow, payload)
})

// Once the app is ready, initialize the runtime config and open the first window.
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

// On non-macOS platforms, quit the app once all windows are closed.
app.on('window-all-closed', () => {
  stopBundledBackend()

  if (process.platform !== 'darwin') {
    app.quit()
  }
})
