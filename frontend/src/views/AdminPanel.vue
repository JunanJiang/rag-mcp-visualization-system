<template>
  <div class="admin-panel">
    <div class="page-head">
      <div>
        <h2 class="page-title">管理中心</h2>
        <p class="page-subtitle">管理员主要负责系统知识库治理、组织协作维护和用户权限管理。</p>
      </div>
    </div>

    <div class="overview-grid" v-if="isAdmin">
      <div class="overview-card">
        <div class="overview-title">系统知识库</div>
        <div class="overview-desc">维护全局共享的知识卡片，作为报告生成与智能问答时的公共专业参考。</div>
        <el-button type="primary" size="small" @click="goKnowledgeCenter">前往知识库</el-button>
      </div>
      <div class="overview-card">
        <div class="overview-title">组织管理</div>
        <div class="overview-desc">查看组织、维护成员关系并支撑组织内共享知识与报告协作。</div>
        <el-button size="small" @click="activeTab = 'orgs'">查看组织</el-button>
      </div>
      <div class="overview-card">
        <div class="overview-title">用户权限</div>
        <div class="overview-desc">管理用户角色，确保系统治理职责与普通业务使用职责边界清晰。</div>
        <el-button size="small" @click="activeTab = 'users'">查看用户</el-button>
      </div>
      <div class="overview-card">
        <div class="overview-title">AI 密钥</div>
        <div class="overview-desc">统一维护系统 LLM 调用所用的 API 密钥，普通用户和对话入口共用当前生效配置。</div>
        <el-button size="small" @click="activeTab = 'aiKeys'">管理密钥</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="admin-tabs">
      <el-tab-pane label="系统知识库" name="knowledge" v-if="isAdmin">
        <div class="section-header">
          <h3>系统知识库治理</h3>
          <el-button type="primary" size="small" @click="goKnowledgeCenter">前往知识库</el-button>
        </div>
        <div class="governance-grid">
          <div class="governance-card">
            <div class="governance-card-title">卡片维护</div>
            <div class="governance-card-desc">管理员可以新建、编辑和删除系统知识卡片，统一维护系统级专业知识。</div>
          </div>
          <div class="governance-card">
            <div class="governance-card-title">共享生效</div>
            <div class="governance-card-desc">系统知识卡片会对所有用户生效，作为报告生成和问答时的公共知识来源。</div>
          </div>
          <div class="governance-card">
            <div class="governance-card-title">产品演示建议</div>
            <div class="governance-card-desc">演示时可直接从知识库页面展示管理员如何维护系统级知识，以及知识如何参与报告生成。</div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 组织管理 -->
      <el-tab-pane label="组织管理" name="orgs">
        <div class="section-header">
          <h3>组织与成员治理</h3>
          <el-button type="primary" size="small" @click="showCreateOrg = true">创建组织</el-button>
        </div>
        <el-table :data="organizations" v-loading="loadingOrgs" stripe>
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="description" label="描述" />
          <el-table-column label="权限说明">
            <template #default="{ row }">
              <el-tag type="info" size="small">
                成员同权
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="viewMembers(row)">成员</el-button>
              <el-button size="small" @click="viewOrgReports(row)">报告</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 创建组织对话框 -->
        <el-dialog v-model="showCreateOrg" title="创建组织" width="400">
          <el-form :model="newOrg">
            <el-form-item label="名称">
              <el-input v-model="newOrg.name" placeholder="组织名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="newOrg.description" type="textarea" placeholder="组织描述" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showCreateOrg = false">取消</el-button>
            <el-button type="primary" @click="createOrg" :loading="submitting">创建</el-button>
          </template>
        </el-dialog>

        <!-- 成员管理对话框 -->
        <el-dialog v-model="showMembers" :title="`${selectedOrg?.name} - 成员管理`" width="600">
          <div class="section-header" style="margin-bottom: 12px">
            <span>共 {{ orgMembers.length }} 人</span>
            <div>
              <el-input v-model="addUsername" placeholder="用户名" size="small" style="width: 160px; margin-right: 8px" />
              <el-button type="primary" size="small" @click="addMember">添加</el-button>
            </div>
          </div>
          <el-table :data="presentedOrgMembers" stripe size="small">
            <el-table-column label="用户名">
              <template #default="{ row }">{{ row.displayUsername }}</template>
            </el-table-column>
            <el-table-column label="显示名">
              <template #default="{ row }">{{ row.displayName }}</template>
            </el-table-column>
            <el-table-column label="组织权限">
              <template #default="{ row }">
                <el-tag type="info" size="small">
                  同权成员
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="danger" size="small" text @click="removeMember(row)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-dialog>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户与权限" name="users" v-if="isAdmin">
        <el-table :data="presentedUsers" v-loading="loadingUsers" stripe>
          <el-table-column label="ID" width="90">
            <template #default="{ row }">{{ row.displayId }}</template>
          </el-table-column>
          <el-table-column label="用户名">
            <template #default="{ row }">{{ row.displayUsername }}</template>
          </el-table-column>
          <el-table-column label="显示名">
            <template #default="{ row }">{{ row.displayName }}</template>
          </el-table-column>
          <el-table-column prop="role" label="角色" width="150">
            <template #default="{ row }">
              <el-select v-model="row.role" size="small" @change="changeRole(row)" style="width: 120px">
                <el-option label="用户" value="user" />
                <el-option label="管理员" value="admin" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column prop="last_login" label="最后登录" width="180" />
        </el-table>
      </el-tab-pane>

      <!-- AI 密钥管理（管理员统一维护系统级 LLM 凭证） -->
      <el-tab-pane label="AI 密钥" name="aiKeys" v-if="isAdmin">
        <div class="section-header">
          <div>
            <h3>系统 AI 密钥</h3>
            <p class="section-desc">
              系统所有 LLM 调用（AI 对话、报告生成、知识检索等）共用"当前生效"的 API 密钥。同一时刻仅一条密钥处于生效状态。
            </p>
          </div>
          <el-button type="primary" size="small" @click="openCreateAiKey">新建密钥</el-button>
        </div>

        <el-table :data="aiKeys" v-loading="loadingAiKeys" stripe>
          <el-table-column label="名称" min-width="140">
            <template #default="{ row }">
              <div class="ai-key-name">
                <span>{{ row.name || '（未命名）' }}</span>
                <el-tag v-if="row.is_active" type="success" size="small" effect="dark">当前生效</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="提供商" prop="provider" width="140">
            <template #default="{ row }">{{ providerLabel(row.provider) }}</template>
          </el-table-column>
          <el-table-column label="模型" prop="model" width="150">
            <template #default="{ row }">{{ row.model || '—' }}</template>
          </el-table-column>
          <el-table-column label="密钥（脱敏）" min-width="220">
            <template #default="{ row }">
              <span class="ai-key-masked">{{ row.api_key_masked || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最后使用" prop="last_used" width="160">
            <template #default="{ row }">{{ row.last_used || '未使用' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" prop="created_at" width="160" />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="!row.is_active"
                size="small"
                type="primary"
                text
                @click="activateAiKey(row)"
              >
                启用
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                text
                @click="deactivateAiKey(row)"
              >
                停用
              </el-button>
              <el-button
                size="small"
                type="danger"
                text
                :disabled="row.is_active"
                @click="deleteAiKey(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="showCreateAiKey" title="新建 AI 密钥" width="480">
          <el-form :model="newAiKey" label-width="90px" label-position="left">
            <el-form-item label="名称">
              <el-input v-model="newAiKey.name" placeholder="例如：DeepSeek 主密钥" />
            </el-form-item>
            <el-form-item label="提供商">
              <el-select v-model="newAiKey.provider" style="width: 100%">
                <el-option label="DeepSeek 云端" value="deepseek" />
                <el-option label="OpenAI / 兼容云端" value="openai" />
                <el-option label="本地模型" value="local" />
                <el-option label="本地 Ollama" value="ollama" />
              </el-select>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="newAiKey.api_key"
                type="password"
                show-password
                placeholder="sk-..."
              />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="newAiKey.model" placeholder="deepseek-chat / gpt-4o-mini / llama3 ..." />
            </el-form-item>
            <el-form-item label="API 端点">
              <el-input v-model="newAiKey.base_url" placeholder="默认 https://api.deepseek.com/v1，本地模型请填本机地址" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="newAiKey.activate" />
              <span class="form-hint">启用后将替换当前生效密钥</span>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showCreateAiKey = false">取消</el-button>
            <el-button type="primary" :loading="creatingAiKey" @click="submitCreateAiKey">创建</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { getUserPresentation } from '../userPresentation'

const router = useRouter()
const currentUser = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || '{}') } catch { return {} }
})
const isAdmin = computed(() => currentUser.value.role === 'admin')

