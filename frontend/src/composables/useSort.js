// 时间排序状态管理 — 支持 localStorage 持久化 + 响应式排序
//
// 🔴 分页列表用「服务端排序」（RBT-122）：把 `order` 放进查询参数、并在
// `watch(order, reload)` 里重取第 1 页，表格直接消费后端返回的顺序
// （见 Students.vue / Scores.vue 等 10 个页面的写法）。
// 只有**非分页**页面（Exams / Resources / Plans，一次性返回全量）才继续用本文件的
// `useSorted()` 做本地排序 —— 那种场景下「本地排序 === 全局排序」。
//
// 为什么不能对分页列表用 `useSorted()`：它排序的是**已经取回的 20 条**，
// 翻到第 1 页点「最早在前」只是把「最新 20 条」倒过来，第 2 页仍是最新的一条在前，
// 页与页之间顺序矛盾，用户会以为有一半记录丢了。
import { ref, watch } from 'vue'

const STORAGE_KEY = 'teachhub_sort_prefs'

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function savePrefs(prefs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
}

const prefs = loadPrefs()

/**
 * 取每条记录用于排序的时间键。
 * 优先使用业务日期字段（工作日志的 date、返校记录的 return_date），
 * 否则回退到 created_at，最后回退到空串（交由 id 兜底）。
 */
function timeKey(item) {
  return item?.date || item?.return_date || item?.created_at || ''
}

export function useSort(moduleKey) {
  const order = ref(prefs[moduleKey] || 'desc')

  watch(order, (val) => {
    prefs[moduleKey] = val
    savePrefs(prefs)
  })

  function sortItems(items) {
    if (!items || !items.length) return items
    const dir = order.value === 'asc' ? 1 : -1
    return [...items].sort((a, b) => {
      const ta = timeKey(a)
      const tb = timeKey(b)
      let cmp = String(ta).localeCompare(String(tb))
      if (cmp !== 0) return cmp * dir
      // 时间相同（例如批量写入时 created_at 同秒）时用 id 兜底，
      // 保证「最新在前/最早在前」切换必然产生可见变化。
      return (Number(a.id ?? 0) - Number(b.id ?? 0)) * dir
    })
  }

  /**
   * 返回响应式排序结果 — 当 order 或 sourceItems 变化时自动重新排序
   */
  function useSorted(sourceRef) {
    const sorted = ref([])
    watch(
      [sourceRef, order],
      () => {
        sorted.value = sortItems(sourceRef.value)
      },
      { immediate: true, deep: false }
    )
    return sorted
  }

  return { order, useSorted }
}
