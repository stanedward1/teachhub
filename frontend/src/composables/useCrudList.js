/**
 * 列表页通用 CRUD 逻辑。
 *
 * 背景：`views/admin/` 下 20+ 个列表页各自手写同一套样板（约 40 行/页）——
 * 声明 page / pageSize / total / loading / error / items，再写 load() 的
 * try-catch-finally、onPage()、remove()（confirm → 调接口 → 提示 → 重新加载）。
 * 本模块把这些收敛为一处，页面只保留「筛选条件 + 参数拼装」的差异部分。
 *
 * 使用示例：
 * ```js
 * const {
 *   items, page, pageSize, total, loading, error, load, reload, onPage, remove,
 * } = useCrudList(studentApi.list, {
 *   removeApi: studentApi.remove,
 *   buildParams: () => ({ keyword: keyword.value, class_id: classId.value }),
 *   removeTip: (row) => `确定删除学生「${row.name}」吗？`,
 * })
 * watch(keyword, reload)   // 注意用 reload：搜索条件变化必须重置页码
 * ```
 *
 * 与 StateView 配合：`loading` / `error` / `empty` 直接透传给
 * `<StateView>`，`load` 作为 `@retry` 回调。
 */
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

export function useCrudList(listApi, options = {}) {
  const {
    /** 删除接口；不传则 remove() 不可用 */
    removeApi = null,
    /** () => 额外查询参数（筛选条件），每次 load 时调用 */
    buildParams = null,
    /** 是否在 onMounted 时自动加载一次 */
    immediate = false,
    /** 加载成功后的回调，可用于联动刷新图表等 */
    onLoaded = null,
    /** 删除确认文案 */
    removeTip = (row) => `确定删除「${row.name || row.id}」吗？`,
    /** 删除成功提示 */
    removeSuccessText = '删除成功',
    /** 初始每页条数 */
    defaultPageSize = 20,
  } = options

  const items = ref([])
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)
  const loading = ref(false)
  const error = ref(false)

  /**
   * 「最后一次请求胜出」序号。
   *
   * 每次 load() 自增一次并记住自己的序号（my）；响应回来时若 my 已不是当前序号，
   * 说明期间又发起了更新的请求，则**丢弃本次结果**，不写回 items / total / onLoaded。
   *
   * 为什么需要它：`api/request.js` 的同 key 并发去重 key 里**含 params**，
   * 于是「第 2 页」和「第 3 页」是两个不同的 key、互相不会取消。快速翻页或连续改筛选时，
   * 先发的慢响应会后到并覆盖新结果（§3.2）。序号保护与取消处理（§3.4）一起保证：
   * 只有最新一次请求能改动状态。
   */
  let seq = 0

  /**
   * 判断异常是否为「请求被主动取消」（路由切换 abortAllPending / 同 key 去重 abort）。
   *
   * @param {*} e 捕获到的异常
   * @returns {boolean} 是否属于取消
   */
  function isCanceled(e) {
    return (
      axios.isCancel?.(e) === true || e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError'
    )
  }

  async function load() {
    const my = ++seq
    loading.value = true
    error.value = false
    try {
      const params = {
        page: page.value,
        page_size: pageSize.value,
        ...(buildParams ? buildParams() : {}),
      }
      const res = await listApi(params)
      // 已有更新的请求发出：本次结果已过期，直接丢弃（不覆盖新数据）
      if (my !== seq) return
      items.value = res.items
      total.value = res.total
      if (onLoaded) onLoaded(res)
    } catch (e) {
      // 主动取消的请求不算错误，不改动 error（§3.4）
      if (isCanceled(e)) return
      // 被更新请求淘汰的旧请求失败时，也不得污染最新请求的错误态
      if (my !== seq) return
      error.value = true
    } finally {
      // 仅「最新一次」请求才允许结束 loading，避免旧请求的 finally 提前撤掉
      // 新请求仍在途中的 loading 骨架（§3.4）
      if (my === seq) loading.value = false
    }
  }

  /**
   * 重置到第 1 页后重新加载。
   * 搜索 / 筛选条件变化必须走这里 —— 否则在第 3 页改关键词会拿新条件查旧页码，
   * 得到错乱结果（原实现多处遗漏了重置页码）。
   */
  function reload() {
    page.value = 1
    load()
  }

  /** 翻页（分页组件 change 事件） */
  function onPage(p) {
    page.value = p
    load()
  }

  /** 每页条数变化：回到第 1 页 */
  function onSizeChange(s) {
    pageSize.value = s
    page.value = 1
    load()
  }

  /**
   * 删除单条：二次确认 → 调接口 → 提示 → 重新加载。
   * 用户取消确认时静默返回（Element Plus 的 confirm 在取消时会 reject）。
   *
   * 删除属于「结果集变小」，必须回到第 1 页（reload）而非停留在当前页（load）：
   * 在第 N 页删掉最后一条后，重查第 N 页只会得到空列表，用户会误以为整页都被删了（§3.3）。
   */
  async function remove(row) {
    if (!removeApi) {
      throw new Error('[useCrudList] 未提供 removeApi，无法删除')
    }
    try {
      await ElMessageBox.confirm(removeTip(row), '提示', { type: 'warning' })
    } catch (e) {
      return // 用户取消
    }
    await removeApi(row.id)
    ElMessage.success(removeSuccessText)
    reload()
  }

  if (immediate) {
    onMounted(load)
  }

  return {
    items,
    page,
    pageSize,
    total,
    loading,
    error,
    load,
    reload,
    onPage,
    onSizeChange,
    remove,
  }
}
