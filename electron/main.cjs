const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { app, BrowserWindow, shell } = require('electron')

// 打包态由 Electron 主进程托管后端进程；开发态通常复用外部 uvicorn。
let backendProcess = null

// 规范化端口输入，不合法时回退到默认值。
function resolvePort(rawPort, fallback) {
  const parsedPort = Number(rawPort)

  if (Number.isInteger(parsedPort) && parsedPort > 0) {
    return parsedPort
  }

  return fallback
}

// 解析开发模式下要加载的前端入口地址。
function resolveRendererUrl() {
  const host = process.env.FRONTEND_DEV_HOST ?? '127.0.0.1'
  const port = process.env.FRONTEND_DEV_PORT ?? '5174'

  return process.env.ELECTRON_RENDERER_URL ?? `http://${host}:${port}`
}

// 根据主机和端口拼出本地 HTTP 基础地址。
function buildHttpUrl(host, port) {
  return `http://${host}:${port}`
}

// 根据后端基础地址拼出 health 接口地址。
function buildHealthUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/health`
}

// 探测本机某个端口当前是否可用。
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

// 从首选端口开始向后查找可用端口。
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

// 轮询等待某个 HTTP 地址可访问。
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

// 解析打包后前端入口文件在 resources 中的位置。
function getBundledFrontendEntry() {
  return path.join(process.resourcesPath, 'frontend', 'index.html')
}

// 解析打包后后端可执行文件在 resources 中的位置。
function getBundledBackendExecutable() {
  const executableName = process.platform === 'win32'
    ? 'oc-creative-backend.exe'
    : 'oc-creative-backend'

  return path.join(process.resourcesPath, 'backend', executableName)
}

// 解析打包态后端数据目录；portable 跟随 exe，安装版跟随当前用户。
function resolveBundledBackendDataDir() {
  const portableExecutableDir = process.env.PORTABLE_EXECUTABLE_DIR

  if (portableExecutableDir) {
    return path.join(portableExecutableDir, 'data')
  }

  return app.getPath('userData')
}

// 在应用退出时停止已启动的后端进程。
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

// 启动打包后的后端，并等待 health 检查通过。
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

  // 后端实际端口可能因占用而后移，最终地址会通过 preload 注入给前端。
  // 数据目录由 Electron 显式传入，避免后端写进 portable 的临时解包目录。
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

// 根据开发态或打包态选择对应的运行配置。
async function resolveRuntimeConfig() {
  if (!app.isPackaged) {
    // 开发态不自动拉起后端，由 scripts/dev-desktop.mjs 或外部服务提供地址。
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

// 加载开发态前端，失败时回退到内联错误页。
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

// 判断一个地址是否为外部 HTTP(S) 链接。
function isHttpUrl(url) {
  return /^https?:/i.test(url)
}

// 判断链接是否仍属于当前前端来源。
function hasSameOrigin(url, rendererOrigin) {
  try {
    return new URL(url).origin === rendererOrigin
  } catch {
    return false
  }
}

// 将外部链接交给系统浏览器，限制应用内导航范围。
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

// 创建主窗口，并把后端地址注入到渲染进程。
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
      // 渲染进程保持浏览器隔离模型，只通过 preload 暴露必要配置。
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

// 进程退出前先清理后端子进程。
app.on('before-quit', () => {
  app.isQuitting = true
  stopBundledBackend()
})

// 应用准备完成后初始化运行配置并打开首个窗口。
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

// 在非 macOS 平台上，窗口全部关闭后退出应用。
app.on('window-all-closed', () => {
  stopBundledBackend()

  if (process.platform !== 'darwin') {
    app.quit()
  }
})
