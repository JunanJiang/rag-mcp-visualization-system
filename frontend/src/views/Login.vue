<template>

  <div class="login-page">

    <div class="login-grid-bg"></div>

    <div class="login-wrapper">

      <div class="login-card">

        <!-- Header -->

        <div class="login-header">

          <div class="login-logo">

            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">

              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>

              <polyline points="7.5 4.21 12 6.81 16.5 4.21"/>

              <polyline points="7.5 19.79 7.5 14.6 3 12"/>

              <polyline points="21 12 16.5 14.6 16.5 19.79"/>

              <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>

              <line x1="12" y1="22.08" x2="12" y2="12"/>

            </svg>

          </div>

          <h1 class="login-title">SimuReport</h1>

          <p class="login-desc">智能仿真报告生成系统</p>

        </div>



        <!-- Tab switcher -->

        <div class="tab-switcher">

          <button

            :class="['tab-btn', { active: activeTab === 'login' }]"

            @click="activeTab = 'login'"

          >登录</button>

          <button

            :class="['tab-btn', { active: activeTab === 'register' }]"

            @click="activeTab = 'register'"

          >注册</button>

        </div>



        <!-- Login Form -->

        <div v-show="activeTab === 'login'" class="form-area">

          <el-form

            ref="loginFormRef"

            :model="loginForm"

            :rules="loginRules"

            @submit.prevent="handleLogin"

            hide-required-asterisk

          >

            <div class="field">

              <label class="field-label">用户名</label>

              <el-form-item prop="username">

                <el-input

                  v-model="loginForm.username"

                  placeholder="请输入用户名"

                  size="large"

                />

              </el-form-item>

            </div>

            <div class="field">

              <label class="field-label">密码</label>

              <el-form-item prop="password">

                <el-input

                  v-model="loginForm.password"

                  type="password"

                  placeholder="请输入密码"

                  size="large"

                  show-password

                  @keyup.enter="handleLogin"

                />

              </el-form-item>

            </div>

            <el-form-item>

              <button

                type="button"

                class="submit-btn"

                :disabled="loading"

                @click="handleLogin"

              >

                <span v-if="loading" class="btn-spinner"></span>

                <span>{{ loading ? '登录中...' : '登 录' }}</span>

              </button>

            </el-form-item>

          </el-form>

        </div>



        <!-- Register Form -->

        <div v-show="activeTab === 'register'" class="form-area">

          <el-form

            ref="registerFormRef"

            :model="registerForm"

            :rules="registerRules"

            @submit.prevent="handleRegister"

            hide-required-asterisk

          >

            <div class="field">

              <label class="field-label">用户名</label>

              <el-form-item prop="username">

                <el-input

                  v-model="registerForm.username"

                  placeholder="至少3个字符"

                  size="large"

                />

              </el-form-item>

            </div>

            <div class="field">

              <label class="field-label">显示名称</label>

              <el-form-item prop="displayName">

                <el-input

                  v-model="registerForm.displayName"

                  placeholder="选填"

                  size="large"

                />

              </el-form-item>

            </div>

            <div class="field">

              <label class="field-label">密码</label>

              <el-form-item prop="password">

                <el-input

                  v-model="registerForm.password"

                  type="password"

                  placeholder="至少6个字符"

                  size="large"

                  show-password

                />

              </el-form-item>

            </div>

            <div class="field">

              <label class="field-label">确认密码</label>

              <el-form-item prop="confirmPassword">

                <el-input

                  v-model="registerForm.confirmPassword"

                  type="password"

                  placeholder="再次输入密码"

                  size="large"

                  show-password

                  @keyup.enter="handleRegister"

                />

              </el-form-item>

            </div>

            <el-form-item>

              <button

                type="button"

                class="submit-btn"

                :disabled="loading"

                @click="handleRegister"

              >

                <span v-if="loading" class="btn-spinner"></span>

                <span>{{ loading ? '注册中...' : '注 册' }}</span>

              </button>

            </el-form-item>

          </el-form>

        </div>



        <p class="login-footer">

          继续使用即表示同意 <a href="#">服务条款</a>

        </p>

      </div>

    </div>

  </div>

</template>



<script setup>

import { ref, reactive } from 'vue'

import { useRouter } from 'vue-router'

import { ElMessage } from 'element-plus'

import api from '../api'



const router = useRouter()

const activeTab = ref('login')

const loading = ref(false)

const loginFormRef = ref(null)

const registerFormRef = ref(null)



const loginForm = reactive({

  username: '',

  password: ''

})



const registerForm = reactive({

  username: '',

  displayName: '',

  password: '',

  confirmPassword: ''

})



const loginRules = {

  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],

  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]

}



const validateConfirmPassword = (rule, value, callback) => {

  if (value !== registerForm.password) {

    callback(new Error('两次输入的密码不一致'))

  } else {

    callback()

  }

}



const registerRules = {

  username: [

    { required: true, message: '请输入用户名', trigger: 'blur' },

    { min: 3, message: '用户名至少3个字符', trigger: 'blur' }

  ],

  password: [

    { required: true, message: '请输入密码', trigger: 'blur' },

    { min: 6, message: '密码至少6个字符', trigger: 'blur' }

  ],

  confirmPassword: [

    { required: true, message: '请确认密码', trigger: 'blur' },

    { validator: validateConfirmPassword, trigger: 'blur' }

  ]

}



async function handleLogin() {

  if (!loginFormRef.value) return

  const valid = await loginFormRef.value.validate().catch(() => false)

  if (!valid) return



  loading.value = true

  try {

    const res = await api.post('/auth/login', {

      username: loginForm.username,

      password: loginForm.password

    })

    if (res.data.success) {

      localStorage.setItem('token', res.data.token)

      localStorage.setItem('user', JSON.stringify(res.data.user))

      ElMessage.success('登录成功')

      router.push('/v2')

    } else {

      ElMessage.error(res.data.error || '登录失败')

    }

  } catch (err) {

    const msg = err.response?.data?.error || '网络错误'

    ElMessage.error(msg)

  } finally {

    loading.value = false

  }

}



