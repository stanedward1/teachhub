// 时间排序状态管理 — 支持 localStorage 持久化 + 响应式排序
import { ref, watch } from 'vue'

const STORAGE_KEY = 'teachhub_sort_prefs'

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
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
