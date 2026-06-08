const cache = new Map<string, string>()

function cacheKey(projectId: string, nodeId: string): string {
  return `${projectId}:${nodeId}`
}

export function useCharacterAvatarCache() {
  function get(projectId: string, nodeId: string): string {
    return cache.get(cacheKey(projectId, nodeId)) ?? ''
  }

  function set(projectId: string, nodeId: string, avatar: string): void {
    if (avatar) {
      cache.set(cacheKey(projectId, nodeId), avatar)
    } else {
      cache.delete(cacheKey(projectId, nodeId))
    }
  }

  function snapshot(projectId: string): Record<string, string> {
    const prefix = `${projectId}:`
    const next: Record<string, string> = {}
    for (const [key, avatar] of cache.entries()) {
      if (!key.startsWith(prefix)) continue
      next[key.slice(prefix.length)] = avatar
    }
    return next
  }

  return { get, set, snapshot }
}
