import axios from 'axios'
import { ElMessage } from 'element-plus'
import { showToast } from 'vant'
import { clearAuth, getToken } from '../utils/auth'
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

// 根据当前路由判断是否移动端，选择对应的 toast 组件
function notifyError(message) {
  const path = router.currentRoute.value?.path || ''
  if (path.startsWith('/m')) {
    showToast({ message, position: 'top' })
  } else {
    ElMessage.error(message)
  }
}

const request = axios.create({
  baseURL: '',
  timeout: 30000
})

// ===== 并发去重：相同「方法+URL+参数」的重复请求，取消前一个 =====
// 场景：用户快速连续点击、搜索框输入抖动等导致的重复 GET/POST。
const pending = new Map()

function genKey(config) {
  const { method, url, params, data } = config
  return [method, url, JSON.stringify(params || {}), JSON.stringify(data || {})].join('&')
}

function removePending(config) {
  const key = genKey(config)
  if (pending.has(key)) {
    pending.get(key).abort()
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
  pending.set(genKey(config), controller)
  return config
})

request.interceptors.response.use(
  (response) => {
    removePending(response.config)
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
      notifyError(error.code === 'ECONNABORTED' ? '请求超时，请重试' : '网络异常，请检查网络连接')
      return Promise.reject(error)
    }
    const detail = error.response?.data?.detail
    const url = error.config?.url || ''
    const isLoginRequest = url.includes('/api/auth/login')

    if (status === 401) {
      if (isLoginRequest) {
        // 登录接口返回 401 = 用户名或密码错误，展示真实原因，不做跳转/清空
        notifyError(normalizeDetail(detail, '用户名或密码错误'))
      } else {
        // 其他接口 401 = 会话过期
        clearAuth()
        notifyError('登录已过期，请重新登录')
        const p = router.currentRoute.value.path
        const loginPath = p.startsWith('/m') ? '/m/login' : p.startsWith('/admin') ? '/admin/login' : '/login'
        router.push(loginPath)
      }
    } else if (status === 403) {
      notifyError(normalizeDetail(detail, '无权限执行此操作'))
    } else if (status === 404) {
      notifyError(normalizeDetail(detail, '请求的资源不存在'))
    } else if (status === 423) {
      notifyError(normalizeDetail(detail, '账号已锁定，请稍后再试'))
    } else if (status === 429) {
      notifyError(normalizeDetail(detail, '操作过于频繁，请稍后再试'))
    } else {
      notifyError(normalizeDetail(detail, '操作失败'))
    }
    return Promise.reject(error)
  }
)

export default request
