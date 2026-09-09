import { createApp } from 'vue'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'

// 命令式 API（ElMessage / ElMessageBox）样式需手动引入（按需组件样式由 resolver 处理）
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

const app = createApp(App)

// 只注册项目实际用到的图标（避免把 @element-plus/icons-vue 全量打入主包）
const USED_ICONS = [
  'ArrowDown', 'Back', 'Briefcase', 'ChatDotRound', 'Clock', 'CollectionTag',
  'Document', 'Key', 'Loading', 'Lock', 'Menu', 'Monitor', 'Notebook', 'Odometer',
  'Reading', 'Right', 'Setting', 'SortDown', 'SortUp', 'Star', 'Switch',
  'UploadFilled', 'User',
]
for (const name of USED_ICONS) {
  const comp = ElementPlusIconsVue[name]
  if (comp) app.component(name, comp)
}

app.use(router)
app.mount('#app')
