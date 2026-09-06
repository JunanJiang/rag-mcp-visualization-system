<template>
  <div class="profile-panel">
    <div class="profile-header">
      <h2>个人信息</h2>
      <p class="profile-subtitle">管理您的账户信息和安全设置</p>
    </div>

    <div class="profile-content" v-loading="loading">
      <!-- 用户信息卡片 -->
      <div class="profile-card">
        <div class="card-section-title">基本信息</div>
        <div class="profile-avatar-row">
          <div class="avatar" :style="{ background: avatarColor }">
            {{ avatarLetter }}
          </div>
          <div class="avatar-info">
            <div class="avatar-name">{{ presentedProfile.displayTitle }}</div>
            <div class="avatar-role">
              <el-tag :type="profile.role === 'admin' ? 'warning' : ''" size="small" effect="plain">
                {{ profile.role === 'admin' ? '管理员' : '普通用户' }}
              </el-tag>
            </div>
          </div>
        </div>

        <el-divider />

        <el-form label-width="90px" label-position="left" class="info-form">
          <el-form-item label="用户名">
            <span class="info-value readonly">{{ presentedProfile.displayUsername }}</span>
            <span class="info-hint">用户名不可修改</span>
          </el-form-item>
          <el-form-item label="显示名称">
            <div class="editable-field">
              <template v-if="!editingName">
                <span class="info-value">{{ presentedProfile.displayName || '未设置' }}</span>
                <el-button text type="primary" size="small" @click="startEditName">修改</el-button>
              </template>
              <template v-else>
                <el-input
                  v-model="newDisplayName"
                  size="default"
                  maxlength="30"
                  show-word-limit
                  placeholder="输入新的显示名称"
                  class="name-input"
                  @keyup.enter="saveDisplayName"
                />
                <el-button type="primary" size="small" :loading="savingName" @click="saveDisplayName">保存</el-button>
                <el-button size="small" @click="editingName = false">取消</el-button>
              </template>
            </div>
          </el-form-item>
          <el-form-item label="注册时间">
            <span class="info-value readonly">{{ formatTime(profile.created_at) }}</span>
          </el-form-item>
          <el-form-item label="最近登录">
            <span class="info-value readonly">{{ formatTime(profile.last_login) || '从未登录' }}</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 统计卡片 -->
      <div class="profile-card">
        <div class="card-section-title">使用统计</div>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-number">{{ stats.report_count }}</div>
            <div class="stat-label">生成报告</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ stats.kb_doc_count }}</div>
            <div class="stat-label">知识库文档</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ stats.org_count }}</div>
            <div class="stat-label">所属组织</div>
          </div>
        </div>
      </div>

      <!-- 系统 AI 模型（只读，由管理员统一管理） -->
      <div class="profile-card">
        <div class="card-section-title">
          当前使用的 AI 模型
          <el-tag size="small" type="info" effect="plain" class="readonly-tag">由管理员统一管理</el-tag>
        </div>
        <el-alert
          v-if="!aiConfigured"
          :title="aiConfigMessage || '管理员尚未启用任何 AI 模型，相关智能功能暂时不可用'"
          type="warning"
          show-icon
          :closable="false"
          class="ai-alert"
        />
        <el-form v-else label-width="110px" label-position="left" class="ai-form ai-form-readonly">
          <el-form-item label="模型来源">
            <span class="info-value readonly">{{ providerLabel }}</span>
          </el-form-item>
          <el-form-item label="模型名称" v-if="aiInfo.model">
            <span class="info-value readonly">{{ aiInfo.model }}</span>
          </el-form-item>
          <el-form-item label="API 端点" v-if="aiInfo.base_url">
            <span class="info-value readonly">{{ aiInfo.base_url }}</span>
          </el-form-item>
          <el-form-item label="API Key">
            <span class="info-value key-masked">{{ aiKeyMasked || '（未配置）' }}</span>
          </el-form-item>
        </el-form>
        <div class="info-hint ai-hint">
          所有用户共用由管理员启用的同一套模型配置，无法自行选择或修改。如需更换模型/密钥，请联系管理员。
        </div>
      </div>

      <!-- 修改密码卡片 -->
      <div class="profile-card">
        <div class="card-section-title">安全设置</div>
        <el-form
          ref="pwdFormRef"
          :model="pwdForm"
          :rules="pwdRules"
          label-width="90px"
          label-position="left"
          class="pwd-form"
        >
          <el-form-item label="旧密码" prop="old_password">
            <el-input
              v-model="pwdForm.old_password"
              type="password"
              show-password
              placeholder="输入当前密码"
            />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input
              v-model="pwdForm.new_password"
              type="password"
              show-password
              placeholder="至少6个字符"
            />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input
              v-model="pwdForm.confirm_password"
              type="password"
              show-password
              placeholder="再次输入新密码"
              @keyup.enter="changePassword"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingPwd" @click="changePassword">修改密码</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { getUserPresentation } from '../userPresentation'

const loading = ref(false)
const profile = ref({})
const stats = ref({ report_count: 0, kb_doc_count: 0, org_count: 0 })

const presentedProfile = computed(() => getUserPresentation(profile.value))

const editingName = ref(false)
const newDisplayName = ref('')
const savingName = ref(false)

