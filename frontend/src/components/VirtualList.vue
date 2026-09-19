<template>
  <div ref="containerRef" class="virtual-list" :style="{ height: `${height}px` }">
    <!-- 上下 padding 撑起总高度，保证滚动条长度与真实数据一致 -->
    <div
      class="virtual-list__spacer"
      :style="{ paddingTop: `${padTop}px`, paddingBottom: `${padBottom}px` }"
    >
      <div
        v-for="row in visibleRows"
        :key="row.index"
        class="virtual-list__item"
        :style="{ height: `${itemHeight}px` }"
      >
        <slot :item="row.item" :index="row.index" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

/**
 * VirtualList — 固定行高长列表虚拟滚动（窗口化）组件。
 *
 * 仅渲染可视区域及其上下 buffer 范围内的行，用上下 padding 撑起总高，
 * 在渲染成千上万条数据时保持流畅，且 DOM 节点数量恒定。
 *
 * 说明：
 * - 行高必须固定（`itemHeight`），不做动态测量，保持简单可靠。
 * - 滚动事件通过 `requestAnimationFrame` 节流，避免高频重排。
 * - `items` 变化时自动将滚动位置重置到顶部。
 *
 * @prop {Array}  items      必填。列表数据源。
 * @prop {Number} itemHeight 必填。单行固定高度（px）。
 * @prop {Number} height     容器可视高度（px），默认 480。
 * @prop {Number} buffer     可视区上下各额外缓存的节点数，默认 4。
 *
 * @slot default 默认作用域插槽，作用域参数 `{ item, index }`。
 */
const props = defineProps({
  /** 列表数据源（必填） */
  items: {
    type: Array,
    required: true,
  },
  /** 单行固定高度（px，必填） */
  itemHeight: {
    type: Number,
    required: true,
  },
  /** 容器可视高度（px） */
  height: { type: Number, default: 480 },
  /** 可视区上下各额外缓存的节点数 */
  buffer: { type: Number, default: 4 },
})

/** 滚动容器 DOM 引用。 */
const containerRef = ref(null)

/** 当前滚动位置（px），仅在 rAF 回调中更新，作为渲染计算依据。 */
const scrollTop = ref(0)

/** rAF 节流标记，避免同一帧内重复计算。 */
let ticking = false

/**
 * 可视区域内可完整显示的行数（向上取整，含不足一行的高度）。
 * @returns {number}
 */
const visibleCount = computed(() => {
  const safeItemHeight = props.itemHeight > 0 ? props.itemHeight : 1
  return Math.ceil(props.height / safeItemHeight)
})

/**
 * 视口首行的理论索引。
 *
 * 已按「数据总长 - 可视行数」做上界收敛：浏览器一般会把 `scrollTop` 限制在
 * `scrollHeight - clientHeight` 之内，但数据变少或外部程序化写入 `scrollTop`
 * 时可能出现越界值；不收敛会让窗口落到数据之外，表现为整屏空白。
 *
 * @returns {number}
 */
const firstVisible = computed(() => {
  if (props.itemHeight <= 0) return 0
  const raw = Math.floor(scrollTop.value / props.itemHeight)
  const maxFirst = Math.max(0, props.items.length - visibleCount.value)
  return Math.min(raw, maxFirst)
})

/**
 * 起始渲染索引（含上下 buffer，且不小于 0）。
 * @returns {number}
 */
const startIndex = computed(() =>
  props.itemHeight <= 0 ? 0 : Math.max(0, firstVisible.value - props.buffer)
)

/**
 * 结束渲染索引（不含，且不超过数据长度）。
 * @returns {number}
 */
const endIndex = computed(() =>
  props.itemHeight <= 0
    ? props.items.length
    : Math.min(props.items.length, firstVisible.value + visibleCount.value + props.buffer)
)

/**
 * 当前需要渲染的行集合，携带原始索引以便插槽使用。
 * @returns {Array<{ item: any, index: number }>}
 */
const visibleRows = computed(() => {
  const start = startIndex.value
  const end = endIndex.value
  if (end <= start) return []
  return props.items.slice(start, end).map((item, i) => ({
    item,
    index: start + i,
  }))
})

/** 顶部占位高度，撑起已滚出可视区上方的行。 */
const padTop = computed(() => (props.itemHeight > 0 ? startIndex.value * props.itemHeight : 0))

/** 底部占位高度，撑起尚未进入可视区下方的行。 */
const padBottom = computed(() => {
  if (props.itemHeight <= 0) return 0
  const remain = props.items.length - endIndex.value
  return remain > 0 ? remain * props.itemHeight : 0
})

/**
 * 滚动处理：使用 requestAnimationFrame 节流，每帧至多更新一次渲染依据。
 * @returns {void}
 */
function onScroll() {
  if (ticking) return
  ticking = true
  window.requestAnimationFrame(() => {
    const el = containerRef.value
    if (el) {
      scrollTop.value = el.scrollTop
    }
    ticking = false
  })
}

/**
 * 将滚动位置重置到顶部（同步 DOM 与内部状态）。
 * @returns {void}
 */
function resetScroll() {
  scrollTop.value = 0
  const el = containerRef.value
  if (el && el.scrollTop !== 0) {
    el.scrollTop = 0
  }
}

// 数据源变化时重置滚动位置到顶部，避免出现空白或错位。
watch(() => props.items, resetScroll)

onMounted(() => {
  const el = containerRef.value
  if (el) {
    el.addEventListener('scroll', onScroll, { passive: true })
    scrollTop.value = el.scrollTop
  }
})

onBeforeUnmount(() => {
  const el = containerRef.value
  if (el) {
    el.removeEventListener('scroll', onScroll)
  }
})
</script>

<style scoped>
.virtual-list {
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.virtual-list__spacer {
  width: 100%;
}

.virtual-list__item {
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
</style>
