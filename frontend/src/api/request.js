import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearAuth, getToken } from '../utils/auth'
import router from '../router'

const request = axios.create({
  baseURL: '',
  timeout: 30000
})

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
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
