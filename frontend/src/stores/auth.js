import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken, getUser, getLastSchoolId, setLastSchoolId } from '../utils/auth'

const TOKEN_KEY = 'teachhub_token'
const USER_KEY = 'teachhub_user'
const REFRESH_TOKEN_KEY = 'refresh_token'

/**
 * 认证状态 store：统一管理 token / 用户信息 / 角色判断 / 学校上下文，
 * 作为响应式视图层（组件内用），底层读写复用与 utils/auth.js 相同的
 * localStorage key，因此两者数据永远一致。
 *
 * 注意：本 store 的 setAuth/clearAuth 直接操作 localStorage（内联 key），
 * 不调用 utils 的 setAuth/clearAuth，避免「store→utils→_syncStore→store」递归。
 * 反向路径（utils.setAuth 被调用）由 utils 的 _syncStore 惰性同步回本 store。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const user = ref(getUser())

  // 角色判断（响应式）
  const isStudent = computed(() => user.value?.role === 'student')
  const isTeacher = computed(() =>
    ['teacher', 'school_admin', 'super_admin'].includes(user.value?.role)
  )
  const isPlatformAdmin = computed(() => user.value?.role === 'super_admin')
  const isSchoolAdmin = computed(() => user.value?.role === 'school_admin')

  // 当前用户所属学校（平台超管为 null）
  const schoolId = computed(() => user.value?.school_id ?? null)

  function setAuth(t, u, rt) {
    token.value = t
    user.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    // 仅显式传入时才更新 refresh token，避免误清已有值
    if (rt !== undefined && rt !== null) {
      localStorage.setItem(REFRESH_TOKEN_KEY, rt)
    }
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }

  return {
    token,
    user,
    isStudent,
    isTeacher,
    isPlatformAdmin,
    isSchoolAdmin,
    schoolId,
    setAuth,
    clearAuth,
    getLastSchoolId,
    setLastSchoolId,
  }
})