const activeTab = ref('knowledge')
const submitting = ref(false)

function goKnowledgeCenter() {
  router.push('/kb')
}

// ── 组织 ──
const organizations = ref([])
const loadingOrgs = ref(false)
const showCreateOrg = ref(false)
const newOrg = reactive({ name: '', description: '' })
const showMembers = ref(false)
const selectedOrg = ref(null)
const orgMembers = ref([])
const addUsername = ref('')
const presentedOrgMembers = computed(() => orgMembers.value.map(member => ({
  ...member,
  ...getUserPresentation(member)
})))

async function loadOrgs() {
  loadingOrgs.value = true
  try {
    const res = await api.get('/orgs')
    if (res.data.success) organizations.value = res.data.organizations
  } catch { /* ignore */ } finally { loadingOrgs.value = false }
}

async function createOrg() {
  submitting.value = true
  try {
    const res = await api.post('/orgs', newOrg)
    if (res.data.success) {
      ElMessage.success('组织创建成功')
      showCreateOrg.value = false
      newOrg.name = ''; newOrg.description = ''
      await loadOrgs()
    } else { ElMessage.error(res.data.error) }
  } catch (e) { ElMessage.error(e.response?.data?.error || '创建失败') }
  finally { submitting.value = false }
}

async function viewMembers(org) {
  selectedOrg.value = org
  showMembers.value = true
  try {
    const res = await api.get(`/orgs/${org.id}/members`)
    if (res.data.success) orgMembers.value = res.data.members
  } catch { ElMessage.error('加载成员失败') }
}

