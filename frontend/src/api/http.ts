/* 桌面态优先使用 preload 注入的后端地址, 浏览器开发态回退到 Vite 环境变量。 */
export const backendBaseUrl = (
window.ocDesktop?.config.backendUrl ||
import.meta.env.VITE_BACKEND_URL ||
'http://127.0.0.1:9000'
).replace(/\/$/, '')

/**
 * 统一请求后端 JSON 接口。
 *
 * Args:
 *   path: 以 `/api` 开头的后端路径。
 *   init: fetch 请求配置。
 *
 * Returns:
 *   反序列化后的响应体。
 *
 * Throws:
 *   Error: 当后端返回非 2xx 状态时抛出。
 */
export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
const response = await fetch(`${backendBaseUrl}${path}`, {
    headers: {
    'Content-Type': 'application/json',
    ...(init?.headers ?? {}),
    },
    ...init,
})

if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
}

return (await response.json()) as T
}