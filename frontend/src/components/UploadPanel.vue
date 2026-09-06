<template>
  <div class="upload-panel">
    <div class="upload-card">
      <div class="card-top">
        <div class="card-icon">
          <el-icon :size="22"><FolderOpened /></el-icon>
        </div>
        <h2>上传数据包</h2>
        <p class="card-desc">支持 SimuVision 导出的 Plot3D 数据包文件夹或 ZIP 压缩包</p>
      </div>
      
      <div class="upload-sections">
        <!-- Section 1: 快速加载 -->
        <button class="quick-load-btn" @click="loadDefaultPackage" :disabled="loading">
          <el-icon :size="16"><FolderOpened /></el-icon>
          <span>{{ loading ? '加载中…' : '一键加载测试数据包' }}</span>
        </button>
        
        <div class="section-divider"><span>或手动输入路径</span></div>
        
        <!-- Section 2: 路径输入 -->
        <div class="folder-input">
          <el-input 
            v-model="folderPath" 
            placeholder="输入数据包文件夹路径"
          >
            <template #prepend>路径</template>
          </el-input>
          <el-button type="primary" @click="loadFolder" :loading="loading">加载</el-button>
        </div>
        
        <div class="section-divider"><span>或上传 ZIP</span></div>
        
        <!-- Section 3: ZIP 上传 -->
        <el-upload
          class="upload-dragger"
          drag
          action="/api/upload"
          :headers="uploadHeaders"
          :show-file-list="false"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          accept=".zip"
        >
          <el-icon class="el-icon--upload" :size="28"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            拖拽 ZIP 到此处，或 <em>点击上传</em>
          </div>
        </el-upload>
      </div>
      
      <!-- 数据包信息预览 -->
      <div v-if="packageInfo" class="package-info">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">数据类型</span>
            <span class="info-value">{{ packageInfo.datasetType }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">网格块数</span>
            <span class="info-value">{{ packageInfo.blockCount }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">总节点数</span>
            <span class="info-value">{{ packageInfo.totalPoints?.toLocaleString() }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">变量数量</span>
            <span class="info-value">{{ packageInfo.variableCount }}</span>
          </div>
        </div>
        <div class="variables-list">
          <span class="var-label">变量：</span>
          <span v-for="v in packageInfo.variables" :key="v" class="var-tag">{{ v }}</span>
        </div>

        <!-- 数据包合规验证 -->
        <div class="validation-section">
          <div class="validation-header">
            <span class="validation-title">DataPackage Spec 验证</span>
            <el-button size="small" text type="primary" @click="runValidation" :loading="validating">
              {{ validation ? '重新验证' : '验证合规性' }}
            </el-button>
          </div>
          <div v-if="validation" class="validation-result">
            <div class="validation-status" :class="validation.is_valid ? 'status-pass' : 'status-fail'">
              {{ validation.is_valid ? '✅ 数据包合规' : '❌ 数据包不合规' }}
            </div>
            <div v-if="validation.errors?.length" class="val-msgs">
              <div v-for="(e, i) in validation.errors" :key="'e'+i" class="val-msg val-error">{{ e }}</div>
            </div>
            <div v-if="validation.warnings?.length" class="val-msgs">
              <div v-for="(w, i) in validation.warnings" :key="'w'+i" class="val-msg val-warn">⚠ {{ w }}</div>
            </div>
            <div v-if="validation.is_valid && !validation.warnings?.length" class="val-msg val-ok">所有检查通过，无警告</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { FolderOpened, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const emit = defineEmits(['uploaded'])

const folderPath = ref('')
const defaultPackagePath = ref('')
const loading = ref(false)
const packageInfo = ref(null)
const validation = ref(null)
const validating = ref(false)

const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

async function loadDefaultPackage() {
  folderPath.value = defaultPackagePath.value || folderPath.value
  if (!folderPath.value) {
    ElMessage.warning('未获取到默认数据包目录，请手动输入路径')
    return
  }
  await loadFolder()
}

async function loadFolder() {
  if (!folderPath.value) {
    ElMessage.warning('请输入文件夹路径')
    return
  }
  
  loading.value = true
  validation.value = null
  try {
    const res = await api.post('/upload-folder', { path: folderPath.value })
    if (res.data.success) {
      packageInfo.value = res.data.info
      ElMessage.success(res.data.message)
      // 上传响应已内含验证结果，直接展示无需额外请求
      if (res.data.validation) {
        validation.value = res.data.validation
      }
      emit('uploaded', { path: res.data.path, info: res.data.info })
    } else {
      ElMessage.error(res.data.error || '加载失败')
    }
  } catch (error) {
    ElMessage.error('加载失败: ' + (error.response?.data?.error || error.message))
  } finally {
    loading.value = false
  }
}

function handleUploadSuccess(response) {
  if (response.success) {
    ElMessage.success(response.message)
    emit('uploaded', { path: response.path })
  } else {
    ElMessage.error(response.error || '上传失败')
  }
}

function handleUploadError(error) {
  ElMessage.error('上传失败: ' + error.message)
}

async function runValidation() {
  validating.value = true
  try {
    const res = await api.post('/data-package/validate')
    if (res.data.success) {
      // 接口直接返回 is_valid/errors/warnings（无 validation 包装层）
      // 但也可能包装在 validation 字段内（API数据包场景）
      validation.value = res.data.validation ?? {
        is_valid: res.data.is_valid,
        errors: res.data.errors || [],
        warnings: res.data.warnings || []
      }
    } else {
      ElMessage.error(res.data.error || '验证失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '验证请求失败')
  } finally {
    validating.value = false
  }
}

function readIntegrationContext() {
  try {
    const raw = localStorage.getItem('integration_context')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

onMounted(async () => {
  try {
    const res = await api.get('/session/context')
    if (!res.data.success) return
    defaultPackagePath.value = res.data.defaultPackagePath || ''
    if (!folderPath.value && defaultPackagePath.value) {
      folderPath.value = defaultPackagePath.value
    }
    if (!res.data.hasDataPackage || !res.data.dataPackage) return
    const dataPackage = res.data.dataPackage
    folderPath.value = dataPackage.path || ''
    packageInfo.value = dataPackage.info || null
    if (res.data.recommendedStep !== 'upload') {
      emit('uploaded', { path: dataPackage.path, info: dataPackage.info })
    }
  } catch (error) {
    console.error('恢复上传面板会话失败:', error)
    const integrationContext = readIntegrationContext()
    if (integrationContext?.packagePath) {
      folderPath.value = integrationContext.packagePath
    }
    packageInfo.value = integrationContext.packageInfo || null
  }
})
</script>

<style scoped>
.upload-panel {
  width: 100%;
  max-width: 760px;
}

.upload-card {
  background: var(--c-bg-card);
  border-radius: var(--radius-2xl);
  padding: var(--sp-8) var(--sp-8);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--c-border-muted);
}

.card-top {
  text-align: center;
  margin-bottom: var(--sp-6);
}

.card-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-xl);
  background: var(--c-primary-light);
  color: var(--c-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--sp-3);
}

h2 {
  margin: 0 0 var(--sp-1);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--c-text-1);
}

.card-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--c-text-4);
}

.upload-sections {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.quick-load-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--text-md);
  font-weight: 600;
  font-family: var(--font-sans);
  color: var(--c-primary);
  background: var(--c-primary-light);
  border: 1.5px solid var(--c-primary-muted);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.quick-load-btn:hover {
  background: var(--c-primary-muted);
  border-color: var(--c-primary);
}
.quick-load-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.section-divider {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  color: var(--c-text-4);
  font-size: var(--text-sm);
}
.section-divider::before,
.section-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--c-border-muted);
}