const avatarLetter = computed(() => {
  const name = presentedProfile.value.displayTitle || profile.value.display_name || profile.value.username || '?'
  return name.charAt(0).toUpperCase()
})

const avatarColor = computed(() => {
  const colors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
  const name = profile.value.username || ''
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
})

async function loadProfile() {
  loading.value = true
  try {
    const res = await api.get('/auth/profile')
    if (res.data.success) {
      profile.value = res.data.user
      stats.value = res.data.stats || stats.value
    }
  } catch { ElMessage.error('获取个人信息失败') }
  finally { loading.value = false }
}

function startEditName() {
  newDisplayName.value = profile.value.display_name || ''
  editingName.value = true
}

async function saveDisplayName() {
  if (!newDisplayName.value.trim()) return ElMessage.warning('显示名称不能为空')
  savingName.value = true
  try {
    const res = await api.put('/auth/profile', { display_name: newDisplayName.value.trim() })
    if (res.data.success) {
      profile.value.display_name = res.data.user.display_name
      const stored = JSON.parse(localStorage.getItem('user') || '{}')
      stored.display_name = res.data.user.display_name
      localStorage.setItem('user', JSON.stringify(stored))
      editingName.value = false
      ElMessage.success('显示名称已更新')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '更新失败')
  } finally { savingName.value = false }
}

// 修改密码
const pwdFormRef = ref(null)
const savingPwd = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const pwdRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (value !== pwdForm.new_password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

async function changePassword() {
  try {
    await pwdFormRef.value.validate()
  } catch { return }

  savingPwd.value = true
  try {
    const res = await api.put('/auth/password', {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password
    })
    if (res.data.success) {
      ElMessage.success('密码已修改')
      pwdForm.old_password = ''
      pwdForm.new_password = ''
      pwdForm.confirm_password = ''
      pwdFormRef.value?.resetFields()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '修改密码失败')
  } finally { savingPwd.value = false }
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ── 系统 AI 模型（只读展示） ──
const aiInfo = reactive({ provider: '', base_url: '', model: '' })
const aiKeyMasked = ref('')
const aiConfigured = ref(false)
const aiConfigMessage = ref('')

const providerLabels = {
  deepseek: 'DeepSeek 云端',
  openai: 'OpenAI / 兼容云端',
  local: '本地模型',
  ollama: '本地 Ollama'
}

const providerLabel = computed(() => providerLabels[aiInfo.provider] || aiInfo.provider || '—')

async function loadAiConfig() {
  try {
    const res = await api.get('/user/ai-config')
    if (res.data.success) {
      const c = res.data.config || {}
      aiInfo.provider = c.provider || ''
      aiInfo.base_url = c.base_url || ''
      aiInfo.model = c.model || ''
      aiKeyMasked.value = res.data.api_key_masked || ''
      aiConfigured.value = !!res.data.configured
      aiConfigMessage.value = res.data.message || ''
    }
  } catch { /* 静默 */ }
}

onMounted(() => { loadProfile(); loadAiConfig() })
</script>

<style scoped>
.profile-panel {
  padding: var(--sp-6) var(--sp-8);
  max-width: 720px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
}

.profile-header {
  margin-bottom: 28px;
}

.profile-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text-1);
  margin: 0 0 4px;
}

.profile-subtitle {
  font-size: 13px;
  color: var(--c-text-3);
  margin: 0;
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 40px;
}

.profile-card {
  background: var(--c-bg-card, #fff);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 24px;
}

.card-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text-1);
  margin-bottom: 20px;
}

/* 头像区域 */
.profile-avatar-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.avatar-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.avatar-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--c-text-1);
}

/* 表单信息 */
.info-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.info-value {
  font-size: 14px;
  color: var(--c-text-1);
}

.info-value.readonly {
  color: var(--c-text-3);
}

.info-hint {
  font-size: 11px;
  color: var(--c-text-3);
  margin-left: 8px;
}

.editable-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name-input {
  max-width: 240px;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 20px 12px;
  background: var(--c-bg-page, #f5f7fa);
  border-radius: 10px;
  border: 1px solid var(--c-border);
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  color: var(--c-primary, #3b82f6);
  line-height: 1;
  margin-bottom: 6px;
}

.stat-label {
  font-size: 12px;
  color: var(--c-text-3);
  font-weight: 500;
}

/* 密码表单 */
.pwd-form {
  max-width: 400px;
}

.pwd-form :deep(.el-input) {
  max-width: 280px;
}

.ai-form {
  max-width: 480px;
}

.ai-form-readonly :deep(.el-form-item) {
  margin-bottom: 10px;
}

.readonly-tag {
  margin-left: 10px;
  vertical-align: middle;
}

.ai-alert {
  margin-bottom: 8px;
}

.ai-hint {
  margin-top: 6px;
  margin-left: 0;
  font-size: 12px;
  color: var(--c-text-3);
  line-height: 1.6;
}

.key-masked {
  font-family: monospace;
  letter-spacing: 1px;
  color: var(--c-text-3);
}

@media (max-width: 640px) {
  .profile-panel {
    padding: var(--sp-4) var(--sp-3);
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .editable-field {
    flex-wrap: wrap;
  }

  .name-input {
    max-width: 100%;
    width: 100%;
  }
}
</style>
