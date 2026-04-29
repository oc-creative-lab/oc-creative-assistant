import { spawn } from 'node:child_process'
import net from 'node:net'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// 规范化端口输入，不合法时回退到默认值。
function resolvePort(rawPort, fallback) {
  const parsedPort = Number(rawPort)

  if (Number.isInteger(parsedPort) && parsedPort > 0) {
    return parsedPort
  }

  return fallback
}

const frontendHost = process.env.FRONTEND_DEV_HOST ?? '127.0.0.1'
const frontendPort = resolvePort(process.env.FRONTEND_DEV_PORT, 5174)
const backendHost = process.env.BACKEND_HOST ?? '127.0.0.1'
const backendPort = resolvePort(process.env.BACKEND_PORT, 9000)
const backendReload = process.env.BACKEND_RELOAD !== 'false'
const backendUrlOverride = process.env.VITE_BACKEND_URL?.replace(/\/$/, '') ?? null
const rendererUrlOverride = process.env.ELECTRON_RENDERER_URL?.replace(/\/$/, '') ?? null
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const pythonCommand = process.env.PYTHON_BIN ?? 'python'

const children = []
let isShuttingDown = false

// 统一桌面启动器日志前缀，便于排查问题。
function log(message) {
  console.log(`[desktop] ${message}`)
}

// 根据主机和端口拼出本地 HTTP 基础地址。
function buildHttpUrl(host, port) {
  return `http://${host}:${port}`
}

