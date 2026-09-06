<template>
  <div class="report-generator">
    <!-- 步骤指引条 -->
    <div class="step-bar">
      <div v-for="(s, i) in stepDefs" :key="s.key" class="step-item" :class="{ active: s.key === currentStep, done: stepIndex > i }">
        <div class="step-dot">
          <span v-if="stepIndex > i" class="step-check">✓</span>
          <span v-else>{{ i + 1 }}</span>
        </div>
        <span class="step-label">{{ s.label }}</span>
        <span v-if="i < stepDefs.length - 1" class="step-line" :class="{ filled: stepIndex > i }"></span>
      </div>
    </div>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 步骤1: 上传数据包 -->
      <div v-if="currentStep === 'upload'" class="step-container">
        <UploadPanel @uploaded="onDataUploaded" />
      </div>

      <!-- 步骤2: Clarification问答 -->
      <div v-else-if="currentStep === 'clarification'" class="step-container">
        <ClarificationPanel 
          ref="clarificationPanelRef"
          :questions="clarificationQuestions"
          :domains="domains"
          :phenomena="phenomena"
          :purposes="purposes"
          @submit="onClarificationSubmit"
          @back="goBackFromClarification"
        />
      </div>

      <!-- 步骤3: 槽位生成与交互 -->
      <div v-else-if="currentStep === 'generate'" class="generate-container">
        <!-- 顶部工具栏 -->
        <div class="generate-toolbar">
          <div class="toolbar-left">
            <el-button type="primary" size="small" @click="generateNextSlot" :disabled="progress.pending === 0">
              <el-icon><CaretRight /></el-icon> 生成下一个
            </el-button>
            <el-button size="small" @click="generateAllSlots" :disabled="progress.pending === 0">
              <el-icon><DArrowRight /></el-icon> 生成全部
            </el-button>
            <el-button type="success" size="small" @click="acceptAllSlots" :disabled="progress.draft === 0">
              <el-icon><Check /></el-icon> 全部确认
            </el-button>
          </div>
          <div class="toolbar-right">
            <el-button size="small" @click="resetWorkflowToUpload">重新上传数据包</el-button>
            <span class="toolbar-stat">
              <span class="stat-dot pending"></span> 待生成 {{ progress.pending }}
            </span>
            <span class="toolbar-stat">
              <span class="stat-dot draft"></span> 待确认 {{ progress.draft }}
            </span>
            <span class="toolbar-stat">
              <span class="stat-dot accepted"></span> 已完成 {{ progress.accepted }}
            </span>
          </div>
        </div>

        <!-- 文档预览（全宽，含内联操作） -->
        <div class="preview-panel">
          <DocumentPreview 
            ref="docPreviewRef"
            :slots="slots"
            :facts="facts"
            :policy="policy"
            :active-slot-id="selectedSlot?.slot_id"
            @slot-click="selectSlot"
            @slot-accept="acceptSlot"
            @slot-reject="rejectSlot"
            @slot-edit="editSlot"
            @slot-rewrite="rewriteSlot"
          />
        </div>
      </div>
    </main>

    <!-- 底部进度条 + 质量评估 + 导出按钮 -->
    <div v-if="currentStep === 'generate'" class="progress-bar">
      <el-progress 
        :percentage="progress.progress" 
        :format="() => `${progress.accepted}/${progress.total}`"
        :stroke-width="4"
        color="#2563eb"
      />
      <el-button
        size="small"
        @click="runQualityCheck"
        :loading="qualityLoading"
        :disabled="progress.total === 0"
        style="margin-left: 8px;"
      >
        <el-icon><DataLine /></el-icon>
        质量评估
      </el-button>
      <el-button 
        type="primary" 
        size="small"
        @click="exportReport"
        :disabled="!canExport"
        style="margin-left: 4px;"
      >
        <el-icon><Download /></el-icon>
        导出
      </el-button>
    </div>

    <!-- 导出下载面板 -->
    <el-dialog v-model="showExport" title="报告导出成功" width="480" :close-on-click-modal="true">
      <div v-if="exportResult" class="export-panel">
        <div class="export-dir">
          <span class="export-dir-label">输出目录</span>
          <code class="export-dir-path">{{ exportResult.outputDir }}</code>
        </div>
        <div class="export-btns">
          <el-button
            v-if="exportResult.hasPdf"
            type="primary"
            size="large"
            class="dl-btn dl-pdf"
            @click="downloadFile('pdf')"
          >
            <el-icon><Document /></el-icon>
            下载 PDF
          </el-button>
          <el-tooltip v-else content="安装 weasyprint 或 pdfkit 可启用 PDF 导出" placement="top">
            <el-button type="primary" size="large" class="dl-btn dl-pdf" disabled>
              <el-icon><Document /></el-icon>
              PDF（未启用）
            </el-button>
          </el-tooltip>

          <el-button size="large" class="dl-btn dl-docx" @click="downloadFile('docx')">
            <el-icon><Memo /></el-icon>
            下载 Word
          </el-button>

          <el-button size="large" class="dl-btn dl-md" @click="downloadFile('md')">
            <el-icon><Document /></el-icon>
            下载 Markdown
          </el-button>

          <el-button size="large" class="dl-btn dl-draft" @click="downloadFile('draft')">
            <el-icon><Files /></el-icon>
            Draft JSON
          </el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showExport = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 质量评估结果弹窗 -->
    <el-dialog v-model="showQuality" title="报告质量评估" width="520">
      <div v-if="qualityResult" class="quality-panel">
        <div class="quality-score-ring">
          <el-progress type="circle" :percentage="qualityResult.total_score" :width="100"
            :color="qualityResult.total_score >= 80 ? '#10b981' : qualityResult.total_score >= 60 ? '#f59e0b' : '#ef4444'"
          />
        </div>
        <div class="quality-dims">
          <div v-for="d in qualityResult.dimensions" :key="d.id" class="dim-row">
            <span class="dim-name">{{ d.name }}</span>
            <el-progress :percentage="d.score" :stroke-width="8" :color="d.score >= 80 ? '#10b981' : d.score >= 60 ? '#f59e0b' : '#ef4444'" style="flex:1;margin:0 12px;" />
            <span class="dim-score">{{ d.score }}</span>
          </div>
        </div>
        <div v-if="qualityResult.suggestions?.length" class="quality-suggestions">
          <div class="sug-title">改进建议</div>
          <div v-for="(s, i) in qualityResult.suggestions" :key="i" class="sug-item">{{ i+1 }}. {{ s }}</div>
        </div>
        <div v-if="qualityResult.summary" class="quality-summary">{{ qualityResult.summary }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, DataLine, Document, Memo, Files, CaretRight, DArrowRight, Check } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

