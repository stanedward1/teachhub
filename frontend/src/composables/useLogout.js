import { useRouter } from 'vue-router'
import { authApi } from '../api'
import { clearAuth, getRefreshToken } from '../utils/auth'

/**
 * 统一登出组合式函数：撤销服务端刷新令牌（尽力而为）后清理本地登录态并跳转。
 *
 * 背景：`access_token` 是无状态 JWT，服务端无法主动失效；只有刷新令牌落库
 * （`refresh_tokens` 表）可被撤销。若登出只清 localStorage 而不调
 * `POST /api/auth/logout`，该刷新令牌在服务端仍然有效（默认 30 天），
 * 一旦泄漏即可继续换取新的 access token。
 *
 * 设计取舍：
 * - **先取令牌再清理**：`clearAuth()` 会删掉 localStorage 中的刷新令牌，必须提前读出，
 *   否则撤销请求没有凭据；
 * - **不阻塞跳转**：撤销是「尽力而为」——失败（断网 / 服务端异常）不应把用户卡在已登录态，
 *   因此本地清理与跳转都不等待请求；SPA 路由跳转不会中断在途 XHR；
 * - **重复点击安全**：后端 `logout` 幂等（令牌不存在/已撤销仍返回 200）；
 *   `request.js` 的并发去重会取消同 key 的前一个在途请求，因此重复触发无副作用。
 *
 * 用法（须在 setup 中调用，内部依赖 useRouter）：
 *   const logout = useLogout()
 *   logout()                  // 跳默认登录页 /login
 *   logout('/admin/login')    // 跳指定登录页
 */
export function useLogout() {
  const router = useRouter()

  /**
   * 执行登出。
   *
   * @param {string} [redirectTo='/login'] 登出后跳转的登录页路径
   * @returns {Promise<unknown>} router.push 的结果
   */
  return function logout(redirectTo = '/login') {
    const refreshToken = getRefreshToken()
    clearAuth()
    if (refreshToken) {
      // fire-and-forget：撤销失败不阻塞登出（令牌将在服务端自然过期）
      authApi.logout(refreshToken).catch(() => {})
    }
    return router.push(redirectTo)
  }
}
