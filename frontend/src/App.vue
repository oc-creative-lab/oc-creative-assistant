<script setup lang="ts">
/**
 * Vue 根组件。
 *
 * 多页架构重构后，根组件只渲染路由出口；具体页面（首页 / 聊天 / 项目库 /
 * 工作台）由 router 决定，业务状态分别由各页面与 Pinia store 管理。
 */
</script>

<template>
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>
