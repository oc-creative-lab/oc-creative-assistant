import { spawn } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// 优先使用显式指定的 Python，其次使用当前 conda 环境。
function resolvePythonCommand() {
  if (process.env.PYTHON_BIN) {
    return process.env.PYTHON_BIN
  }

  if (process.env.CONDA_PREFIX) {
    return path.join(
      process.env.CONDA_PREFIX,
      process.platform === 'win32' ? 'python.exe' : 'bin/python',
    )
  }

  return process.platform === 'win32' ? 'python.exe' : 'python3'
}

// 执行子命令，并在构建异常退出时立即失败。
function run(command, args, name) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: rootDir,
      stdio: 'inherit',
      shell: false,
      env: process.env,
    })

    child.on('error', (error) => {
      reject(new Error(`${name} failed to start: ${error.message}`))
    })

    child.on('exit', (code) => {
      if (code === 0) {
        resolve()
        return
      }

      reject(new Error(`${name} exited with code ${code ?? 1}`))
    })
  })
}

// 在调用 PyInstaller 前先确定 Python 可执行文件。
const pythonCommand = resolvePythonCommand()

// 将 FastAPI 后端打包为可分发目录。
await run(
  pythonCommand,
  [
    '-m',
    'PyInstaller',
    '--noconfirm',
    '--clean',
    '--onedir',
    '--name',
    'oc-creative-backend',
    '--distpath',
    'backend/dist',
    '--workpath',
    'backend/build',
    '--specpath',
    'backend',
    // PyInstaller 需要显式包含 uvicorn 的动态导入模块，否则可执行文件启动后会缺依赖。
    '--hidden-import',
    'uvicorn.logging',
    '--hidden-import',
    'uvicorn.loops.auto',
    '--hidden-import',
    'uvicorn.protocols.http.auto',
    '--hidden-import',
    'uvicorn.protocols.websockets.auto',
    '--hidden-import',
    'uvicorn.lifespan.on',
    'backend/serve.py',
  ],
  'backend build',
)
