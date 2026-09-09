import { customRef } from 'vue'

/**
 * 自定义 ref：对 set 做防抖（默认 300ms）。
 * - 立即更新内部值，.value 始终返回最新输入（el-input v-model 体验正常）
 * - 延迟 trigger 通知依赖（watch/computed/模板），实现"停顿后自动搜索"
 * - 与 el-input v-model 配合：用户看到实时输入，搜索请求在停顿 300ms 后发起
 * - 仍可配合 @keyup.enter / @clear 等即时触发：load() 读取 keyword.value 拿到最新值
 */
export function useDebouncedRef(value, delay = 300) {
  return customRef((track, trigger) => {
    let val = value
    let timer = null
    return {
      get() {
        track()
        return val
      },
      set(newValue) {
        val = newValue
        if (timer) clearTimeout(timer)
        timer = setTimeout(trigger, delay)
      }
    }
  })
}
