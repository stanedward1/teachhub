/**
 * Element Plus 图标的按需注册表。
 *
 * 背景：`@element-plus/icons-vue` 共 293 个图标，全量注册会让首屏多下载
 * 约 44KB（gzip）。本项目实际只用到 40 个，这里手工维护白名单。
 *
 * ⚠️ 新增图标（尤其在模板里写 `<Edit />`，或在 menuConfig / 看板配置里写
 * `icon: 'Edit'` 这类**字符串名**）必须同步加进下面的表 —— 字符串形式走
 * `<component :is="name" />`，解析不到全局组件时只会静默渲染空白。
 * 开发模式下 `assertMenuIcons()` 会对菜单树做一次校验并在控制台报错，
 * 但**模板里直接写的标签**无法自动校验，改模板时请一并检查本文件。
 */
import {
  ArrowDown,
  Back,
  Bell,
  Box,
  Briefcase,
  Calendar,
  ChatDotRound,
  ChatLineSquare,
  Clock,
  CollectionTag,
  Document,
  Expand,
  Fold,
  Folder,
  InfoFilled,
  Key,
  Loading,
  Lock,
  MagicStick,
  Menu,
  Notebook,
  Odometer,
  Phone,
  Right,
  School,
  Setting,
  SortDown,
  SortUp,
  Star,
  Switch,
  Tickets,
  Timer,
  TopRight,
  TrendCharts,
  Trophy,
  Upload,
  UploadFilled,
  User,
  View,
  WarningFilled,
} from '@element-plus/icons-vue'

const ICONS = {
  ArrowDown,
  Back,
  Bell,
  Box,
  Briefcase,
  Calendar,
  ChatDotRound,
  ChatLineSquare,
  Clock,
  CollectionTag,
  Document,
  Expand,
  Fold,
  Folder,
  InfoFilled,
  Key,
  Loading,
  Lock,
  MagicStick,
  Menu,
  Notebook,
  Odometer,
  Phone,
  Right,
  School,
  Setting,
  SortDown,
  SortUp,
  Star,
  Switch,
  Tickets,
  Timer,
  TopRight,
  TrendCharts,
  Trophy,
  Upload,
  UploadFilled,
  User,
  View,
  WarningFilled,
}

/**
 * 全局注册白名单内的图标。
 *
 * @param {import('vue').App} app
 */
export function registerElementIcons(app) {
  for (const [name, component] of Object.entries(ICONS)) {
    app.component(name, component)
  }
}

/**
 * 开发期校验：菜单树里出现的图标名是否都已注册。
 *
 * 只覆盖 `menuConfig.MENU`（字符串图标名的主要来源）；模板里直接写的标签
 * 无法在运行时枚举，靠改代码时的自觉 + 本文件白名单。
 */
export async function assertMenuIcons() {
  const { MENU } = await import('../layout/admin/menuConfig.js')
  const missing = new Set()
  const walk = (items) => {
    for (const item of items || []) {
      if (item.icon && !ICONS[item.icon]) missing.add(item.icon)
      if (item.children) walk(item.children)
    }
  }
  walk(MENU)
  if (missing.size) {
    console.error(
      '[icons] 菜单使用了未注册的图标：' + [...missing].join(', ') + '，请加入 src/plugins/icons.js'
    )
  }
}
