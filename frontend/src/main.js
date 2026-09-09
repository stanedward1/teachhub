import { createApp } from 'vue'
import {
  ArrowDown, Back, Bell, Briefcase, Calendar, ChatDotRound, Clock, CollectionTag,
  Document, Expand, Folder, Fold, Key, Loading, Lock, Menu, Monitor, Notebook,
  Odometer, Reading, Right, School, Setting, SortDown, SortUp, Star, Switch,
  Tickets, Upload, UploadFilled, User,
} from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'

// 命令式 API（ElMessage / ElMessageBox）样式需手动引入（按需组件样式由 resolver 处理）
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

const app = createApp(App)

// 具名导入 + 只注册项目实际用到的图标（tree-shaking 生效，避免把整个图标库打进主包）
const ICONS = {
  ArrowDown, Back, Bell, Briefcase, Calendar, ChatDotRound, Clock, CollectionTag,
  Document, Expand, Folder, Fold, Key, Loading, Lock, Menu, Monitor, Notebook,
  Odometer, Reading, Right, School, Setting, SortDown, SortUp, Star, Switch,
  Tickets, Upload, UploadFilled, User,
}
for (const [name, comp] of Object.entries(ICONS)) {
  app.component(name, comp)
}

app.use(router)
app.mount('#app')
