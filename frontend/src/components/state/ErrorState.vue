<template>
  <div class="error-state-comp">
    <el-icon class="error-state-comp__icon" :size="imageSize">
      <WarningFilled />
    </el-icon>
    <p class="error-state-comp__desc">{{ description }}</p>
    <el-button class="error-state-comp__retry" type="primary" plain @click="onRetry">
      重试
    </el-button>
  </div>
</template>

<script setup>
/**
 * ErrorState — 统一错误状态占位组件。
 *
 * 用于数据加载失败时展示一致的错误视觉，并提供「重试」按钮，
 * 点击后向上抛出 `retry` 事件，由父组件决定重新请求逻辑。
 *
 * @prop {String} description 错误描述文案，默认「加载失败，请稍后重试」。
 * @prop {Number} imageSize   图标尺寸（px），默认 88。
 *
 * @emits {void} retry 点击「重试」按钮时触发。
 */
defineProps({
  /** 错误描述文案 */
  description: { type: String, default: '加载失败，请稍后重试' },
  /** 图标尺寸（px） */
  imageSize: { type: Number, default: 88 },
})

const emit = defineEmits(['retry'])

/**
 * 点击重试按钮，向上抛出 retry 事件。
 * @returns {void}
 */
function onRetry() {
  emit('retry')
}
</script>

<style scoped>
.error-state-comp {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 20px;
  color: var(--text-tertiary);
}

.error-state-comp__icon {
  color: var(--el-color-danger);
  line-height: 1;
}

.error-state-comp__desc {
  margin: 12px 0 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.error-state-comp__retry {
  margin-top: 16px;
}
</style>
