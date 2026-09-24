import axios from 'axios'
import { ElMessage } from 'element-plus'
import { showToast } from 'vant'
import { clearAuth, getToken, getRefreshToken, getUser, setAuth } from '../utils/auth'
import router from '../router'

// 归一化后端返回的 detail：可能是 string / 数组（Pydantic 校验）/ 对象，统一转为可读文案
function normalizeDetail(detail, fallback = '操作失败') {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const first = detail[0]
    if (first && typeof first === 'object' && first.msg) return first.msg
    if (first) return String(first)
  }
  if (detail && typeof detail === 'object') {
    // FastAPI 校验错误：{ "msg": "..." } 或 { detail: [...] }
    if (typeof detail.msg === 'string') return detail.msg
    if (Array.isArray(detail.detail)) return normalizeDetail(detail.detail, fallback)
  }
  return fallback
}

// 根据当前路由判断是否移动端，选择对应的 toast 组件。
//
// 请求配置可带 `_silent: true` 抑制提示，用于「最近导入记录」这类**只读附加信息**的
// 静默降级：拉取失败时不该在用户刚打开导入弹窗时弹一句「操作失败」，让人误以为导入出错。
// 注意：会话过期（401 且刷新失败）的提示**刻意不受该开关影响** —— 它伴随跳转登录页，
// 静默掉会让用户莫名其妙被踢出。
function notifyError(message, config) {
  if (config?._silent) return
  const path = router.currentRoute.value?.path || ''
  if (path.startsWith('/m')) {
    showToast({ message, position: 'top' })
  } else {
    ElMessage.error(message)
  }
}

// 会话过期后跳转对应端的登录页（保持既有路径规则不变）
function redirectToLogin() {
  const p = router.currentRoute.value.path
  const loginPath = p.startsWith('/m')
    ? '/m/login'
    : p.startsWith('/admin')
      ? '/admin/login'
      : '/login'
  router.push(loginPath)
}

const request = axios.create({
  baseURL: '',
  timeout: 30000,
})

// 静默刷新专用的「裸」实例：不挂任何拦截器，
// 避免刷新请求自身返回 401 时再次触发「401 → 刷新」的递归。
const refreshClient = axios.create({
  baseURL: '',
  timeout: 30000,
})

// ===== 并发去重：相同「方法+URL+参数」的重复请求，取消前一个 =====
// 场景：用户快速连续点击、搜索框输入抖动等导致的重复 GET/POST。
const pending = new Map()

function genKey(config) {
  const { method, url, params, data } = config
  return [method, url, JSON.stringify(params || {}), JSON.stringify(data || {})].join('&')
}

// 下载类请求（responseType: 'blob'）不随路由切换取消：
// 导出/模板下载通常需要较长时间，用户在等待期间切换菜单不应中断文件生成。
function isDownloadRequest(config) {
  return config?.responseType === 'blob'
}

function removePending(config) {
  const key = genKey(config)
  if (pending.has(key)) {
    pending.get(key).controller.abort()
    pending.delete(key)
  }
}

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  removePending(config)
  const controller = new AbortController()
  config.signal = controller.signal
  pending.set(genKey(config), { controller, keep: isDownloadRequest(config) })
  return config
})

// ===== 路由级取消：切换路由时撤销上一路由遗留的在途请求 =====
// 背景：翻页或切换菜单后，上一页面的慢请求仍会 resolve 并把数据写进已切换的视图，
// 造成脏数据竞态与内存泄漏。此处在导航开始时（beforeEach）统一撤销——
// 此时新页面尚未发起请求，不会误伤当前路由。
//
// 注意：在这里注册守卫而不是让 router/index.js 反向 import 本模块，
// 是为了避免 request ↔ router 循环依赖（本模块已 import router 用于错误提示与登录跳转）。

/**
 * 撤销所有在途请求（下载类请求除外）。
 * 被取消的请求不会弹出错误提示——响应拦截器已对 axios.isCancel 静默处理。
 *
 * @returns {number} 实际被取消的请求数
 */
export function abortAllPending() {
  let count = 0
  for (const [key, item] of pending) {
    if (item.keep) continue
    item.controller.abort()
    pending.delete(key)
    count += 1
  }
  return count
}

router.beforeEach(() => {
  abortAllPending()
  return true
})

// ===== 401 单飞（single-flight）静默刷新 =====
// 同一时刻只允许一个刷新在途；刷新期间并发到达的 401 请求共享同一个 Promise，
// 避免并发多次刷新把服务端的 refresh token 轮换打乱。
let refreshPromise = null

// 「会话过期」的后果（清空登录态 + 弹提示 + 跳登录页）只执行一次。
// 背景：刷新失败时，N 个并发 401 会共享同一个 refreshPromise，并在同一批微任务里各自进入
// 失败分支；refreshPromise 只去重了「刷新」这一动作，未去重其后果，于是会弹 N 次提示、
// 跳 N 次登录页（§3.6）。此处用一个一次性闸门把后果也收敛为「只做一次」。
let sessionExpiredNotified = false

