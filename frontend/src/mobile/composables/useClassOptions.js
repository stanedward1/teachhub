import { ref } from 'vue'
import { studentApi } from '../../api'

/**
 * 移动端班级下拉选项共享逻辑（Checkin / AttendanceStats 两页同构）：
 * 拉取未毕业班级 → 组装 van-dropdown options → 默认选中第一个班级并触发首屏加载。
 * @param {() => Promise<void>|void} onSelected 默认班级就位后的首屏加载回调（各页注入自己的 load）
 */
export function useClassOptions(onSelected) {
  const classId = ref(null)
  const classOptions = ref([])

  async function loadClasses() {
    try {
      const res = await studentApi.classrooms({ graduated: 'false' })
      classOptions.value = (res.items || []).map((c) => ({ text: c.name, value: c.id }))
      if (classOptions.value.length && !classId.value) {
        classId.value = classOptions.value[0].value
        await onSelected()
      }
    } catch (e) {}
  }

  return { classId, classOptions, loadClasses }
}
