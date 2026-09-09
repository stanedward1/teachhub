import { ref } from 'vue'

/**
 * 防重复提交组合式函数：包装异步提交函数，提交期间返回 submitting=true，
 * 并在提交完成前忽略重复调用，避免用户快速双击导致重复创建/提交。
 *
 * 用法：
 *   const { submitting, run } = useSubmit(apiCreateStudent)
 *   await run(form)   // submitting 会自动置 true，结束后置 false
 *
 * 按钮上绑定 :loading="submitting" 即可获得加载态 + 防重复提交。
 */
export function useSubmit(fn) {
  const submitting = ref(false)

  async function run(...args) {
    if (submitting.value) return undefined
    submitting.value = true
    try {
      return await fn(...args)
    } finally {
      submitting.value = false
    }
  }

  return { submitting, run }
}