// 根据基础地址拼出后端 health 接口地址。
function buildHealthUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/health`
}

// 启动子进程，并统一注册生命周期处理逻辑。
function spawnProcess(name, command, args, extraEnv = {}) {
  log(`Starting ${name}...`)
  // Windows 下 npm.cmd 需要 shell 才能正常解析，其他命令保持直接 spawn。
  const useShell = process.platform === 'win32' && command.toLowerCase().endsWith('.cmd')

  const child = spawn(command, args, {
    cwd: rootDir,
    env: {
      ...process.env,
      ...extraEnv,
    },
    stdio: 'inherit',
    shell: useShell,
  })

  children.push({ child, name })

  child.on('error', (error) => {
    if (isShuttingDown) {
      return
    }

    console.error(`[desktop] Failed to start ${name}:`, error)
    void shutdown(1)
  })

  child.on('exit', (code, signal) => {
    if (isShuttingDown) {
      return
    }

    const reason = signal ? `signal ${signal}` : `code ${code ?? 0}`

    if (name === 'electron') {
      log(`Electron exited with ${reason}. Shutting down the rest of the stack.`)
      void shutdown(code ?? 0)
      return
    }

    console.error(`[desktop] ${name} exited early with ${reason}.`)
    void shutdown(code ?? 1)
  })

  return child
}

// 轮询等待某个 HTTP 地址可访问。
async function waitForUrl(url, timeoutMs = 60_000, intervalMs = 500) {
  const startedAt = Date.now()

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url)

      if (response.ok) {
        return
      }
    } catch {
      // Keep polling until the dev server is ready or the timeout expires.
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  throw new Error(`Timed out waiting for ${url}`)
}

// 判断当前是否已有可复用的 Vite 开发服务。
async function isFrontendReady(baseUrl) {
  try {
    const response = await fetch(new URL('/__vite_ping', `${baseUrl}/`))
    return response.ok
  } catch {
    return false
  }
}

// 判断当前是否已有可复用的 FastAPI 后端服务。
async function isBackendReady(healthUrl) {
  try {
    const response = await fetch(healthUrl)

    if (!response.ok) {
      return false
    }

    const payload = await response.json()
    return payload?.status === 'ok' && payload?.service === 'backend'
  } catch {
    return false
  }
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

// 从配置 URL 中提取端口，不存在时回退到默认端口。
function readPortFromUrl(url, fallbackPort) {
  try {
    const parsedUrl = new URL(url)

    if (parsedUrl.port) {
      return Number(parsedUrl.port)
    }

    return fallbackPort
  } catch {
    return fallbackPort
  }
}

// 按平台差异安全结束子进程。
function terminateChild(child) {
  if (!child.pid) {
    return
  }

  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
    return
  }

  child.kill('SIGTERM')
}

// 按启动逆序关闭整套桌面开发进程。
async function shutdown(exitCode = 0) {
  if (isShuttingDown) {
    return
  }

  isShuttingDown = true

  for (const { child } of [...children].reverse()) {
    terminateChild(child)
  }

  setTimeout(() => {
    process.exit(exitCode)
  }, 200)
}

// 统筹本地开发态下 frontend、backend 和 Electron 的启动流程。
async function main() {
  let selectedBackendPort = backendPort
  let selectedBackendUrl = backendUrlOverride ?? buildHttpUrl(backendHost, selectedBackendPort)
  let selectedBackendHealthUrl = buildHealthUrl(selectedBackendUrl)
  let shouldStartBackend = false

  const backendRunning = await isBackendReady(selectedBackendHealthUrl)

  if (backendRunning) {
    // 已有后端可用时直接复用，避免重复启动导致端口冲突或数据文件争用。
    log(`Reusing existing backend at ${selectedBackendHealthUrl}.`)
  } else if (backendUrlOverride) {
    throw new Error(
      `Configured backend URL ${selectedBackendHealthUrl} is not reachable. Start it manually or remove VITE_BACKEND_URL.`,
    )
  } else {
    selectedBackendPort = await findAvailablePort(backendHost, backendPort)
    selectedBackendUrl = buildHttpUrl(backendHost, selectedBackendPort)
    selectedBackendHealthUrl = buildHealthUrl(selectedBackendUrl)
    shouldStartBackend = true

    if (selectedBackendPort !== backendPort) {
      log(`Backend port ${backendPort} is unavailable. Falling back to ${selectedBackendPort}.`)
    }
  }

  let selectedRendererUrl = rendererUrlOverride ?? buildHttpUrl(frontendHost, frontendPort)
  let selectedFrontendPort = readPortFromUrl(selectedRendererUrl, frontendPort)
  let shouldStartFrontend = false

  const frontendRunning = await isFrontendReady(selectedRendererUrl)

  if (frontendRunning) {
    // 复用正在运行的 Vite，能保留开发者当前页面状态和 HMR 会话。
    log(`Reusing existing frontend at ${selectedRendererUrl}.`)
  } else if (rendererUrlOverride) {
    throw new Error(
      `Configured renderer URL ${selectedRendererUrl} is not reachable. Start it manually or remove ELECTRON_RENDERER_URL.`,
    )
  } else {
    selectedFrontendPort = await findAvailablePort(frontendHost, frontendPort)
    selectedRendererUrl = buildHttpUrl(frontendHost, selectedFrontendPort)
    shouldStartFrontend = true

    if (selectedFrontendPort !== frontendPort) {
      log(`Frontend port ${frontendPort} is unavailable. Falling back to ${selectedFrontendPort}.`)
    }
  }

  if (shouldStartFrontend) {
    spawnProcess(
      'frontend',
      npmCommand,
      ['--prefix', 'frontend', 'run', 'dev', '--', '--configLoader', 'native'],
      {
        FRONTEND_DEV_HOST: frontendHost,
        FRONTEND_DEV_PORT: String(selectedFrontendPort),
        VITE_BACKEND_URL: selectedBackendUrl,
      },
    )
  }

  const backendArgs = [
    '-m',
    'uvicorn',
    'main:app',
    '--host',
    backendHost,
    '--port',
    String(selectedBackendPort),
    '--app-dir',
    'backend',
  ]

  if (backendReload) {
    backendArgs.splice(3, 0, '--reload')
  }

  if (shouldStartBackend) {
    spawnProcess('backend', pythonCommand, backendArgs)
  }

  if (shouldStartFrontend) {
    log(`Waiting for frontend dev server at ${selectedRendererUrl}...`)
    await waitForUrl(selectedRendererUrl)
  }

  if (shouldStartBackend) {
    log(`Waiting for backend health endpoint at ${selectedBackendHealthUrl}...`)
    await waitForUrl(selectedBackendHealthUrl)
  }

  log('Desktop dependencies are ready. Launching Electron.')

  spawnProcess('electron', npmCommand, ['--prefix', 'electron', 'run', 'dev'], {
    BACKEND_BASE_URL: selectedBackendUrl,
    ELECTRON_RENDERER_URL: selectedRendererUrl,
    FRONTEND_DEV_HOST: frontendHost,
    FRONTEND_DEV_PORT: String(selectedFrontendPort),
  })
}

// 收到终止信号时，统一关闭所有子进程。
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    void shutdown(0)
  })
}

// 将未处理的 Promise 异常统一导入关闭流程。
process.on('unhandledRejection', (error) => {
  console.error('[desktop] Unhandled rejection:', error)
  void shutdown(1)
})

// 将未捕获异常统一导入关闭流程。
process.on('uncaughtException', (error) => {
  console.error('[desktop] Uncaught exception:', error)
  void shutdown(1)
})

// 启动桌面开发调度器，并清晰输出启动错误。
main().catch((error) => {
  console.error('[desktop] Failed to boot the desktop dev flow:', error)
  void shutdown(1)
})
