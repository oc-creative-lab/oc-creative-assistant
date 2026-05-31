<script setup lang="ts">
import { nodeTypeOptions } from '../../utils/nodeFactory'
import type { CreativeNodeType } from '../../types/node'

/**
 * 画布右键菜单（second_revision 改点 A）。
 *
 * menuType='blank'：在鼠标位置新建节点（按当前 sub-graph 允许的类型）。
 * menuType='node'：编辑详情 / 复制 / 删除 / 复制到对话框。
 * position:fixed + z-index:9999，盖过节点与画布。
 */
defineProps<{
  show: boolean
  x: number
  y: number
  menuType: 'blank' | 'node'
  createTypes: CreativeNodeType[]
}>()
const emit = defineEmits<{
  create: [type: CreativeNodeType]
  edit: []
  duplicate: []
  remove: []
  quote: []
  close: []
}>()

function labelOf(type: CreativeNodeType): string {
  return ({character:'Character',worldbuilding:'Worldbuilding',plot:'Story node',idea:'Idea',research:'Research',structure:'Structure'} as Record<string,string>)[type] ?? type
}
</script>

<template>
  <div v-if="show" class="ctx-menu" :style="{ left: `${x}px`, top: `${y}px` }">
    <template v-if="menuType === 'blank'">
      <button
        v-for="type in createTypes"
        :key="type"
        type="button"
        class="ctx-menu__item"
        @click="emit('create', type)"
      >
        + New {{ labelOf(type) }}
      </button>
    </template>
    <template v-else>
      <button type="button" class="ctx-menu__item" @click="emit('edit')">Edit</button>
      <button type="button" class="ctx-menu__item" @click="emit('duplicate')">Duplicate</button>
      <button type="button" class="ctx-menu__item" @click="emit('quote')">Copy to composer</button>
      <button type="button" class="ctx-menu__item ctx-menu__item--danger" @click="emit('remove')">
        Delete
      </button>
    </template>
  </div>
</template>

<style scoped>
.ctx-menu {
  position: fixed;
  z-index: 9999;
  min-width: 140px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
  display: flex;
  flex-direction: column;
}
.ctx-menu__item {
  text-align: left;
  padding: 8px 12px;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text, #333);
}
.ctx-menu__item:hover {
  background: #f3f4f6;
}
.ctx-menu__item--danger {
  color: #dc2626;
}
</style>
