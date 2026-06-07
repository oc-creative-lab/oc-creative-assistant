<script setup lang="ts">
/**
 * Vue root component.
 *
 * After the multi-page refactor, the root component only renders the router
 * outlet; the actual pages (home / chat / library / workspace) are decided by
 * the router, and business state is managed by each page and the Pinia stores.
 */
</script>

<template>
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>
