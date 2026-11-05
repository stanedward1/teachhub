/**
 * 移动端 Vant **函数式组件**（Toast / Dialog）的统一出口。
 *
 * 为什么不直接 `import { showToast } from 'vant'`：
 * 那样会把整个 Vant 包纳入 PC 端的首屏依赖（约 78KB JS + 53KB CSS gzip），
 * 而 PC 端一个 Vant 组件都不用。改为从 `vant/es/<组件>` 子路径按需引入，
 * 这些模块只会被打进移动端页面（或本文件所在的小 chunk）。
 *
 * 模板里的 `<van-xxx>` 组件由 vite 的 VantResolver 自动按需引入，不经过本文件；
 * 本文件只负责**在 JS 里调用**的那几个 API。
 */
import { showSuccessToast, showToast } from 'vant/es/toast'
import { showConfirmDialog } from 'vant/es/dialog'

// 函数式组件不走模板解析，样式需要显式引入（各组件 style 已含 base 变量）
import 'vant/es/toast/style'
import 'vant/es/dialog/style'

export { showConfirmDialog, showSuccessToast, showToast }
