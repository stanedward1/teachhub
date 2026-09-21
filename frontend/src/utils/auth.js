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

/** 记住上次选择的学校（登录页用） */
export function getLastSchoolId() {
  const v = localStorage.getItem(SCHOOL_KEY)
  return v ? Number(v) : null
}

export function setLastSchoolId(id) {
  if (id) localStorage.setItem(SCHOOL_KEY, String(id))
  else localStorage.removeItem(SCHOOL_KEY)
}
