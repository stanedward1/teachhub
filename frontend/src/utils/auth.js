const TOKEN_KEY = 'teachhub_token'
const USER_KEY = 'teachhub_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
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

/** 当前用户所属学校（平台超管为 null） */
export function getSchoolId() {
  return getUser()?.school_id ?? null
}

const SCHOOL_KEY = 'teachhub_school_id'

/** 记住上次选择的学校（登录页用） */
export function getLastSchoolId() {
  const v = localStorage.getItem(SCHOOL_KEY)
  return v ? Number(v) : null
}

export function setLastSchoolId(id) {
  if (id) localStorage.setItem(SCHOOL_KEY, String(id))
  else localStorage.removeItem(SCHOOL_KEY)
}
