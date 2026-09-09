import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearAuth, getToken } from '../utils/auth'
import router from '../router'

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
    const detail = error.response?.data?.detail || error.message || '请求失败'
    const url = error.config?.url || ''
    const isLoginRequest = url.includes('/api/auth/login')

    if (status === 401) {
      if (isLoginRequest) {
        // 登录接口返回 401 = 用户名或密码错误，展示真实原因，不做跳转/清空
        ElMessage.error(typeof detail === 'string' ? detail : '用户名或密码错误')
      } else {
        // 其他接口 401 = 会话过期
        clearAuth()
        ElMessage.error('登录已过期，请重新登录')
        const p = router.currentRoute.value.path
        const loginPath = p.startsWith('/m') ? '/m/login' : p.startsWith('/admin') ? '/admin/login' : '/login'
        router.push(loginPath)
      }
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '操作失败')
    }
    return Promise.reject(error)
  }
)

export default request
