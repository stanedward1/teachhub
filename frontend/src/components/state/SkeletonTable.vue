<template>
  <div class="skeleton-table">
    <el-skeleton animated>
      <template #template>
        <!-- 表头占位 -->
        <div v-if="showHeader" class="skeleton-table__row skeleton-table__row--head">
          <div v-for="c in columns" :key="`head-${c}`" class="skeleton-table__cell">
            <el-skeleton-item variant="text" style="width: 60%" />
          </div>
        </div>

        <!-- 数据行占位 -->
        <div v-for="r in rows" :key="`row-${r}`" class="skeleton-table__row">
          <div v-for="c in columns" :key="`cell-${r}-${c}`" class="skeleton-table__cell">
            <el-skeleton-item variant="text" :style="{ width: cellWidth(r, c) }" />
          </div>
        </div>
      </template>
    </el-skeleton>
  </div>
</template>

<script setup>
/**
 * SkeletonTable — 表格骨架屏组件。
 *
 * 以「表头 + 若干行占位」的形式模拟表格加载状态，行高固定，
 * 避免加载完成前后的布局跳动（CLS）。
 *
 * @prop {Number}  rows       占位数据行数，默认 8。
 * @prop {Number}  columns    占位列数，默认 4。
 * @prop {Boolean} showHeader 是否显示表头占位行，默认 true。
 */
defineProps({
  /** 占位数据行数 */
  rows: { type: Number, default: 8 },
  /** 占位列数 */
  columns: { type: Number, default: 4 },
  /** 是否显示表头占位行 */
  showHeader: { type: Boolean, default: true },
})

/** 列宽候选比例，保证每格宽度错落有致且渲染稳定（不随数据变化）。 */
const WIDTH_PRESETS = ['80%', '60%', '70%', '50%', '65%', '45%']

/**
 * 计算单元格占位条宽度，依据行列索引取模选取固定比例，
 * 使各格宽度错落、视觉更接近真实表格。
 *
 * @param {number} row    行索引（从 1 开始）
 * @param {number} col    列索引（从 1 开始）
 * @returns {string} 宽度百分比字符串，如 '60%'
 */
function cellWidth(row, col) {
  const index = (row + col) % WIDTH_PRESETS.length
  return WIDTH_PRESETS[index]
}
</script>

<style scoped>
.skeleton-table {
  width: 100%;
}

.skeleton-table__row {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 44px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-light);
}

.skeleton-table__row:last-child {
  border-bottom: none;
}

.skeleton-table__row--head {
  background: var(--bg-page);
}

.skeleton-table__cell {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  align-items: center;
}
</style>
