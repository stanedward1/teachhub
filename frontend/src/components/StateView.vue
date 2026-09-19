<template>
  <!-- 首屏加载：骨架屏（替代白屏 / 纯 loading 遮罩）；非表格页面可用 #skeleton 自定义 -->
  <slot v-if="showSkeleton" name="skeleton">
    <SkeletonTable :rows="rows" :columns="columns" :show-header="showHeader" />
  </slot>
  <!-- 首屏失败：错误态 + 重试 -->
  <ErrorState v-else-if="showError" :description="errorDescription" @retry="$emit('retry')" />
  <!-- 无数据：空态（默认插槽可放「新建」等操作按钮） -->
  <EmptyState v-else-if="showEmpty" :description="emptyDescription">
    <slot name="empty" />
  </EmptyState>
  <!-- 正常内容 -->
  <slot v-else />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import SkeletonTable from './SkeletonTable.vue'
import ErrorState from './ErrorState.vue'
import EmptyState from './EmptyState.vue'

/**
 * StateView — 列表「加载 / 错误 / 空 / 正常」四态统一接入层。
 *
 * 把 `SkeletonTable` + `ErrorState` + `EmptyState` 组合成单一开关，页面只需提供
 * `loading` / `error` / `empty` 三个布尔量即可获得一致的加载反馈，避免每个页面
 * 各写一套 `v-if` 判断。
 *
 * 时序约定（重要）：
 * - **骨架屏与错误态只在「首屏尚未成功展示过内容」时出现**。一旦成功渲染过内容，
 *   后续刷新（翻页、筛选、搜索等）不会再顶掉已有内容，仍由页面自身的
 *   `v-loading` 提供反馈 —— 否则带防抖搜索的页面会在每次输入时反复闪烁。
 * - 已有内容时若刷新失败，请由页面自行提示（全局拦截器已弹错误消息），本组件不接管。
 * - 页面的 `load()` 请固定写成「先 `loading = true`，再 `error = false`」，
 *   并在 `catch` 里置 `error = true`、`finally` 里置 `loading = false`。
 *
 * 用法：
 * ```vue
 * <StateView
 *   :loading="loading" :error="error" :empty="!items.length"
 *   :columns="6" empty-description="暂无学生" @retry="load"
 * >
 *   <template #empty><el-button type="primary" @click="openCreate">添加学生</el-button></template>
 *   <el-table :data="items" v-loading="loading">...</el-table>
 * </StateView>
 * ```
 *
 * @prop {Boolean} loading          数据是否加载中。
 * @prop {Boolean} error            首屏加载是否失败。
 * @prop {Boolean} empty            数据是否为空。
 * @prop {Number}  rows             骨架屏占位行数，默认 8。
 * @prop {Number}  columns          骨架屏占位列数，默认 4（建议与真实表格列数一致）。
 * @prop {Boolean} showHeader       骨架屏是否渲染表头占位，默认 true。
 * @prop {String}  emptyDescription 空态文案，默认「暂无数据」。
 * @prop {String}  errorDescription 错误态文案，默认「加载失败，请稍后重试」。
 *
 * @slot default 正常内容（通常是 `el-table`）。
 * @slot empty   空态下的操作按钮。
 *
 * @emits {void} retry 错误态点击「重试」时触发，由父组件重新取数。
 */
const props = defineProps({
  /** 数据是否加载中 */
  loading: { type: Boolean, default: false },
  /** 首屏加载是否失败 */
  error: { type: Boolean, default: false },
  /** 数据是否为空 */
  empty: { type: Boolean, default: false },
  /** 骨架屏占位行数 */
  rows: { type: Number, default: 8 },
  /** 骨架屏占位列数 */
  columns: { type: Number, default: 4 },
  /** 骨架屏是否渲染表头占位 */
  showHeader: { type: Boolean, default: true },
  /** 空态文案 */
  emptyDescription: { type: String, default: '暂无数据' },
  /** 错误态文案 */
  errorDescription: { type: String, default: '加载失败，请稍后重试' },
})

defineEmits(['retry'])

/** 是否已成功展示过一次内容，用于区分「首屏加载」与「后续刷新」。 */
const revealed = ref(false)

// 以 loading 的「下降沿」判定一次加载真正结束，且结束时无错误才置位。
// 不要写成 !loading && !error —— 父组件「先重置 error 再置 loading」的中间态、
// 或重试过程中的瞬时值，都会被那种写法误判为「已成功」，导致骨架屏提前消失。
watch(
  () => props.loading,
  (loading, prevLoading) => {
    if (prevLoading === true && loading === false && !props.error) {
      revealed.value = true
    }
  }
)

/** 骨架屏：仅首屏加载期间展示。 */
const showSkeleton = computed(() => props.loading && !revealed.value)

/** 错误态：仅首屏失败时展示；已有内容时的刷新失败不顶掉数据。 */
const showError = computed(() => props.error && !revealed.value)

/** 空态：加载中与错误态优先，避免相互叠加造成闪烁。 */
const showEmpty = computed(() => props.empty && !props.loading && !showError.value)
</script>
