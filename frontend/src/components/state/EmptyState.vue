<template>
  <div class="empty-state-comp">
    <el-icon class="empty-state-comp__icon" :size="imageSize">
      <Box />
    </el-icon>
    <p class="empty-state-comp__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state-comp__actions">
      <slot />
    </div>
  </div>
</template>

<script setup>
/**
 * EmptyState — 统一空状态占位组件。
 *
 * 用于列表 / 表格 / 卡片在无数据时展示一致的占位视觉，
 * 支持通过默认插槽追加操作按钮（如「新建」）。
 *
 * @prop {String} description 空态描述文案，默认「暂无数据」。
 * @prop {Number} imageSize   图标尺寸（px），默认 88。
 *
 * @slot default 可选。放置操作按钮等自定义内容。
 */
defineProps({
  /** 空态描述文案 */
  description: { type: String, default: '暂无数据' },
  /** 图标尺寸（px） */
  imageSize: { type: Number, default: 88 },
})
</script>

<style scoped>
.empty-state-comp {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 20px;
  color: var(--text-tertiary);
}

.empty-state-comp__icon {
  color: var(--text-placeholder);
  line-height: 1;
}

.empty-state-comp__desc {
  margin: 12px 0 0;
  font-size: 14px;
  color: var(--text-tertiary);
}

.empty-state-comp__actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
