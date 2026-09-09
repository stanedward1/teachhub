import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

// 全量引入 Element Plus（项目几乎用到全部核心组件，按需引入在 dev 模式会
// 反复触发依赖预构建重跑导致卡顿，全量引入可让 vite 启动时一次性预构建完成）
app.use(ElementPlus)

// 全量引入 Vant（移动端 /m 共用同一入口）
app.use(Vant)

// 全量注册图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(router)
app.mount('#app')