async function handleRegister() {

  if (!registerFormRef.value) return

  const valid = await registerFormRef.value.validate().catch(() => false)

  if (!valid) return



  loading.value = true

  try {

    const res = await api.post('/auth/register', {

      username: registerForm.username,

      password: registerForm.password,

      displayName: registerForm.displayName

    })

    if (res.data.success) {

      localStorage.setItem('token', res.data.token)

      localStorage.setItem('user', JSON.stringify(res.data.user))

      ElMessage.success('注册成功')

      router.push('/v2')

    } else {

      ElMessage.error(res.data.error || '注册失败')

    }

  } catch (err) {

    const msg = err.response?.data?.error || '网络错误'

    ElMessage.error(msg)

  } finally {

    loading.value = false

  }

}

</script>



<style scoped>

/* ── Page ── */

.login-page {

  position: relative;

  min-height: 100vh;

  display: flex;

  align-items: center;

  justify-content: center;

  background: #fafafa;

  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;

}



.login-grid-bg {

  position: absolute;

  inset: 0;

  background-image:

    linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),

    linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px);

  background-size: 32px 32px;

  pointer-events: none;

}



/* ── Wrapper ── */

.login-wrapper {

  position: relative;

  z-index: 1;

  width: 100%;

  max-width: 400px;

  padding: 16px;

  box-sizing: border-box;

}



/* ── Card ── */

.login-card {

  background: #fff;

  border-radius: 12px;

  border: 1px solid #e5e7eb;

  padding: 40px 32px 32px;

  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);

}



/* ── Header ── */

.login-header {

  text-align: center;

  margin-bottom: 32px;

}



.login-logo {

  width: 48px;

  height: 48px;

  margin: 0 auto 16px;

  border-radius: 12px;

  background: #0f172a;

  color: #fff;

  display: flex;

  align-items: center;

  justify-content: center;

}



.login-title {

  font-size: 22px;

  font-weight: 700;

  color: #0f172a;

  margin: 0 0 6px;

  letter-spacing: -0.02em;

}



.login-desc {

  font-size: 14px;

  color: #94a3b8;

  margin: 0;

}



/* ── Tab Switcher ── */

.tab-switcher {

  display: flex;

  gap: 4px;

  background: #f1f5f9;

  border-radius: 8px;

  padding: 4px;

  margin-bottom: 28px;

}



.tab-btn {

  flex: 1;

  padding: 8px 0;

  border: none;

  border-radius: 6px;

  background: transparent;

  color: #64748b;

  font-size: 14px;

  font-weight: 500;

  cursor: pointer;

  transition: all 0.2s ease;

}



.tab-btn.active {

  background: #fff;

  color: #0f172a;

  box-shadow: 0 1px 3px rgba(0,0,0,0.08);

}



.tab-btn:hover:not(.active) {

  color: #334155;

}



/* ── Form ── */

.form-area {

  width: 100%;

}



.field {

  margin-bottom: 20px;

}



.field-label {

  display: block;

  font-size: 13px;

  font-weight: 600;

  color: #1e293b;

  margin-bottom: 6px;

}



/* ── Element Plus overrides ── */

.form-area :deep(.el-form-item) {

  margin-bottom: 0;

}



.form-area :deep(.el-form-item__content) {

  width: 100%;

}



.form-area :deep(.el-input__wrapper) {

  box-shadow: 0 0 0 1px #e2e8f0 inset !important;

  border-radius: 8px;

  padding: 0 12px;

  transition: border-color 0.2s, box-shadow 0.2s;

  width: 100%;

}



.form-area :deep(.el-input__wrapper:hover) {

  box-shadow: 0 0 0 1px #cbd5e1 inset !important;

}



.form-area :deep(.el-input__wrapper.is-focus) {

  box-shadow: 0 0 0 2px #0f172a inset !important;

}



.form-area :deep(.el-input__inner) {

  color: #0f172a;

  height: 40px;

  font-size: 14px;

}



.form-area :deep(.el-input__inner::placeholder) {

  color: #94a3b8;

}



.form-area :deep(.el-input) {

  width: 100%;

}



.form-area :deep(.el-form-item__error) {

  padding-top: 4px;

  font-size: 12px;

}



/* ── Submit Button ── */

.submit-btn {

  width: 100%;

  height: 42px;

  border: none;

  border-radius: 8px;

  background: #0f172a;

  color: #fff;

  font-size: 14px;

  font-weight: 600;

  cursor: pointer;

  transition: background 0.2s ease;

  display: flex;

  align-items: center;

  justify-content: center;

  gap: 8px;

  margin-top: 8px;

}



.submit-btn:hover {

  background: #1e293b;

}



.submit-btn:active {

  background: #0f172a;

  transform: scale(0.99);

}



.submit-btn:disabled {

  opacity: 0.7;

  cursor: not-allowed;

}



.btn-spinner {

  width: 16px;

  height: 16px;

  border: 2px solid rgba(255,255,255,0.3);

  border-top-color: #fff;

  border-radius: 50%;

  animation: spin 0.6s linear infinite;

}



@keyframes spin {

  to { transform: rotate(360deg); }

}



/* ── Footer ── */

.login-footer {

  text-align: center;

  font-size: 12px;

  color: #94a3b8;

  margin: 24px 0 0;

}



.login-footer a {

  color: #0f172a;

  text-decoration: none;

  font-weight: 500;

}



.login-footer a:hover {

  text-decoration: underline;

}

</style>

