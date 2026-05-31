import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * 应用路由骨架（阶段 0）。
 *
 * 目标产品形态：首页(HomeLanding) → 聊天入口 / 项目库 → ChatWorkspace / Workspace。
 * 阶段 0 只搭占位路由保证可跳转；HomeLanding / ChatEntry / ProjectLibrary 的
 * 正式实现在阶段 2，WorkspaceShell + 三视图在阶段 3。
 *
 * 过渡期约束（复用优先、不破坏现有功能）：
 * - `/workspace/:projectId` 暂时直接复用现有的 `AppShell.vue`，让旧的单画布工作台
 *   在重构期间仍可用；阶段 3 再替换为 `WorkspaceShell.vue` + 子路由三视图。
 *
 * 桌面端用 hash history：Electron 以 file:// 加载打包后的 index.html，
 * hash 模式不依赖服务端路由，刷新不会 404。
 */
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeLanding.vue'),
    },
    {
      path: '/chat',
      name: 'chat-entry',
      component: () => import('../views/ChatEntry.vue'),
    },
    {
      path: '/chat/:projectId',
      name: 'chat-workspace',
      component: () => import('../views/ChatWorkspace.vue'),
      props: true,
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('../views/ProjectLibrary.vue'),
    },
    {
      path: '/workspace/:projectId',
      component: () => import('../views/WorkspaceShell.vue'),
      props: true,
      children: [
        { path: '', redirect: { name: 'workspace-overview' } },
        {
          path: 'overview',
          name: 'workspace-overview',
          component: () => import('../views/workspace/ProjectOverview.vue'),
        },
        {
          path: 'plot',
          name: 'workspace-plot',
          component: () => import('../views/workspace/PlotCanvas.vue'),
        },
        {
          path: 'characters',
          name: 'workspace-characters',
          component: () => import('../views/workspace/CharacterCardList.vue'),
        },
        {
          path: 'characters/:charId',
          name: 'workspace-character-detail',
          component: () => import('../views/workspace/CharacterCardDetail.vue'),
          props: true,
        },
        {
          path: 'world',
          name: 'workspace-world',
          component: () => import('../views/workspace/WorldCanvas.vue'),
        },
      ],
    },
    {
      // 旧单画布工作台保留可达（不删除现有 AppShell），便于过渡期对照。
      path: '/legacy',
      name: 'legacy-appshell',
      component: () => import('../components/workspace/AppShell.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})
