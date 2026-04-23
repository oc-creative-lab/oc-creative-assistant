import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const bundleDir = path.join(rootDir, 'electron', '.bundle')
const frontendDistDir = path.join(rootDir, 'frontend', 'dist')
const backendDistDir = path.join(rootDir, 'backend', 'dist', 'oc-creative-backend')

function ensureExists(targetPath, label) {
  if (!fs.existsSync(targetPath)) {
    throw new Error(`${label} not found at ${targetPath}`)
  }
}

ensureExists(frontendDistDir, 'frontend build output')
ensureExists(backendDistDir, 'backend build output')

fs.rmSync(bundleDir, { recursive: true, force: true })
fs.mkdirSync(bundleDir, { recursive: true })

fs.cpSync(frontendDistDir, path.join(bundleDir, 'frontend'), { recursive: true })
fs.cpSync(backendDistDir, path.join(bundleDir, 'backend'), { recursive: true })