async function addMember() {
  if (!addUsername.value) return
  try {
    const res = await api.post(`/orgs/${selectedOrg.value.id}/members`, { username: addUsername.value })
    if (res.data.success) {
      ElMessage.success(res.data.message)
      addUsername.value = ''
      await viewMembers(selectedOrg.value)
    } else { ElMessage.error(res.data.error) }
  } catch (e) { ElMessage.error(e.response?.data?.error || '添加失败') }
}

async function removeMember(member) {
  try {
    const res = await api.delete(`/orgs/${selectedOrg.value.id}/members/${member.id}`)
    if (res.data.success) {
      ElMessage.success('已移除')
      await viewMembers(selectedOrg.value)
    }
  } catch (e) { ElMessage.error(e.response?.data?.error || '移除失败') }
}

async function viewOrgReports(org) {
  ElMessage.info(`查看 ${org.name} 的报告（功能开发中）`)
}

// ── 用户管理 ──
const allUsers = ref([])
const loadingUsers = ref(false)
const presentedUsers = computed(() => allUsers.value.map(user => ({
  ...user,
  ...getUserPresentation(user)
})))

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res = await api.get('/admin/users')
    if (res.data.success) {
      allUsers.value = res.data.users
    }
  } catch { /* ignore */ } finally { loadingUsers.value = false }
}

async function changeRole(user) {
  try {
    const res = await api.put(`/admin/users/${user.id}/role`, { role: user.role })
    if (res.data.success) {
      const target = allUsers.value.find(item => item.id === user.id)
      if (target) target.role = user.role
      ElMessage.success(res.data.message)
    } else {
      ElMessage.error(res.data.error)
      await loadUsers()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '更新失败')
    await loadUsers()
  }
}

