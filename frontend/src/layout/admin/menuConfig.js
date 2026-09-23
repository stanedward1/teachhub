/**
 * TeachHub 后台布局的菜单配置与派生逻辑。
 *
 * 本模块是纯数据 + 纯函数：不含任何 Vue 依赖，也不含样式，
 * 便于单独测试与复用（从 AdminLayout.vue 抽取，行为与原文件完全一致）。
 */

/**
 * 后台侧边栏菜单树。
 *
 * 结构约定：
 * - 叶子项：`{ index, label, icon?, need? }`，`index` 即路由路径，点击后由 el-menu 的 router 模式跳转。
 * - 分组项：`{ key, label, icon, children: [...] }`，`key` 作为 el-sub-menu 的 index。
 * - `need`：角色门控，`'admin'` 需学校管理员及以上，`'platform'` 需平台管理员；缺省表示对所有角色可见。
 *
 * 注意：菜单顺序、文案、图标与原 AdminLayout.vue 逐字保持一致。
 *
 * @type {Array<{index?: string, key?: string, label: string, icon?: string, need?: string, children?: Array<object>}>}
 */
export const MENU = [
  { index: '/admin/dashboard', label: '数据看板', icon: 'Odometer' },
  {
    key: 'hw',
    label: '上机作业管理',
    icon: 'Document',
    children: [{ index: '/admin/homework', label: '任务列表' }],
  },
  {
    key: 'workbench',
    label: '教师工作台',
    icon: 'Briefcase',
    children: [
      { index: '/admin/students', label: '学生管理' },
      { index: '/admin/scores', label: '成绩管理' },
      { index: '/admin/leaves', label: '考勤管理' },
      { index: '/admin/communications', label: '家校沟通' },
      { index: '/admin/resources', label: '资源管理' },
      { index: '/admin/exams', label: '试卷管理' },
      { index: '/admin/seats', label: '座位表' },
    ],
  },
  {
    key: 'classlog',
    label: '班级日志',
    icon: 'Notebook',
    children: [
      { index: '/admin/classrooms', label: '班级管理' },
      { index: '/admin/worklogs', label: '工作日志' },
      { index: '/admin/plans', label: '计划总结' },
      { index: '/admin/schedules', label: '课程表' },
      { index: '/admin/activities', label: '班级活动' },
      { index: '/admin/talks', label: '师生谈心' },
      { index: '/admin/return-records', label: '返校记录' },
      { index: '/admin/performances', label: '学生表现（含积分）' },
      { index: '/admin/student-comments', label: '学生评语' },
      { index: '/admin/reports', label: '班级报告' },
    ],
  },
  {
    key: 'system',
    label: '系统管理',
    icon: 'Setting',
    children: [
      { index: '/admin/users', label: '账号管理', need: 'admin' },
      { index: '/admin/schools', label: '学校管理', need: 'platform' },
      { index: '/admin/platform-settings', label: '平台设置', need: 'platform' },
      { index: '/admin/audit-logs', label: '审计日志', need: 'admin' },
      { index: '/admin/settings', label: '系统设置', need: 'admin' },
    ],
  },
]

/**
 * 路由路径 -> 页面标题（用于顶栏面包屑）。
 *
 * 注意：本映射刻意与路由表保持一致的原文件内容（23 条）。
 * 其中不含 `/admin/audit-logs`，该路径的面包屑会退化为 `['TeachHub']`，属既有行为，保持不变。
 *
 * @type {Record<string, string>}
 */
export const PAGE_TITLES = {
  '/admin/dashboard': '数据看板',
  '/admin/homework': '作业任务',
  '/admin/students': '学生管理',
  '/admin/classrooms': '班级管理',
  '/admin/scores': '成绩管理',
  '/admin/leaves': '考勤管理',
  '/admin/communications': '家校沟通',
  '/admin/resources': '资源管理',
  '/admin/exams': '试卷管理',
  '/admin/seats': '座位表',
  '/admin/worklogs': '工作日志',
  '/admin/plans': '计划总结',
  '/admin/schedules': '课程表',
  '/admin/activities': '班级活动',
  '/admin/talks': '师生谈心',
  '/admin/return-records': '返校记录',
  '/admin/performances': '学生表现（含积分）',
  '/admin/student-comments': '学生评语',
  '/admin/reports': '班级报告',
  '/admin/users': '账号管理',
  '/admin/schools': '学校管理',
  '/admin/settings': '系统设置',
  '/admin/platform-settings': '平台设置',
}

