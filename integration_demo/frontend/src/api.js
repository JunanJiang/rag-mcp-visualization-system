import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  withCredentials: true
})

export default api