// ── AI 密钥管理 ──
const aiKeys = ref([])
const loadingAiKeys = ref(false)
const showCreateAiKey = ref(false)
const creatingAiKey = ref(false)
const newAiKey = reactive({
  name: '',
  provider: 'deepseek',
  api_key: '',
  base_url: '',
  model: '',
  activate: true,
})

const providerLabels = {
  deepseek: 'DeepSeek 云端',
  openai: 'OpenAI / 兼容云端',
  local: '本地模型',
  ollama: '本地 Ollama',
}

function providerLabel(provider) {
  return providerLabels[provider] || provider || '—'
}

async function loadAiKeys() {
  loadingAiKeys.value = true
  try {
    const res = await api.get('/admin/ai-keys')
    if (res.data.success) aiKeys.value = res.data.keys || []
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加载 AI 密钥失败')
  } finally { loadingAiKeys.value = false }
}

function openCreateAiKey() {
  newAiKey.name = ''
  newAiKey.provider = 'deepseek'
  newAiKey.api_key = ''
  newAiKey.base_url = ''
  newAiKey.model = ''
  newAiKey.activate = true
  showCreateAiKey.value = true
}

async function submitCreateAiKey() {
  if ((newAiKey.provider === 'deepseek' || newAiKey.provider === 'openai') && !newAiKey.api_key.trim()) {
    ElMessage.warning('云端模型必须填写 API Key')
    return
  }
  creatingAiKey.value = true
  try {
    const res = await api.post('/admin/ai-keys', {
      name: newAiKey.name.trim(),
      provider: newAiKey.provider,
      api_key: newAiKey.api_key.trim(),
      base_url: newAiKey.base_url.trim(),
      model: newAiKey.model.trim(),
      activate: newAiKey.activate,
    })
    if (res.data.success) {
      ElMessage.success('AI 密钥已创建')
      showCreateAiKey.value = false
      await loadAiKeys()
    } else {
      ElMessage.error(res.data.error || '创建失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '创建失败')
  } finally { creatingAiKey.value = false }
}

async function activateAiKey(row) {
  try {
    const res = await api.post(`/admin/ai-keys/${row.id}/activate`)
    if (res.data.success) {
      ElMessage.success(res.data.message || '已启用')
      await loadAiKeys()
    } else { ElMessage.error(res.data.error || '启用失败') }
  } catch (e) { ElMessage.error(e.response?.data?.error || '启用失败') }
}

async function deactivateAiKey(row) {
  try {
    const res = await api.post(`/admin/ai-keys/${row.id}/deactivate`)
    if (res.data.success) {
      ElMessage.success(res.data.message || '已停用')
      await loadAiKeys()
    } else { ElMessage.error(res.data.error || '停用失败') }
  } catch (e) { ElMessage.error(e.response?.data?.error || '停用失败') }
}

async function deleteAiKey(row) {
  if (!window.confirm(`确认删除密钥 "${row.name || row.id}"？`)) return
  try {
    const res = await api.delete(`/admin/ai-keys/${row.id}`)
    if (res.data.success) {
      ElMessage.success(res.data.message || '已删除')
      await loadAiKeys()
    } else { ElMessage.error(res.data.error || '删除失败') }
  } catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

onMounted(() => {
  loadOrgs()
  if (isAdmin.value) {
    loadUsers()
    loadAiKeys()
  }
})
</script>

<style scoped>
.admin-panel {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
  color: #1a1a2e;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.page-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.6;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.overview-card,
.governance-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 16px;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.04);
}
.overview-title,
.governance-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 8px;
}
.overview-desc,
.governance-card-desc {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
  margin-bottom: 14px;
}
.governance-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.section-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.admin-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.section-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  max-width: 640px;
}
.ai-key-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-key-masked {
  font-family: 'Fira Code', Consolas, monospace;
  letter-spacing: 0.5px;
  color: #334155;
  font-size: 13px;
}
.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #6b7280;
}
@media (max-width: 1200px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 960px) {
  .overview-grid,
  .governance-grid {
    grid-template-columns: 1fr;
  }
}
</style>
