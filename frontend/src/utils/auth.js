import { getActivePinia } from 'pinia'

const TOKEN_KEY = 'teachhub_token'
const USER_KEY = 'teachhub_user'
const SCHOOL_KEY = 'teachhub_school_id'
// 刷新令牌：与 access token 分开持久化，供 401 静默刷新使用
const REFRESH_TOKEN_KEY = 'refresh_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/** 读取持久化的刷新令牌（无则返回 null） */
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

/**
 * 写入登录态。
 *
 * @param {string} token        access token
 * @param {object} user         用户信息
 * @param {string} [refreshToken] 刷新令牌；仅当显式传入（非 null/undefined）时才更新，
 *                                以免既有调用方（改密 / 头像等）误清除已有的 refresh token。
 */
export function setAuth(token, user, refreshToken) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  if (refreshToken !== undefined && refreshToken !== null) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
  _syncStore()
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  _syncStore()
}

/**
 * 仅清除持久化的刷新令牌（保留 access token 与用户信息）。
 *
 * 用于「新会话已建立、但服务端未回传 refresh_token」的场景（如学生自助注册）：
 * 此时若不清除，localStorage 会残留上一个账号的 refresh token，access token 过期后
 * 会拿旧账号身份去刷新（§3.6），必须显式清除以避免身份串号。
 */
export function clearRefreshToken() {
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/**
 * 在写完 localStorage 后同步已激活的 Pinia store 的 ref（若存在），
 * 使组件内的响应式登录态（useAuthStore）与 localStorage 保持一致。
 *
 * 用 getActivePinia() 惰性检测 + 动态 import，规避与 stores/auth.js 的循环依赖。
 * store 的 setAuth/clearAuth 内部直接操作 localStorage（不调用本模块的 setAuth），
 * 因此不会形成「store→utils→store」的递归。
 */
function _syncStore() {
  const pinia = getActivePinia()
  if (!pinia) return
  import('../stores/auth').then(({ useAuthStore }) => {
    const store = useAuthStore(pinia)
    const token = getToken()
    const user = getUser()
    if (store.token !== token) store.token = token
    if (store.user !== user) store.user = user
  })
}

export function isStudent() {
  return getUser()?.role === 'student'
}

/** 后台角色：教师 / 学校管理员 / 平台超管 */
export function isTeacher() {
  return ['teacher', 'school_admin', 'super_admin'].includes(getUser()?.role)
}

/** 平台超管：跨学校管理 */
export function isPlatformAdmin() {
  return getUser()?.role === 'super_admin'
}

/** 学校管理员：本校最高管理员 */
export function isSchoolAdmin() {
  return getUser()?.role === 'school_admin'
}

/**
 * 班主任：教师角色且至少担任一个班的班主任。
 *
 * 依赖登录响应里的 `head_classes`（由后端 `auth_service.public_user` 提供，
 * 与 `/admin/audit-logs` 的可见范围同源）。**仅用于前端展示层判断**
 * （是否展示审计日志菜单/是否放行该路由）；真正的数据边界由后端按班级过滤，
 * 科任老师直接调接口仍会拿到 403。
 */
export function isTeacherHead() {
  const headClasses = getUser()?.head_classes
  return Array.isArray(headClasses) && headClasses.length > 0
}

/** 记住上次选择的学校（登录页用） */
export function getLastSchoolId() {
  const v = localStorage.getItem(SCHOOL_KEY)
  return v ? Number(v) : null
}

export function setLastSchoolId(id) {
  if (id) localStorage.setItem(SCHOOL_KEY, String(id))
  else localStorage.removeItem(SCHOOL_KEY)
}
