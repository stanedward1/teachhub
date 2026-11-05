/**
 * 移动端 Toast 的「注册式」出口。
 *
 * 为什么绕这一层：`api/request.js` 是所有页面共用的核心模块，如果它直接
 * `import { showToast } from 'vant'`（或动态 import 移动端封装），Vant 就会被
 * 绑进 request 所在的 chunk —— 结果 PC 端后台每个页面都要多下 34KB(gzip) 的
 * 移动端组件库。改成「移动端页面挂载时把自己的 Toast 注册进来」，request 就
 * 与 Vant 彻底解耦：PC 端永不加载，移动端也能保持原有的 Vant 提示样式。
 *
 * 未注册时（例如移动端组件尚未挂载）由调用方回退到 Element Plus 的 ElMessage，
 * 保证「请求出错」这件事在用户眼前仍然可见。
 */

/** @type {((message: string) => void) | null} */
let handler = null

/**
 * 注册移动端 Toast 实现（移动端布局 / 独立页面挂载时调用，可重复注册）。
 *
 * @param {(message: string) => void} fn
 */
export function registerMobileToast(fn) {
  handler = fn
}

/**
 * 取出当前已注册的移动端 Toast 实现；未注册时返回 null。
 *
 * @returns {((message: string) => void) | null}
 */
export function getMobileToast() {
  return handler
}