/**
 * 会话过期兜底：清空登录态 → 提示 → 跳转对应端登录页。
 * 同一波并发 401 只执行一次（由 sessionExpiredNotified 闸门保证）。
 */
function handleSessionExpired() {
  if (sessionExpiredNotified) return
  sessionExpiredNotified = true
  clearAuth()
  notifyError('登录已过期，请重新登录')
  redirectToLogin()
}

/**
 * 复位「会话过期」闸门。
 * 任一请求成功（如重新登录）或刷新成功即代表已回到有效会话，下一次令牌过期仍应正常提示与跳转。
 */
function resetSessionExpiredFlag() {
  sessionExpiredNotified = false
}

/**
 * 触发一次静默刷新。
 *
 * 刷新成功 → 更新本地 access/refresh token，resolve 新的 access token；
 * 刷新失败（401 / 网络错误）或本地无 refresh token → reject。
 *
 * @returns {Promise<string>} 新的 access token
 */
function doSilentRefresh() {
  if (refreshPromise) return refreshPromise

  const rt = getRefreshToken()
  if (!rt) return Promise.reject(new Error('NO_REFRESH_TOKEN'))

  refreshPromise = refreshClient
    .post('/api/auth/refresh', { refresh_token: rt })
    .then((res) => res.data)
    .then((data) => {
      // 保留既有用户信息，仅替换两个 token；setAuth 内部会同步 Pinia store
      setAuth(data.token, getUser(), data.refresh_token)
      // 刷新成功 = 已回到有效会话，复位过期闸门
      resetSessionExpiredFlag()
      return data.token
    })
    .finally(() => {
      refreshPromise = null
    })

  return refreshPromise
}

request.interceptors.response.use(
  (response) => {
    removePending(response.config)
    // 仅当「新会话建立」类请求成功（登录 / 注册）才复位过期闸门：这类响应意味着已用新凭证
    // 回到有效会话，下一次令牌过期仍应正常提示与跳转。刻意**不**按「任意 2xx」复位，
    // 以免一波 401 处理途中被无关的成功响应提前解除闸门而重复提示/跳转。
    // （刷新令牌走 refreshClient 裸实例，不经此处，其复位在上面的 doSilentRefresh 内完成。）
    const url = response.config?.url || ''
    if (url.includes('/api/auth/login') || url.includes('/api/auth/register')) {
      resetSessionExpiredFlag()
    }
    return response.data
  },
  (error) => {
    if (error.config) removePending(error.config)
    const status = error.response?.status
    // 主动取消的请求不弹错误提示
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }
    // 网络层错误（超时、断网、跨域等），无 response
    if (!error.response) {
      notifyError(error.code === 'ECONNABORTED' ? '请求超时，请重试' : '网络异常，请检查网络连接', error.config)
      return Promise.reject(error)
    }
    const detail = error.response?.data?.detail
    const url = error.config?.url || ''
    const isLoginRequest = url.includes('/api/auth/login')

    if (status === 401) {
      if (isLoginRequest) {
        // 登录接口返回 401 = 用户名或密码错误，展示真实原因，不做跳转/清空
        notifyError(normalizeDetail(detail, '用户名或密码错误'), error.config)
      } else if (!error.config?._retried && getRefreshToken()) {
        // 其他接口 401 = access token 过期：尝试一次静默刷新后重放原请求
        const originalConfig = error.config
        return doSilentRefresh().then(
          (newToken) => {
            // 重放原请求（仅一次）：打标防重入，并清掉旧的并发去重占位
            originalConfig._retried = true
            removePending(originalConfig)
            originalConfig.headers = originalConfig.headers || {}
            originalConfig.headers.Authorization = `Bearer ${newToken}`
            return request(originalConfig)
          },
          () => {
            // 仅「刷新失败」才清空并跳登录；重放请求自身的错误按原样向上抛，不在此处理。
            // 提示与跳转交由 handleSessionExpired 收敛：并发的 401 只弹一次、只跳一次
            handleSessionExpired()
            return Promise.reject(error)
          }
        )
      } else {
        // 无 refresh token / 已重试过 = 会话过期；同样收敛为只提示、只跳转一次
        handleSessionExpired()
      }
    } else if (status === 403) {
      notifyError(normalizeDetail(detail, '无权限执行此操作'), error.config)
    } else if (status === 404) {
      notifyError(normalizeDetail(detail, '请求的资源不存在'), error.config)
    } else if (status === 423) {
      notifyError(normalizeDetail(detail, '账号已锁定，请稍后再试'), error.config)
    } else if (status === 429) {
      notifyError(normalizeDetail(detail, '操作过于频繁，请稍后再试'), error.config)
    } else {
      notifyError(normalizeDetail(detail, '操作失败'), error.config)
    }
    return Promise.reject(error)
  }
)

export default request