import UploadPanel from '../components/UploadPanel.vue'
import ClarificationPanel from '../components/ClarificationPanel.vue'
import DocumentPreview from '../components/DocumentPreview.vue'
// InteractionPanel removed — operations merged into DocumentPreview inline actions

const KB_PREFERENCES_KEY = 'kb_generation_preferences'

function loadKbPreferences() {
  try {
    const raw = localStorage.getItem(KB_PREFERENCES_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return {
      enable_system_kb: parsed.enableSystemKb !== false,
      enable_personal_kb: parsed.enablePersonalKb !== false,
      enable_org_kb: parsed.enableOrgKb !== false
    }
  } catch {
    return {
      enable_system_kb: true,
      enable_personal_kb: true,
      enable_org_kb: true
    }
  }
}

// 路由
const route = useRoute()
const router = useRouter()

// AI 工作流事件
const workflowEvent = inject('workflowEvent', ref(null))

// 状态
const clarificationPanelRef = ref(null)
const docPreviewRef = ref(null)
const aiDraftReady = ref(false)  // AI 已在后端创建 Draft，无需重复提交
const currentStep = ref('upload')  // upload, clarification, generate

const stepDefs = [
  { key: 'upload', label: '上传数据' },
  { key: 'clarification', label: '配置报告' },
  { key: 'generate', label: '生成内容' },
  { key: 'export', label: '导出报告' },
]
const stepIndex = computed(() => {
  const idx = stepDefs.findIndex(s => s.key === currentStep.value)
  return idx >= 0 ? idx : 0
})
const dataPackagePath = ref('')
const clarificationQuestions = ref([])
const domains = ref([])
const phenomena = ref([])
const purposes = ref([])
const slots = ref([])
const facts = ref({})
const policy = ref({})
const progress = ref({ total: 0, pending: 0, draft: 0, accepted: 0, progress: 0 })
const selectedSlot = ref(null)

const canExport = computed(() => {
  return progress.value.pending === 0 && progress.value.total > 0
})

function clearLocalWorkflowState() {
  aiDraftReady.value = false
  currentStep.value = 'upload'
  dataPackagePath.value = ''
  clarificationQuestions.value = []
  domains.value = []
  phenomena.value = []
  purposes.value = []
  slots.value = []
  facts.value = {}
  policy.value = {}
  progress.value = { total: 0, pending: 0, draft: 0, accepted: 0, progress: 0 }
  selectedSlot.value = null
  qualityLoading.value = false
  qualityResult.value = null
  showQuality.value = false
  exportResult.value = null
  showExport.value = false
}

async function resetWorkflowToUpload({ confirm = true, showMessage = true } = {}) {
  if (confirm) {
    try {
      await ElMessageBox.confirm(
        '重新上传会清空当前数据包和已生成的 Draft，是否继续？',
        '确认重新上传',
        {
          type: 'warning',
          confirmButtonText: '继续',
          cancelButtonText: '取消'
        }
      )
    } catch {
      return false
    }
  }

  try {
    await api.post('/session/reset')
    clearLocalWorkflowState()
    if (showMessage) {
      ElMessage.success('已清空当前数据包，请重新上传')
    }
    return true
  } catch (error) {
    ElMessage.error('重置失败: ' + (error.response?.data?.error || error.message))
    return false
  }
}

// clarification 页返回按钮
async function goBackFromClarification() {
  await resetWorkflowToUpload()
}

// 质量评估
const qualityLoading = ref(false)
const qualityResult = ref(null)
const showQuality = ref(false)

// 导出
const showExport = ref(false)
const exportResult = ref(null)

watch(() => route.query.reset, async (val) => {
  if (val) {
    await resetWorkflowToUpload({ confirm: false, showMessage: false })
    router.replace({ path: '/v2', query: {} })
  }
}, { immediate: true })

function getKbPolicyPayload() {
  return loadKbPreferences()
}

async function syncKbPreferencesToDraft({ silent = false } = {}) {
  try {
    const kbPolicy = getKbPolicyPayload()
    const res = await api.put('/draft/policy', kbPolicy)
    policy.value = { ...policy.value, ...kbPolicy }
    return res.data
  } catch (error) {
    if (error.response?.status === 400) return null
    if (!silent) {
      ElMessage.error('知识库开关同步失败: ' + (error.response?.data?.error || error.message))
    }
    return null
  }
}

// 监听 AI 工作流事件，动态更新 UI
watch(workflowEvent, async (event) => {
  if (!event) return
  
  const { action, result } = event
  console.log('[WorkflowEvent]', action, result)
  
  if (action === 'auto_configure') {
    // AI 自动配置 → 先加载问题 → 跳到配置页面 → 动画演示选择 → 再跳到生成页面
    try {
      // 确保问题已加载
      if (clarificationQuestions.value.length === 0) {
        const res = await api.get('/clarification/questions')
        if (res.data.success) {
          clarificationQuestions.value = res.data.questions
          domains.value = res.data.domains
          phenomena.value = res.data.phenomena
          purposes.value = res.data.purposes
        }
      }
      // 跳到 clarification 页面
      currentStep.value = 'clarification'
      await nextTick()
      // 等待组件挂载
      await new Promise(r => setTimeout(r, 300))
      // 播放 AI 动画（选中选项 + 自动提交）
      if (clarificationPanelRef.value && result.answers) {
        aiDraftReady.value = true
        const aiAnswers = { ...result.answers }
        clarificationPanelRef.value.playAiAnimation(aiAnswers)
      } else {
        // fallback：直接跳转
        await refreshDraft()
        await syncKbPreferencesToDraft({ silent: true })
        currentStep.value = 'generate'
        ElMessage.success(`AI 已完成报告配置，创建了 ${result.slot_count || '?'} 个槽位`)
      }
    } catch (err) {
      console.error('auto_configure animation failed:', err)
      await refreshDraft()
      await syncKbPreferencesToDraft({ silent: true })
      currentStep.value = 'generate'
    }
  } 
  else if (action === 'generate_next_slot') {
    // AI 生成了一个槽位 → 确保在生成页面 → 刷新 Draft → 滚动到该槽位
    if (currentStep.value !== 'generate') currentStep.value = 'generate'
    await refreshDraft()
    await nextTick()
    if (docPreviewRef.value && result.slot_id) {
      docPreviewRef.value.scrollToSlot(result.slot_id)
    }
    const remaining = result.remaining ?? '?'
    ElMessage.info(`已生成「${result.slot_name || result.slot_id}」${remaining > 0 ? `，还剩 ${remaining} 个` : '，全部完成！'}`)
  }
  else if (action === 'generate_all_slots') {
    // AI 一次性生成了所有槽位（备用）→ 确保在生成页面 → 刷新 Draft
    if (currentStep.value !== 'generate') currentStep.value = 'generate'
    await refreshDraft()
    await nextTick()
    if (docPreviewRef.value && slots.value.length > 0) {
      docPreviewRef.value.scrollToSection('section-1')
    }
    ElMessage.success(`AI 已生成 ${result.generated || '?'} 个槽位内容`)
  } 
  else if (action === 'accept_all_slots') {
    // AI 确认了所有槽位 → 刷新 Draft
    if (currentStep.value !== 'generate') currentStep.value = 'generate'
    await refreshDraft()
    await nextTick()
    // 滚动到结论部分，展示确认效果
    if (docPreviewRef.value) {
      docPreviewRef.value.scrollToSection('section-7')
    }
    ElMessage.success(`AI 已确认 ${result.accepted_count || '?'} 个槽位`)
  } 
  else if (action === 'export_report') {
    // AI 导出了报告 → 显示结果
    await refreshDraft()
    ElMessageBox.alert(
      `<p>报告已由 AI 助手自动生成并导出：</p>
       <p><code>${result.output_dir || ''}</code></p>
       <p>包含文件：report.md, report.docx, draft.json</p>`,
      'AI 自动导出成功',
      { dangerouslyUseHTMLString: true, confirmButtonText: '确定' }
    )
  }
}, { deep: true })

// 获取 Clarification 问题
async function fetchClarificationQuestions() {
  try {
    const res = await api.get('/clarification/questions')
    if (res.data.success) {
      clarificationQuestions.value = res.data.questions
      domains.value = res.data.domains || []
      phenomena.value = res.data.phenomena || []
      purposes.value = res.data.purposes || []
      currentStep.value = 'clarification'
    }
  } catch (error) {
    ElMessage.error('获取问题失败: ' + (error.response?.data?.error || error.message))
  }
}

// 数据包上传完成
async function onDataUploaded(result) {
  dataPackagePath.value = result.path
  await fetchClarificationQuestions()
}

// Clarification提交
async function onClarificationSubmit(answers) {
  try {
    // 如果 AI 已经在后端创建了 Draft，直接刷新而不是重复提交
    if (aiDraftReady.value) {
      aiDraftReady.value = false
      await refreshDraft()
      await syncKbPreferencesToDraft({ silent: true })
      currentStep.value = 'generate'
      ElMessage.success('AI 配置完成，开始生成报告')
      return
    }

    const kbPolicy = getKbPolicyPayload()
    const res = await api.post('/clarification/submit', {
      answers: {
        ...answers,
        ...kbPolicy
      },
      engineModelName: answers.engineModelName || '',
      projectCode: answers.projectCode || ''
    })
    
    if (res.data.success) {
      // 直接使用原始数据，不做任何转换
      slots.value = res.data.slots
      policy.value = { ...res.data.policy, ...kbPolicy }
      facts.value = res.data.facts || {}
      progress.value = res.data.progress
      
      // 调试：打印到页面alert
      const debugInfo = `
        manifest.block_count: ${res.data.facts?.manifest?.block_count}
        datasets.block_count: ${res.data.facts?.datasets?.block_count}
        variables.length: ${res.data.facts?.variables?.length}
      `
      console.log('DEBUG:', debugInfo)
      console.log('Full facts:', JSON.stringify(res.data.facts, null, 2).substring(0, 500))
      
      currentStep.value = 'generate'
      ElMessage.success('配置完成，开始生成报告')
    }
  } catch (error) {
    ElMessage.error('提交失败: ' + (error.response?.data?.error || error.message))
  }
}

// 获取Draft状态
async function refreshDraft() {
  try {
    const res = await api.get('/draft')
    if (res.data.success) {
      slots.value = res.data.draft.slots
      facts.value = res.data.draft.facts
      policy.value = res.data.draft.policy
      progress.value = res.data.progress
    }
  } catch (error) {
    console.error('刷新Draft失败:', error)
  }
}

function consumeIntegrationContext() {
  try {
    const raw = localStorage.getItem('integration_context')
    if (!raw) return null
    localStorage.removeItem('integration_context')
    return JSON.parse(raw)
  } catch {
    localStorage.removeItem('integration_context')
    return null
  }
}

async function applySessionContext(context) {
  if (!context) return false
  if (context.dataPackage?.path) {
    dataPackagePath.value = context.dataPackage.path
  } else if (context.packagePath) {
    dataPackagePath.value = context.packagePath
  }
  const recommendedStep = context.recommendedStep
  if (recommendedStep === 'generate') {
    await refreshDraft()
    currentStep.value = 'generate'
    return true
  }
  if (recommendedStep === 'clarification') {
    await fetchClarificationQuestions()
    currentStep.value = 'clarification'
    return true
  }
  return !!dataPackagePath.value
}

async function restoreSessionContext() {
  const integrationContext = consumeIntegrationContext()
  if (integrationContext) {
    const applied = await applySessionContext(integrationContext)
    if (applied) return
  }
  try {
    const res = await api.get('/session/context')
    if (!res.data.success) return
    await applySessionContext(res.data)
  } catch (error) {
    console.error('恢复会话上下文失败:', error)
  }
}

onMounted(async () => {
  await syncKbPreferencesToDraft({ silent: true })
  if (route.query.resume === '1') {
    await restoreSessionContext()
  }
})

// 生成下一个槽位
async function generateNextSlot() {
  try {
    const res = await api.post('/slots/generate-next')
    if (res.data.success) {
      if (res.data.completed) {
        ElMessage.success('所有槽位已生成')
      } else {
        // 更新槽位列表
        const updatedSlot = res.data.slot
        const index = slots.value.findIndex(s => s.slot_id === updatedSlot.slot_id)
        if (index >= 0) {
          slots.value[index] = updatedSlot
        }
        progress.value = res.data.progress
        selectSlot(updatedSlot)
      }
    }
  } catch (error) {
    ElMessage.error('生成失败: ' + (error.response?.data?.error || error.message))
  }
}

// 生成所有槽位
async function generateAllSlots() {
  try {
    ElMessage.info('正在生成所有槽位...')
    const res = await api.post('/slots/generate-all')
    if (res.data.success) {
      slots.value = res.data.slots
      progress.value = res.data.progress
      ElMessage.success(`已生成 ${res.data.generated} 个槽位`)
    }
  } catch (error) {
    ElMessage.error('生成失败: ' + (error.response?.data?.error || error.message))
  }
}

// 选择槽位
function selectSlot(slot) {
  selectedSlot.value = slot
}

// 接受槽位
async function acceptSlot(slotId) {
  try {
    const res = await api.post(`/slots/${slotId}/accept`)
    if (res.data.success) {
      const index = slots.value.findIndex(s => s.slot_id === slotId)
      if (index >= 0) {
        slots.value[index] = res.data.slot
      }
      progress.value = res.data.progress
      selectedSlot.value = res.data.slot
      ElMessage.success('已接受')
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

// 全部确认
async function acceptAllSlots() {
  try {
    const res = await api.post('/slots/accept-all')
    if (res.data.success) {
      slots.value = res.data.slots
      progress.value = res.data.progress
      ElMessage.success(`已确认 ${res.data.accepted_count} 个槽位`)
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

// 拒绝槽位
async function rejectSlot({ slotId, reason, feedback }) {
  try {
    const res = await api.post(`/slots/${slotId}/reject`, { reason, feedback })
    if (res.data.success) {
      const index = slots.value.findIndex(s => s.slot_id === slotId)
      if (index >= 0) {
        slots.value[index] = res.data.slot
      }
      progress.value = res.data.progress
      selectedSlot.value = res.data.slot
      ElMessage.warning('已拒绝，请点击改写')
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

// 改写槽位
async function rewriteSlot(slotId) {
  try {
    const res = await api.post(`/slots/${slotId}/rewrite`)
    if (res.data.success) {
      const index = slots.value.findIndex(s => s.slot_id === slotId)
      if (index >= 0) {
        slots.value[index] = res.data.slot
      }
      progress.value = res.data.progress
      selectedSlot.value = res.data.slot
      ElMessage.success('已改写')
    }
  } catch (error) {
    ElMessage.error('改写失败: ' + (error.response?.data?.error || error.message))
  }
}

// 编辑槽位
async function editSlot({ slotId, content }) {
  try {
    const res = await api.put(`/slots/${slotId}/edit`, { content })
    if (res.data.success) {
      const index = slots.value.findIndex(s => s.slot_id === slotId)
      if (index >= 0) {
        slots.value[index] = res.data.slot
      }
      progress.value = res.data.progress
      selectedSlot.value = res.data.slot
      ElMessage.success('已保存')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.error || error.message))
  }
}

// 质量评估
async function runQualityCheck() {
  qualityLoading.value = true
  try {
    const res = await api.post('/report/quality-check')
    if (res.data.success) {
      qualityResult.value = res.data.quality
      showQuality.value = true
    } else {
      ElMessage.error(res.data.error || '质量评估失败')
    }
  } catch (error) {
    ElMessage.error('质量评估失败: ' + (error.response?.data?.error || error.message))
  } finally {
    qualityLoading.value = false
  }
}

// 导出报告
async function exportReport() {
  try {
    const res = await api.post('/export/report')
    if (res.data.success) {
      ElMessage.success('报告导出成功')
      exportResult.value = {
        outputDir: res.data.outputDir,
        hasPdf: !!res.data.files?.pdf,
        reportId: res.data.reportId
      }
      showExport.value = true
    } else {
      ElMessage.error(res.data.error || '导出失败')
    }
  } catch (error) {
    ElMessage.error('导出失败: ' + (error.response?.data?.error || error.message))
  }
}

// 下载文件（通过 axios blob 下载，携带 token 认证）
async function downloadFile(type) {
  if (!exportResult.value?.outputDir) return
  try {
    const token = localStorage.getItem('token')
    const res = await api.get(`/download/${type}`, {
      params: { dir: exportResult.value.outputDir },
      responseType: 'blob',
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    const nameMap = { pdf: 'report.pdf', docx: 'report.docx', md: 'report.md', draft: 'draft.json' }
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = nameMap[type] || 'download'
    a.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败: ' + (error.response?.data?.error || error.message))
  }
}
</script>

<style scoped>
.report-generator {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--c-bg-page);
}

/* ── Step Bar ── */
.step-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px var(--sp-6);
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
  gap: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.step-bar::-webkit-scrollbar {
  display: none;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.step-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  background: var(--c-gray-100);
  color: var(--c-text-4);
  border: 2px solid var(--c-border);
  flex-shrink: 0;
  transition: all 0.3s ease;
}
.step-item.active .step-dot {
  background: var(--c-primary);
  color: white;
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px rgba(37,99,235,0.15);
}
.step-item.done .step-dot {
  background: #10b981;
  color: white;
  border-color: #10b981;
}
.step-check { font-size: 12px; }
.step-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-4);
  white-space: nowrap;
}
.step-item.active .step-label { color: var(--c-primary); font-weight: 600; }
.step-item.done .step-label { color: #10b981; }
.step-line {
  width: 32px;
  height: 2px;
  background: var(--c-border);
  margin: 0 4px;
  border-radius: 1px;
  transition: background 0.3s ease;
}
.step-line.filled { background: #10b981; }

.main-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.step-container {
  height: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-6) var(--sp-8);
  overflow-y: auto;
}

.generate-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.generate-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-2) var(--sp-4);
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
  gap: var(--sp-3);
}
.toolbar-left { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.toolbar-right { display: flex; gap: var(--sp-4); align-items: center; }
.toolbar-stat { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--c-text-3); }
.stat-dot { width: 8px; height: 8px; border-radius: 50%; }
.stat-dot.pending { background: #e6a23c; }
.stat-dot.draft { background: #ffc107; }
.stat-dot.accepted { background: #10b981; }

.preview-panel {
  flex: 1;
  overflow: auto;
  background: var(--c-bg-card);
  min-width: 0;
}

.progress-bar {
  display: flex;
  align-items: center;
  padding: var(--sp-2) var(--sp-4);
  background: var(--c-bg-card);
  border-top: 1px solid var(--c-border);
  flex-shrink: 0;
  gap: var(--sp-2);
}

.progress-bar .el-progress {
  flex: 1;
}

/* ── 质量评估面板 ── */
.quality-panel {
  text-align: center;
}

.quality-score-ring {
  margin-bottom: 20px;
}

.quality-dims {
  text-align: left;
  margin-bottom: 16px;
}

.dim-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.dim-name {
  width: 90px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  flex-shrink: 0;
}

.dim-score {
  width: 32px;
  text-align: right;
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  flex-shrink: 0;
}

.quality-suggestions {
  text-align: left;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 12px;
}

.sug-title {
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 6px;
}

.sug-item {
  font-size: 13px;
  color: #78350f;
  line-height: 1.6;
}

.quality-summary {
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}

/* ── 导出下载面板 ── */
.export-panel {
  padding: 4px 0;
}

.export-dir {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 20px;
}

.export-dir-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.export-dir-path {
  font-size: 12px;
  background: #f3f4f6;
  padding: 6px 10px;
  border-radius: 6px;
  color: #374151;
  word-break: break-all;
}

.export-btns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.dl-btn {
  width: 100%;
  height: 52px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.dl-pdf.el-button--primary {
  background: #dc2626 !important;
  border-color: #dc2626 !important;
  font-size: 15px !important;
  height: 58px !important;
}
.dl-pdf.el-button--primary:hover {
  background: #b91c1c !important;
  border-color: #b91c1c !important;
}

.dl-docx {
  color: #2563eb !important;
  border-color: #bfdbfe !important;
  background: #eff6ff !important;
}
.dl-docx:hover {
  background: #dbeafe !important;
  border-color: #2563eb !important;
}

.dl-md {
  color: #059669 !important;
  border-color: #a7f3d0 !important;
  background: #ecfdf5 !important;
}
.dl-md:hover {
  background: #d1fae5 !important;
  border-color: #059669 !important;
}

.dl-draft {
  color: #6b7280 !important;
  border-color: #e5e7eb !important;
  background: #f9fafb !important;
}
.dl-draft:hover {
  background: #f3f4f6 !important;
  border-color: #9ca3af !important;
}

@media (max-width: 1100px) {
  .step-container {
    padding: var(--sp-4) var(--sp-5);
  }

  .toolbar-right {
    gap: var(--sp-2);
  }
}

@media (max-width: 820px) {
  .step-bar {
    justify-content: flex-start;
    padding: 8px var(--sp-3);
  }

  .step-label {
    font-size: 11px;
  }

  .step-line {
    width: 24px;
  }

  .generate-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
  }

  .toolbar-right {
    justify-content: space-between;
  }

  .progress-bar {
    flex-direction: column;
    align-items: stretch;
    gap: var(--sp-2);
  }

  .export-btns {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .step-container {
    padding: var(--sp-3);
  }

  .toolbar-stat {
    font-size: 11px;
  }

  .progress-bar :deep(.el-button) {
    width: 100%;
    margin-left: 0 !important;
  }
}
</style>