.folder-input {
  display: flex;
  gap: var(--sp-2);
}
.folder-input .el-input { flex: 1; }

.upload-dragger { width: 100%; }
.upload-dragger :deep(.el-upload-dragger) {
  padding: var(--sp-6) var(--sp-4);
  border-radius: var(--radius-lg);
  border-color: var(--c-border);
  background: var(--c-bg-sunken);
  transition: all var(--duration-fast) var(--ease-default);
}
.upload-dragger :deep(.el-upload-dragger:hover) {
  border-color: var(--c-primary-muted);
  background: var(--c-primary-light);
}
.upload-dragger :deep(.el-upload__text) {
  font-size: var(--text-sm);
  color: var(--c-text-3);
}
.upload-dragger :deep(.el-upload__text em) {
  color: var(--c-primary);
}

/* ── Package Info ── */
.package-info {
  margin-top: var(--sp-5);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border-muted);
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--sp-2) var(--sp-3);
  background: var(--c-bg-sunken);
  border-radius: var(--radius-md);
}

.info-label {
  font-size: var(--text-xs);
  color: var(--c-text-4);
  font-weight: 500;
}

.info-value {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--c-text-1);
}

.variables-list {
  margin-top: var(--sp-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  align-items: center;
}

.var-label {
  font-size: var(--text-sm);
  color: var(--c-text-4);
  margin-right: var(--sp-1);
}

.var-tag {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 2px var(--sp-2);
  background: var(--c-bg-sunken);
  color: var(--c-text-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border-muted);
}

/* ── 验证区 ── */
.validation-section {
  margin-top: var(--sp-4);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border-muted);
}

.validation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);
}

.validation-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-text-2);
}

.validation-status {
  font-size: var(--text-sm);
  font-weight: 600;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--sp-2);
}

.status-pass {
  color: #065f46;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.status-fail {
  color: #991b1b;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.val-msgs {
  margin-top: var(--sp-1);
}

.val-msg {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 3px;
}

.val-error {
  color: #dc2626;
  background: #fef2f2;
}

.val-warn {
  color: #d97706;
  background: #fffbeb;
}

.val-ok {
  color: #059669;
  background: #ecfdf5;
}
</style>
