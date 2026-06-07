import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const bundleDir = path.join(rootDir, 'electron', '.bundle')
const frontendDistDir = path.join(rootDir, 'frontend', 'dist')
const backendDistDir = path.join(rootDir, 'backend', 'dist', 'oc-creative-backend')

// Fail early if a required build artifact is missing.
function ensureExists(targetPath, label) {
  if (!fs.existsSync(targetPath)) {
    throw new Error(`${label} not found at ${targetPath}`)
  }
}

// First confirm that both the frontend and backend build artifacts exist.
ensureExists(frontendDistDir, 'frontend build output')
ensureExists(backendDistDir, 'backend build output')

// Recreate the temporary Electron packaging directory.
// This directory is a build artifact and can be safely cleared; do not put user data under electron/.bundle.
fs.rmSync(bundleDir, { recursive: true, force: true })
fs.mkdirSync(bundleDir, { recursive: true })

// Copy the frontend and backend artifacts into the Electron resources directory.
fs.cpSync(frontendDistDir, path.join(bundleDir, 'frontend'), { recursive: true })
fs.cpSync(backendDistDir, path.join(bundleDir, 'backend'), { recursive: true })
