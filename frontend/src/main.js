import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus 的组件**与样式**都改为按需（见 vite.config.js 的 Components 插件）。
// 下面三个是「在 JS 里直接调用」的函数式组件 / 指令，不经过模板解析，
// 按需插件覆盖不到，必须在这里补样式（每个 css.mjs 已自带 base 等依赖）。
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import { ElLoading } from 'element-plus'
import App from './App.vue'
import router from './router'
import './style.css'
import { assertMenuIcons, registerElementIcons } from './plugins/icons'

const app = createApp(App)

// 状态管理：Pinia（authStore 统一登录态，替代 utils/auth.js 的散落 localStorage 读取）
app.use(createPinia())

// 图标按需注册（白名单见 src/plugins/icons.js —— 新增图标务必同步）
registerElementIcons(app)
if (import.meta.env.DEV) assertMenuIcons()

// `v-loading` 指令显式注册（全项目 35 处使用）：不依赖按需插件对指令的解析，
// 少一条「插件升级后指令悄悄失效」的隐患。
app.directive('loading', ElLoading.directive)

// Vant 移到移动端按需加载（组件走 VantResolver，函数式 API 走 mobile/vant-fn.js）：
// PC 端首屏不再下载整个 Vant（约 78KB JS + 53KB CSS gzip）。

app.use(router)
app.mount('#app')
