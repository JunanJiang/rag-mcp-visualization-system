/**
 * 统一 API 请求模块
 * - axios 实例自动附带 JWT token
 * - 提供 authFetch 用于 SSE 流式请求
 * - 401 响应自动跳转登录页
 */
import axios from 'axios'
import router from './router'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
  paramsSerializer: {
    indexes: null
  }
})

// 请求拦截器：自动附带 JWT token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动跳转登录
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

/**
 * 带 JWT token 的 fetch（用于 SSE 流式请求）
 * - 自动附带 JWT token
 * - 401 响应自动跳转登录页（与 axios 拦截器行为一致）
 */
export async function authFetch(url, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const resp = await fetch(url, { ...options, headers })
  if (resp.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }
  return resp
}

export default api
