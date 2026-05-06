import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

// 仓库根目录（脚本位于 scripts/，上一级为项目根）。
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
// 后端本地环境变量文件；用于在不改系统环境的前提下固定打包用 Python（如 PYTHON_BIN）。
const backendEnvPath = path.join(rootDir, 'backend', '.env')

/**
 * 极简 .env 解析：只支持 KEY=VALUE，忽略空行与 # 注释。
 * 用于读取 backend/.env 中的 PYTHON_BIN / OC_BACKEND_PYTHON，与 dotenv 行为近似但不依赖额外包。
 *
 * @param {string} filePath
 * @returns {Record<string, string>}
 */
function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {}
  }

  const values = {}

  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim().replace(/^\uFEFF/, '')

    if (!line || line.startsWith('#') || !line.includes('=')) {
      continue
    }

    const [rawKey, ...rawValueParts] = line.split('=')
    const key = rawKey.trim().replace(/^\uFEFF/, '')
    const value = rawValueParts.join('=').trim().replace(/^['"]|['"]$/g, '')

    if (key) {
      values[key] = value
    }
  }

  return values
}

// 模块加载时读一次，供 resolvePythonCommand 使用（相对路径以 rootDir 为准）。
const backendEnv = parseEnvFile(backendEnvPath)

/**
 * 给定 conda / venv 等「环境根目录」前缀，返回该平台下的 python 可执行文件绝对路径。
 *
 * @param {string} prefix 例如 conda 的 env 目录或 miniconda 根下的 envs/oc
 */
function getPythonExecutable(prefix) {
  return path.join(
    prefix,
    process.platform === 'win32' ? 'python.exe' : 'bin/python',
  )
}

/**
 * 从 PATH 里各目录推断可能的 conda「安装根」（base 所在层），供查找 envs/<name>。
 * 启发式规则：识别 .../Library/bin、.../Scripts|bin、或路径下已有 envs/<OC_CONDA_ENV|oc>。
 *
 * @returns {string[]}
 */
function discoverCondaBasesFromPath() {
  const rawPath = process.env.PATH ?? process.env.Path ?? ''
  const candidates = []

  for (const entry of rawPath.split(path.delimiter)) {
    if (!entry) {
      continue
    }

    const normalizedEntry = path.resolve(entry)
    const entryName = path.basename(normalizedEntry).toLowerCase()
    const parentName = path.basename(path.dirname(normalizedEntry)).toLowerCase()

    if (entryName === 'bin' && parentName === 'library') {
      candidates.push(path.dirname(path.dirname(normalizedEntry)))
      continue
    }

    if (entryName === 'scripts' || entryName === 'bin') {
      candidates.push(path.dirname(normalizedEntry))
      continue
    }

    if (fs.existsSync(getPythonExecutable(path.join(normalizedEntry, 'envs', process.env.OC_CONDA_ENV ?? 'oc')))) {
      candidates.push(normalizedEntry)
    }
  }

  return candidates
}

/**
 * 在若干 conda 根候选下查找名为 OC_CONDA_ENV（默认 oc）的环境对应的 python。
 *
 * @returns {string | null} 找到则返回可执行文件路径，否则 null
 */
function resolveNamedCondaPython() {
  const envName = process.env.OC_CONDA_ENV ?? 'oc'
  const baseCandidates = []

  if (process.env.CONDA_EXE) {
    baseCandidates.push(path.resolve(path.dirname(process.env.CONDA_EXE), '..'))
  }

  baseCandidates.push(...discoverCondaBasesFromPath())

  const seen = new Set()

  for (const baseCandidate of baseCandidates) {
    const normalizedBase = path.resolve(baseCandidate)

    if (seen.has(normalizedBase)) {
      continue
    }

    seen.add(normalizedBase)

    const pythonPath = getPythonExecutable(path.join(normalizedBase, 'envs', envName))

    if (fs.existsSync(pythonPath)) {
      return pythonPath
    }
  }

  return null
}

/**
 * 决定调用 PyInstaller 时使用的 Python，优先级（高 → 低）：
 * 1. 进程环境 PYTHON_BIN / OC_BACKEND_PYTHON
 * 2. backend/.env 中同名键（便于本机固定解释器而不提交到 git）
 * 3. 已激活且非 base 的 conda 环境（CONDA_PREFIX）
 * 4. conda 下名为 OC_CONDA_ENV（默认 oc）的环境
 * 5. 仅 CONDA_PREFIX（含 base）
 * 6. 系统 PATH 上的 python.exe / python3
 *
 * 建议稳定打包时在 backend/.env 或环境中设置 PYTHON_BIN 指向项目 venv。
 *
 * @returns {string}
 */
function resolvePythonCommand() {
  if (process.env.PYTHON_BIN) {
    return process.env.PYTHON_BIN
  }

  if (process.env.OC_BACKEND_PYTHON) {
    return process.env.OC_BACKEND_PYTHON
  }

  if (backendEnv.PYTHON_BIN) {
    return backendEnv.PYTHON_BIN
  }

  if (backendEnv.OC_BACKEND_PYTHON) {
    return backendEnv.OC_BACKEND_PYTHON
  }

  if (process.env.CONDA_PREFIX && process.env.CONDA_DEFAULT_ENV && process.env.CONDA_DEFAULT_ENV !== 'base') {
    return getPythonExecutable(process.env.CONDA_PREFIX)
  }

  const namedCondaPython = resolveNamedCondaPython()

  if (namedCondaPython) {
    return namedCondaPython
  }

  if (process.env.CONDA_PREFIX) {
    return getPythonExecutable(process.env.CONDA_PREFIX)
  }

  return process.platform === 'win32' ? 'python.exe' : 'python3'
}

/**
 * 在仓库根目录下执行子进程；非 0 退出码视为构建失败并 reject。
 *
 * @param {string} command
 * @param {string[]} args
 * @param {string} name 仅用于错误信息
 */
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

const pythonCommand = resolvePythonCommand()
console.log(`[backend-build] Using Python: ${pythonCommand}`)

// --onedir：生成 oc-creative-backend.exe + _internal，供 Electron extraResources 拷贝。
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
    // ChromaDB 和 OpenAI SDK 都是运行时懒导入；这里显式收集，避免打包后向量库不可用。
    '--collect-all',
    'chromadb',
    '--hidden-import',
    'openai',
    'backend/serve.py',
  ],
  'backend build',
)
