import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const bundleDir = path.join(rootDir, 'electron', '.bundle')
const frontendDistDir = path.join(rootDir, 'frontend', 'dist')
const backendDistDir = path.join(rootDir, 'backend', 'dist', 'oc-creative-backend')

// 若缺少必要构建产物则提前失败。
function ensureExists(targetPath, label) {
  if (!fs.existsSync(targetPath)) {
    throw new Error(`${label} not found at ${targetPath}`)
  }
}

// 先确认前端和后端构建产物都已存在。
ensureExists(frontendDistDir, 'frontend build output')
ensureExists(backendDistDir, 'backend build output')

// 重新创建临时 Electron 打包目录。
fs.rmSync(bundleDir, { recursive: true, force: true })
fs.mkdirSync(bundleDir, { recursive: true })

// 将前端和后端产物复制到 Electron resources 目录。
fs.cpSync(frontendDistDir, path.join(bundleDir, 'frontend'), { recursive: true })
fs.cpSync(backendDistDir, path.join(bundleDir, 'backend'), { recursive: true })
