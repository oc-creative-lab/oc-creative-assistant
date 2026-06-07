import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

// Repository root (the script lives in scripts/; its parent is the project root).
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
// Backend local environment variable file; used to pin the Python used for packaging (e.g. PYTHON_BIN) without changing the system environment.
const backendEnvPath = path.join(rootDir, 'backend', '.env')

/**
 * Minimal .env parser: supports only KEY=VALUE, ignoring blank lines and # comments.
 * Used to read PYTHON_BIN / OC_BACKEND_PYTHON from backend/.env; behaves similarly to dotenv but without depending on an extra package.
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

// Read once at module load for use by resolvePythonCommand (relative paths are resolved against rootDir).
const backendEnv = parseEnvFile(backendEnvPath)

/**
 * Given an "environment root directory" prefix such as a conda / venv, return the absolute path to the python executable for this platform.
 *
 * @param {string} prefix e.g. a conda env directory or envs/oc under the miniconda root
 */
function getPythonExecutable(prefix) {
  return path.join(
    prefix,
    process.platform === 'win32' ? 'python.exe' : 'bin/python',
  )
}

/**
 * Infer possible conda "install roots" (the level where base resides) from the directories in PATH, for locating envs/<name>.
 * Heuristics: recognize .../Library/bin, .../Scripts|bin, or a path that already contains envs/<OC_CONDA_ENV|oc>.
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
 * Search the candidate conda roots for the python belonging to the environment named OC_CONDA_ENV (default oc).
 *
 * @returns {string | null} the executable path if found, otherwise null
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
 * Decide which Python to use when invoking PyInstaller, in priority order (high -> low):
 * 1. Process environment PYTHON_BIN / OC_BACKEND_PYTHON
 * 2. The same-named keys in backend/.env (convenient for pinning the interpreter locally without committing to git)
 * 3. An activated, non-base conda environment (CONDA_PREFIX)
 * 4. The conda environment named OC_CONDA_ENV (default oc)
 * 5. CONDA_PREFIX alone (including base)
 * 6. python.exe / python3 on the system PATH
 *
 * For stable packaging it is recommended to set PYTHON_BIN in backend/.env or the environment, pointing to the project venv.
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
 * Run a child process in the repository root; a non-zero exit code is treated as a build failure and rejects.
 *
 * @param {string} command
 * @param {string[]} args
 * @param {string} name used only for error messages
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

// --onedir: produce oc-creative-backend.exe + _internal for Electron extraResources to copy.
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
    // PyInstaller needs uvicorn's dynamically imported modules to be included explicitly, otherwise the executable will be missing dependencies at startup.
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
    // ChromaDB and the OpenAI SDK are both lazily imported at runtime; collect them explicitly here so the vector store is not unavailable after packaging.
    '--collect-all',
    'chromadb',
    '--hidden-import',
    'openai',
    'backend/serve.py',
  ],
  'backend build',
)
