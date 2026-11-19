import { ref } from 'vue'
import { studentApi } from '../../api'

/**
 * 移动端班级下拉选项共享逻辑（Checkin / AttendanceStats 两页同构）：
 * 拉取未毕业班级 → 组装 van-dropdown options → 默认选中第一个班级并触发首屏加载。
 *
 * 失败语义（VUE-16 的共享根因，见 `.workbuddy/scan3/frontend.md` FE3-08）：
 * 本函数原先在 `catch` 里把失败**降级成空数组**且不暴露任何错误标志 —— 于是
 * 「新老师确实没带班」与「`/api/classrooms` 挂了」在页面上完全同形，两个调用页
 * 都只能显示「请先选择班级」，而且没有重试入口。
 * 现在改为暴露 `classesError` + `reloadClasses`，由调用方渲染横幅/重试按钮；
 * **失败时刻意不清空 `classOptions`** —— 有旧数据时保留，避免一次网络抖动把下拉
 * 清空、连带让已选中的 `classId` 失效。
 *
 * @param {() => Promise<void>|void} onSelected 默认班级就位后的首屏加载回调（各页注入自己的 load）
 */
export function useClassOptions(onSelected) {
  const classId = ref(null)
  const classOptions = ref([])
  /**
   * 班级列表是否加载失败。
   *
   * 必须与「教师真的没带班」区分开：请求失败时 options 也是空数组，若不单独标记，
   * 页面会断言「你还没有带班班级」——把网络故障说成业务事实，且没有重试入口。
   */
  const classesError = ref(false)
  /**
   * 班级列表是否在请求中。
   *
   * 初值取 `true`：本 composable 的约定就是「组件挂载时立刻 `onMounted(loadClasses)`」，
   * 而 `onMounted` 晚于首帧渲染 —— 初值 false 会让首帧闪一下「你还没有带班班级」。
   */
  const classesLoading = ref(true)

  async function loadClasses() {
    classesLoading.value = true
    classesError.value = false
    try {
      const res = await studentApi.classrooms({ graduated: 'false' })
      classOptions.value = (res.items || []).map((c) => ({ text: c.name, value: c.id }))
      if (classOptions.value.length && !classId.value) {
        classId.value = classOptions.value[0].value
        await onSelected()
      }
    } catch (e) {
      // 已由全局拦截器提示（request.js 在 /m* 路由走 showToast）；
      // 这里只标记「列表没拿到」，让调用方能把失败与「真的没带班」区分开并给重试入口。
      classesError.value = true
    } finally {
      classesLoading.value = false
    }
  }

  return {
    classId,
    classOptions,
    classesError,
    classesLoading,
    loadClasses,
    /** 语义化别名：失败横幅/空态上的「重试」用它，强调这是「重新拉列表」而非首次加载。 */
    reloadClasses: loadClasses,
  }
}
