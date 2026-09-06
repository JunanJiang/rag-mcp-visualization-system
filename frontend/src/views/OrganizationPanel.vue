<template>
  <div class="organization-panel">
    <div class="page-header">
      <div>
        <h2 class="page-title">组织</h2>
        <p class="page-subtitle">每个组织都对应一个共享知识库。成员可以上传文件或将个人知识库文档导入组织，组织内所有成员权限一致。</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadPageData">刷新</el-button>
        <el-button type="primary" @click="showCreateOrg = true">创建组织</el-button>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-label">我的组织</div>
        <div class="summary-value">{{ organizations.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">可加入组织</div>
        <div class="summary-value">{{ discoverOrganizations.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">当前组织成员</div>
        <div class="summary-value">{{ selectedOrgMemberCount }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">当前共享文档</div>
        <div class="summary-value">{{ selectedOrgDocCount }}</div>
      </div>
    </div>

    <div class="tip-card">
      <div class="tip-title">组织使用说明</div>
      <div class="tip-text">组织本质上是一个共享知识库容器。成员可查看组织知识库、直接上传文件到组织，并可将自己的个人知识库文档导入组织；组织内成员默认同权，不再区分组织管理员。</div>
    </div>

    <div class="joinable-section">
      <div class="section-title-row">
        <div>
          <div class="section-title">可加入的组织</div>
          <div class="section-subtitle">如果组织已存在，可以直接加入并使用其共享知识库。</div>
        </div>
      </div>
      <div v-if="discoverOrganizations.length > 0" class="discover-grid">
        <div v-for="org in discoverOrganizations" :key="org.id" class="discover-card">
          <div class="discover-card-head">
            <div class="discover-name">{{ org.name }}</div>
            <el-tag size="small" type="info">{{ org.member_count || 0 }} 人</el-tag>
          </div>
          <div class="discover-desc">{{ org.description || '暂无描述' }}</div>
          <div class="discover-card-footer">
            <span class="discover-meta">创建时间：{{ org.created_at || '未知' }}</span>
            <el-button type="primary" :loading="joiningOrgId === org.id" @click="joinOrg(org)">加入组织</el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="当前没有可加入的组织" :image-size="72" class="join-empty">
        <el-button type="primary" @click="showCreateOrg = true">创建一个组织</el-button>
      </el-empty>
    </div>

    <div class="section-title-row my-org-section">
      <div>
        <div class="section-title">我的组织</div>
        <div class="section-subtitle">加入后的组织会出现在这里。你可以把它理解成自己参与维护的共享知识库。</div>
      </div>
    </div>

    <el-table :data="organizations" v-loading="loadingOrgs" stripe empty-text="你还没有加入任何组织" class="org-table">
      <el-table-column prop="name" label="组织名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="220">
        <template #default="{ row }">
          <span>{{ row.description || '暂无描述' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="成员数" width="100">
        <template #default="{ row }">{{ row.member_count ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="共享文档" width="100">
        <template #default="{ row }">{{ row.shared_doc_count ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="340" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewMembers(row)">成员</el-button>
          <el-button size="small" @click="viewSharedDocs(row)">共享文档</el-button>
          <el-button size="small" type="primary" text @click="goToKb(row)">前往知识库</el-button>
          <el-button size="small" type="danger" text :loading="leavingOrgId === row.id" @click="leaveOrg(row)">{{ (row.member_count ?? 0) <= 1 ? '删除组织' : '退出' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="organizations.length === 0 && !loadingOrgs" description="你还没有加入任何组织" :image-size="84" class="my-org-empty">
      <div class="empty-actions">
        <el-button @click="showCreateOrg = true">创建组织</el-button>
      </div>
    </el-empty>

    <el-dialog v-model="showCreateOrg" title="创建组织" width="420px">
      <el-form :model="newOrg" label-position="top">
        <el-form-item label="组织名称">
          <el-input v-model="newOrg.name" placeholder="请输入组织名称" />
        </el-form-item>
        <el-form-item label="组织描述">
          <el-input v-model="newOrg.description" type="textarea" :autosize="{ minRows: 3, maxRows: 5 }" placeholder="可选，简要说明该组织的用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateOrg = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createOrg">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMembers" :title="selectedOrg ? `${selectedOrg.name} - 成员` : '成员管理'" width="720px">
      <div class="dialog-toolbar">
        <div class="dialog-tip">组织内成员同权，均可管理成员与共享知识库。</div>
        <div class="member-add-row">
          <el-input v-model="addUsername" placeholder="输入用户名邀请成员" size="small" @keyup.enter="addMember" />
          <el-button type="primary" size="small" @click="addMember">添加成员</el-button>
        </div>
      </div>
      <el-table :data="presentedOrgMembers" stripe size="small" empty-text="暂无成员">
        <el-table-column label="用户名" min-width="120">
          <template #default="{ row }">
            <span>{{ row.displayUsername }}</span>
          </template>
        </el-table-column>
        <el-table-column label="显示名" min-width="140">
          <template #default="{ row }">
            <span>{{ row.displayName }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="joined_at" label="加入时间" min-width="180" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button type="danger" text size="small" :disabled="orgMembers.length <= 1" @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="bottom-tip">组织至少保留 1 名成员，最后一名成员不可移除。</div>
    </el-dialog>

    <el-drawer v-model="showSharedDocs" :title="selectedOrg ? `${selectedOrg.name} - 共享文档` : '共享文档'" direction="rtl" size="560px">
      <div class="drawer-actions">
        <div class="dialog-tip">组织知识库文档在组织成员之间共享使用。</div>
        <el-button type="primary" @click="goToKb(selectedOrg)">前往知识库页管理</el-button>
      </div>
      <el-table :data="sharedDocs" v-loading="loadingSharedDocs" stripe size="small" empty-text="当前组织暂无共享文档">
        <el-table-column prop="filename" label="文件名" min-width="180" />
        <el-table-column prop="file_type" label="类型" width="90" />
        <el-table-column prop="chunk_count" label="分块" width="80" />
        <el-table-column prop="created_at" label="上传时间" min-width="160" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '../api'
import { getUserPresentation } from '../userPresentation'

const router = useRouter()

const organizations = ref([])
const loadingOrgs = ref(false)
const submitting = ref(false)
const joiningOrgId = ref(null)
const leavingOrgId = ref(null)
const showCreateOrg = ref(false)
const newOrg = reactive({ name: '', description: '' })
const discoverOrganizations = ref([])

const selectedOrg = ref(null)
const showMembers = ref(false)
const orgMembers = ref([])
const addUsername = ref('')
const presentedOrgMembers = computed(() => orgMembers.value.map(member => ({
  ...member,
  ...getUserPresentation(member)
})))

const showSharedDocs = ref(false)
const sharedDocs = ref([])
const loadingSharedDocs = ref(false)

const selectedOrgMemberCount = computed(() => selectedOrg.value?.member_count || 0)
const selectedOrgDocCount = computed(() => selectedOrg.value?.shared_doc_count || 0)

async function enrichOrgStats(baseOrgs) {
  const enriched = await Promise.all(baseOrgs.map(async (org) => {
    let memberCount = 0
    let sharedDocCount = 0
    try {
      const membersRes = await api.get(`/orgs/${org.id}/members`)
      if (membersRes.data.success) memberCount = (membersRes.data.members || []).length
    } catch {}
    try {
      const docsRes = await api.get(`/kb/orgs/${org.id}/documents`)
      if (docsRes.data.success) sharedDocCount = (docsRes.data.documents || []).length
    } catch {}
    return { ...org, member_count: memberCount, shared_doc_count: sharedDocCount }
  }))
  organizations.value = enriched
  if (enriched.length > 0) {
    const activeId = selectedOrg.value?.id
    selectedOrg.value = enriched.find(org => org.id === activeId) || enriched[0]
  } else {
    selectedOrg.value = null
  }
}

async function loadDiscoverOrgs() {
  try {
    const res = await api.get('/orgs/discover')
    if (res.data.success) {
      discoverOrganizations.value = res.data.organizations || []
    }
  } catch {
    discoverOrganizations.value = []
  }
}

async function loadPageData() {
  await Promise.all([loadOrgs(), loadDiscoverOrgs()])
}

async function loadOrgs() {
  loadingOrgs.value = true
  try {
    const res = await api.get('/orgs')
    if (res.data.success) {
      await enrichOrgStats(res.data.organizations || [])
    }
  } catch {
    organizations.value = []
    selectedOrg.value = null
  } finally {
    loadingOrgs.value = false
  }
}

async function createOrg() {
  if (!newOrg.name.trim()) return ElMessage.warning('请输入组织名称')
  submitting.value = true
  try {
    const res = await api.post('/orgs', {
      name: newOrg.name.trim(),
      description: newOrg.description.trim()
    })
    if (res.data.success) {
      ElMessage.success('组织创建成功')
      showCreateOrg.value = false
      newOrg.name = ''
      newOrg.description = ''
      await loadPageData()
    } else {
      ElMessage.error(res.data.error || '创建失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '创建失败')
  } finally {
    submitting.value = false
  }
}

async function joinOrg(org) {
  joiningOrgId.value = org.id
  try {
    const res = await api.post(`/orgs/${org.id}/join`)
    if (res.data.success) {
      ElMessage.success(res.data.message || '加入成功')
      await loadPageData()
    } else {
      ElMessage.error(res.data.error || '加入失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加入失败')
  } finally {
    joiningOrgId.value = null
  }
}

async function downloadOrgArchive(org) {
  try {
    const res = await api.get(`/orgs/${org.id}/export`, { responseType: 'blob' })
    const disposition = res.headers['content-disposition'] || ''
    const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
    const rawName = match?.[1] || match?.[2] || `${org.name || 'organization'}-knowledge-base.zip`
    const filename = decodeURIComponent(rawName)
    const blobUrl = window.URL.createObjectURL(new Blob([res.data]))
    const anchor = document.createElement('a')
    anchor.href = blobUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(blobUrl)
    ElMessage.success('组织知识库压缩包已开始下载')
    return true
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '下载组织知识库失败')
    return false
  }
}

async function leaveOrg(org) {
  const isDeletingOrg = (org.member_count ?? 0) <= 1
  try {
    if (isDeletingOrg) {
      await ElMessageBox.confirm(
        `当前你是组织「${org.name}」的最后一名成员。继续操作将删除该组织，并销毁其共享知识库。此操作不可恢复。`,
        '删除组织',
        { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
      )
    } else {
      await ElMessageBox.confirm(
        `确定要退出组织「${org.name}」吗？退出后将无法访问该组织的共享知识库。`,
        '退出组织',
        { confirmButtonText: '确定退出', cancelButtonText: '取消', type: 'warning' }
      )
    }
  } catch {
    return
  }
  if (isDeletingOrg && (org.shared_doc_count ?? 0) > 0) {
    try {
      await ElMessageBox.confirm(
        `组织删除后，共享知识库中的 ${org.shared_doc_count} 份文档将被销毁。是否先一键下载 ZIP 备份到本地？`,
        '下载组织知识库',
        { confirmButtonText: '下载后删除', cancelButtonText: '直接删除', type: 'warning', distinguishCancelAndClose: true }
      )
      const downloaded = await downloadOrgArchive(org)
      if (!downloaded) return
    } catch (e) {
      if (e === 'close') return
    }
  }
  leavingOrgId.value = org.id
  try {
    const res = await api.post(`/orgs/${org.id}/leave`)
    if (res.data.success) {
      if (selectedOrg.value?.id === org.id && res.data.deleted_org) {
        showMembers.value = false
        showSharedDocs.value = false
        orgMembers.value = []
        sharedDocs.value = []
      }
      ElMessage.success(res.data.message || (isDeletingOrg ? '组织已删除' : '已退出组织'))
      await loadPageData()
    } else {
      ElMessage.error(res.data.error || (isDeletingOrg ? '删除组织失败' : '退出失败'))
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || (isDeletingOrg ? '删除组织失败' : '退出失败'))
  } finally {
    leavingOrgId.value = null
  }
}

async function viewMembers(org) {
  selectedOrg.value = org
  showMembers.value = true
  try {
    const res = await api.get(`/orgs/${org.id}/members`)
    if (res.data.success) orgMembers.value = res.data.members || []
  } catch {
    ElMessage.error('加载成员失败')
  }
}

async function addMember() {
  if (!selectedOrg.value) return
  if (!addUsername.value.trim()) return ElMessage.warning('请输入用户名')
  try {
    const res = await api.post(`/orgs/${selectedOrg.value.id}/members`, {
      username: addUsername.value.trim()
    })
    if (res.data.success) {
      ElMessage.success(res.data.message || '添加成功')
      addUsername.value = ''
      await viewMembers(selectedOrg.value)
      await loadPageData()
    } else {
      ElMessage.error(res.data.error || '添加失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '添加失败')
  }
}

async function removeMember(member) {
  if (!selectedOrg.value) return
  if (orgMembers.value.length <= 1) return ElMessage.warning('组织至少保留 1 名成员')
  try {
    const res = await api.delete(`/orgs/${selectedOrg.value.id}/members/${member.id}`)
    if (res.data.success) {
      ElMessage.success('已移除')
      await viewMembers(selectedOrg.value)
      await loadPageData()
    } else {
      ElMessage.error(res.data.error || '移除失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '移除失败')
  }
}

async function viewSharedDocs(org) {
  selectedOrg.value = org
  showSharedDocs.value = true
  loadingSharedDocs.value = true
  try {
    const res = await api.get(`/kb/orgs/${org.id}/documents`)
    if (res.data.success) sharedDocs.value = res.data.documents || []
    else sharedDocs.value = []
  } catch {
    sharedDocs.value = []
    ElMessage.error('加载共享文档失败')
  } finally {
    loadingSharedDocs.value = false
  }
}

function goToKb(org) {
  if (org?.id) router.push({ path: '/kb', query: { org: String(org.id) } })
  else router.push('/kb')
}

onMounted(() => {
  loadPageData()
})
</script>

<style scoped>
.organization-panel {
  padding: 24px;
  max-width: 1120px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
}

.page-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.summary-card,
.tip-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 16px 18px;
}

.summary-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: #111827;
}

.tip-card {
  margin-bottom: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.tip-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  color: #1f2937;
}

.tip-text,
.dialog-tip,
.bottom-tip {
  color: #6b7280;
  font-size: 13px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
}

.section-subtitle,
.discover-meta {
  color: #6b7280;
  font-size: 13px;
}

.joinable-section,
.my-org-section {
  margin-bottom: 16px;
}

.discover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.discover-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 16px;
}

.discover-card-head,
.discover-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.discover-name {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.discover-desc {
  min-height: 40px;
  margin: 12px 0 14px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.6;
}

.org-table {
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
}

.dialog-toolbar,
.drawer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.member-add-row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 280px;
}

.bottom-tip {
  margin-top: 12px;
}

.join-empty,
.my-org-empty {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  margin-bottom: 18px;
}

.empty-actions {
  display: flex;
  justify-content: center;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .dialog-toolbar,
  .drawer-actions,
  .discover-card-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions,
  .member-add-row {
    min-width: 0;
  }
}
</style>