/**
 * 按角色过滤菜单树。
 *
 * 仅为分组项过滤其 `children`，分组外壳始终保留（与原模板中 el-sub-menu
 * 恒渲染、仅子项用 v-if 的行为一致）；叶子项无 `need` 时对所有角色可见。
 *
 * @param {Array<object>} menu 原始菜单树（通常为 {@link MENU}）。
 * @param {{ isAdmin?: boolean, isPlatform?: boolean }} roles 当前用户角色标志。
 * @returns {Array<object>} 过滤后的菜单树（不修改入参）。
 */
export function filterMenuByRole(menu, { isAdmin = false, isPlatform = false } = {}) {
  return menu.map((group) => {
    if (!group.children) return group
    const children = group.children.filter((leaf) => {
      if (leaf.need === 'admin') return isAdmin
      if (leaf.need === 'platform') return isPlatform
      return true
    })
    return { ...group, children }
  })
}

/**
 * 路由路径 -> 角色门控（由 {@link MENU} 的 `need` 派生）。
 *
 * **单一事实来源**：路由守卫按本函数拦截，侧边栏按 `need` 隐藏，二者永不走样。
 * 历史上二者各写一份，导致「菜单看不见、手输 URL 却能直达」的越权页面
 * （`/admin/users`、`/admin/schools`、`/admin/platform-settings`、`/admin/settings`、
 * `/admin/audit-logs`）。新增受控页面只需在 {@link MENU} 里写一次 `need`。
 *
 * @param {string} path 目标路由路径。
 * @returns {'admin'|'platform'|undefined} `'admin'` 需学校管理员及以上；
 *          `'platform'` 需平台超管；`undefined` 表示不做角色门控。
 */
export function routeNeed(path) {
  const target = normalizeRoutePath(path)
  for (const group of MENU) {
    for (const leaf of group.children || []) {
      if (normalizeRoutePath(leaf.index) === target) return leaf.need
    }
  }
  return undefined
}

/**
 * 归一化路由路径：去掉末尾斜杠并转小写。
 *
 * 必须归一化才能做「路径 → 门控」比对：vue-router 默认**大小写不敏感**且
 * `strict: false`，所以 `/admin/users/`、`/ADMIN/users` 都会匹配到同一个页面，
 * 而 `to.path` 会**原样保留**用户输入的形态。基于原始 `to.path` 做精确比对或前缀
 * 判断都会被绕开（实测后果）：
 * - `/admin/users/` → `routeNeed` 拿到带尾斜杠的串，精确匹配失败 → 返回 `undefined`
 *   → 门控整体放行（5 个受控页面全部可越权进入）；
 * - `/ADMIN/users` → 连守卫外层的 `startsWith('/admin')` 都失效，整段管理端分支被跳过
 *   → **连 `!hasToken || !isTeacher()` 登录拦截也一并跳过**。
 *
 * @param {string} path 原始路径（通常是 `to.path`）。
 * @returns {string} 归一化后的路径（至少为 `'/'`）。
 */
export function normalizeRoutePath(path) {
  return (path || '').replace(/\/+$/, '').toLowerCase() || '/'
}

/**
 * 由当前路由路径推导 el-menu 的激活项。
 *
 * 作业提交审阅等子页面（路径含 `/submissions`）归属「任务列表」。
 *
 * @param {string} path 当前路由路径。
 * @returns {string} 应高亮的菜单 index。
 */
export function resolveActiveMenu(path) {
  if (path.includes('/submissions')) return '/admin/homework'
  return path
}

/**
 * 由当前路由路径推导顶栏面包屑。
 *
 * 规则与原实现一致：
 * 1. 路径含 `/submissions` -> `['上机作业管理', '提交审阅']`；
 * 2. 命中 {@link PAGE_TITLES} -> `[标题]`；
 * 3. 否则 -> `['TeachHub']`。
 *
 * @param {string} path 当前路由路径。
 * @returns {string[]} 面包屑文本数组。
 */
export function resolveBreadcrumb(path) {
  if (path.includes('/submissions')) return ['上机作业管理', '提交审阅']
  const name = PAGE_TITLES[path]
  if (!name) return ['TeachHub']
  return [name]
}
