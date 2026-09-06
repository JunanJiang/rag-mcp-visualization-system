<template>
  <div class="dev-tools">
    <div class="dev-header">
      <h2 class="page-title">
        <span class="dev-icon">⚡</span>
        开发者工具
      </h2>
      <span class="dev-badge">Admin Only</span>
    </div>

    <el-tabs v-model="activeTab" class="dev-tabs">
      <!-- 数据包规范 -->
      <el-tab-pane label="数据包规范" name="spec">
        <div class="section-card">
          <div class="section-top">
            <h3>DataPackage Spec v1.0</h3>
            <el-button size="small" @click="loadSpec" :loading="loadingSpec">刷新</el-button>
          </div>
          <div v-if="spec" class="spec-content">
            <div class="spec-meta">
              <span class="spec-tag">版本 {{ spec.spec_version }}</span>
              <span class="spec-tag">必需文件: {{ spec.required_files?.join(', ') }}</span>
            </div>
            <el-collapse>
              <el-collapse-item title="manifest.json Schema" name="manifest">
                <pre class="json-block">{{ JSON.stringify(spec.schemas?.manifest, null, 2) }}</pre>
              </el-collapse-item>
              <el-collapse-item title="variables.json Schema" name="variables">
                <pre class="json-block">{{ JSON.stringify(spec.schemas?.variables, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>

        <!-- 数据包验证 -->
        <div class="section-card" style="margin-top: 16px;">
          <div class="section-top">
            <h3>数据包合规验证</h3>
            <el-button type="primary" size="small" @click="validatePackage" :loading="validating">验证当前数据包</el-button>
          </div>
          <div v-if="validation" class="validation-result">
            <el-result 
              :icon="validation.is_valid ? 'success' : 'error'" 
              :title="validation.is_valid ? '数据包合规' : '数据包不合规'"
              :sub-title="`${validation.errors?.length || 0} 个错误，${validation.warnings?.length || 0} 个警告`"
            />
            <div v-if="validation.errors?.length" class="msg-list">
              <div v-for="(e, i) in validation.errors" :key="'e'+i" class="msg-item msg-error">❌ {{ e }}</div>
            </div>
            <div v-if="validation.warnings?.length" class="msg-list">
              <div v-for="(w, i) in validation.warnings" :key="'w'+i" class="msg-item msg-warn">⚠️ {{ w }}</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 异步任务监控 -->
      <el-tab-pane label="异步任务" name="tasks">
        <div class="section-card">
          <div class="section-top">
            <h3>任务队列</h3>
            <el-button size="small" @click="loadTasks" :loading="loadingTasks">刷新</el-button>
          </div>
          <el-table :data="tasks" v-loading="loadingTasks" stripe size="small" empty-text="暂无任务">
            <el-table-column prop="task_id" label="任务ID" width="160">
              <template #default="{ row }">
                <code class="task-id">{{ row.task_id }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag 
                  :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'running' ? 'warning' : 'info'" 
                  size="small"
                >{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.progress" :stroke-width="6" :status="row.status === 'failed' ? 'exception' : row.status === 'completed' ? 'success' : ''" />
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" />
            <el-table-column prop="created_at" label="创建时间" width="180" />
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 报告模板 -->
      <el-tab-pane label="报告模板" name="templates">
        <div class="section-card">
          <div class="section-top">
            <h3>可用模板</h3>
            <el-button size="small" @click="loadTemplates" :loading="loadingTemplates">刷新</el-button>
          </div>
          <div class="template-grid">
            <div v-for="t in templates" :key="t.id" class="template-card">
              <div class="tpl-name">{{ t.name }}</div>
              <div class="tpl-id"><code>{{ t.id }}</code></div>
              <div class="tpl-desc">{{ t.description }}</div>
              <div class="tpl-meta" v-if="t.section_count">{{ t.section_count }} 个章节</div>
            </div>
          </div>
          <el-empty v-if="!templates.length && !loadingTemplates" description="暂无模板" />
        </div>
      </el-tab-pane>

      <!-- MCP 接口测试 -->
      <el-tab-pane label="MCP 接口" name="mcp">
        <div class="section-card">
          <div class="section-top">
            <h3>MCP 工具在线测试</h3>
            <el-button size="small" @click="loadMcpTools" :loading="loadingMcp">刷新工具列表</el-button>
          </div>
          <p class="mcp-hint">选择工具 → 填入参数 → 点击执行，结果实时展示。外部平台可通过 <code>POST /mcp/tools/call</code> 调用。</p>

          <div class="mcp-test-layout">
            <!-- 工具选择 -->
            <div class="mcp-tool-list">
              <div
                v-for="t in mcpTools" :key="t.name"
                class="mcp-tool-item"
                :class="{ selected: selectedMcpTool === t.name }"
                @click="selectMcpTool(t)"
              >
                <code>{{ t.name }}</code>
                <span class="mcp-tool-desc">{{ t.description?.slice(0, 40) }}</span>
              </div>
              <el-empty v-if="!mcpTools.length && !loadingMcp" description="未加载" :image-size="40" />
            </div>

            <!-- 参数 + 执行 -->
            <div class="mcp-tool-form">
              <div v-if="selectedMcpTool" class="mcp-form-inner">
                <div class="mcp-form-title">{{ selectedMcpTool }}</div>
                <el-input
                  v-model="mcpArgsJson"
                  type="textarea"
                  :rows="4"
                  placeholder='参数 JSON，如 {"query": "Plot3D"}'
                  style="margin-bottom: 12px;"
                />
                <el-button type="primary" size="small" @click="callMcpTool" :loading="callingMcp">执行</el-button>

                <!-- curl 示例 -->
                <div class="mcp-curl">
                  <div class="curl-label">curl 示例</div>
                  <pre class="curl-block">curl -X POST http://127.0.0.1:5000/mcp/tools/call \
  -H "Authorization: Bearer &lt;token&gt;" \
  -H "Content-Type: application/json" \
  -d '{"name":"{{ selectedMcpTool }}","arguments":{{ mcpArgsJson || '{}' }}}'</pre>
                </div>

                <!-- 结果 -->
                <div v-if="mcpResult !== null" class="mcp-result">
                  <div class="mcp-result-title">返回结果</div>
                  <pre class="json-block">{{ JSON.stringify(mcpResult, null, 2) }}</pre>
                </div>
              </div>
              <el-empty v-else description="请选择左侧工具" :image-size="50" />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 报告版本 -->
      <el-tab-pane label="报告历史" name="reports">
        <div class="section-card">
          <div class="section-top">
            <h3>我的报告历史</h3>
            <el-button size="small" @click="loadReports" :loading="loadingReports">刷新</el-button>
          </div>
          <el-table :data="reports" v-loading="loadingReports" stripe size="small" empty-text="暂无报告">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const activeTab = ref('spec')

// ── 数据包规范 ──
const spec = ref(null)
const loadingSpec = ref(false)
const validation = ref(null)
const validating = ref(false)

async function loadSpec() {
  loadingSpec.value = true
  try {
    const res = await api.get('/data-package/spec')
    if (res.data.success) spec.value = res.data.spec
  } catch { /* ignore */ }
  finally { loadingSpec.value = false }
}

async function validatePackage() {
  validating.value = true
  try {
    const res = await api.post('/data-package/validate')
    if (res.data.success) {
      validation.value = res.data.validation
    } else {
      ElMessage.error(res.data.error || '验证失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '验证请求失败')
  } finally { validating.value = false }
}

// ── 异步任务 ──
const tasks = ref([])
const loadingTasks = ref(false)

async function loadTasks() {
  loadingTasks.value = true
  try {
    const res = await api.get('/tasks')
    if (res.data.success) tasks.value = res.data.tasks
  } catch { /* ignore */ }
  finally { loadingTasks.value = false }
}

function statusLabel(s) {
  const m = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败' }
  return m[s] || s
}

// ── 模板 ──
const templates = ref([])
const loadingTemplates = ref(false)

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    const res = await api.get('/templates')
    if (res.data.success) templates.value = res.data.templates
  } catch { /* ignore */ }
  finally { loadingTemplates.value = false }
}

// ── MCP 接口测试 ──
const mcpTools = ref([])
const loadingMcp = ref(false)
const selectedMcpTool = ref('')
const mcpArgsJson = ref('{}')
const mcpResult = ref(null)
const callingMcp = ref(false)

async function loadMcpTools() {
  loadingMcp.value = true
  try {
    const res = await api.get('/mcp/tools/list')
    if (res.data.tools) mcpTools.value = res.data.tools
  } catch { /* ignore */ }
  finally { loadingMcp.value = false }
}

function selectMcpTool(tool) {
  selectedMcpTool.value = tool.name
  mcpArgsJson.value = '{}'
  mcpResult.value = null
}

async function callMcpTool() {
  callingMcp.value = true
  mcpResult.value = null
  try {
    let args = {}
    try { args = JSON.parse(mcpArgsJson.value || '{}') } catch { ElMessage.error('参数 JSON 格式错误'); callingMcp.value = false; return }
    const res = await api.post('/mcp/tools/call', { name: selectedMcpTool.value, arguments: args })
    mcpResult.value = res.data
  } catch (e) {
    mcpResult.value = { error: e.response?.data?.error || e.message }
  } finally { callingMcp.value = false }
}

// ── 报告历史 ──
const reports = ref([])
const loadingReports = ref(false)

async function loadReports() {
  loadingReports.value = true
  try {
    const res = await api.get('/auth/reports')
    if (res.data.success) reports.value = res.data.reports
  } catch { /* ignore */ }
  finally { loadingReports.value = false }
}

onMounted(() => {
  loadSpec()
  loadTasks()
  loadTemplates()
  loadMcpTools()
  loadReports()
})
</script>

<style scoped>
.dev-tools {
  padding: 24px 32px;
  max-width: 1100px;
  margin: 0 auto;
}

.dev-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dev-icon { font-size: 22px; }

.dev-badge {
  font-size: 11px;
  font-weight: 600;
  color: #7c3aed;
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  padding: 3px 12px;
  border-radius: 20px;
}

.section-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.section-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-top h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}

.spec-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.spec-tag {
  font-size: 12px;
  padding: 2px 10px;
  background: #f3f4f6;
  border-radius: 6px;
  color: #6b7280;
}

.json-block {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 300px;
  color: #374151;
}

.validation-result {
  text-align: center;
}

.msg-list {
  text-align: left;
  margin-top: 8px;
}

.msg-item {
  padding: 6px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  font-size: 13px;
}

.msg-error {
  background: #fef2f2;
  color: #dc2626;
}

.msg-warn {
  background: #fffbeb;
  color: #d97706;
}

.task-id {
  font-size: 11px;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 4px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.template-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  background: #fafafa;
  transition: border-color 0.2s;
}

.template-card:hover {
  border-color: #7c3aed;
}

.tpl-name {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
}

.tpl-id {
  margin-bottom: 8px;
}

.tpl-id code {
  font-size: 11px;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 4px;
  color: #7c3aed;
}

.tpl-desc {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.4;
}

.tpl-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}

.dev-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

/* ── MCP 接口测试 ── */
.mcp-hint {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 16px;
  line-height: 1.5;
}
.mcp-hint code {
  font-size: 12px;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 4px;
  color: #7c3aed;
}
.mcp-test-layout {
  display: flex;
  gap: 16px;
  min-height: 320px;
}
.mcp-tool-list {
  width: 220px;
  min-width: 220px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow-y: auto;
  max-height: 400px;
  background: #fafafa;
}
.mcp-tool-item {
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f6;
  transition: background 0.15s;
}
.mcp-tool-item:hover { background: #eff6ff; }
.mcp-tool-item.selected {
  background: #eff6ff;
  border-left: 3px solid #2563eb;
}
.mcp-tool-item code {
  font-size: 11px;
  color: #7c3aed;
  display: block;
  font-weight: 600;
}
.mcp-tool-desc {
  font-size: 11px;
  color: #9ca3af;
  display: block;
  margin-top: 2px;
}
.mcp-tool-form {
  flex: 1;
  min-width: 0;
}
.mcp-form-inner {
  padding: 0;
}
.mcp-form-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 12px;
  font-family: monospace;
}
.mcp-curl {
  margin-top: 16px;
  background: #1e293b;
  border-radius: 8px;
  padding: 12px 16px;
}
.curl-label {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 6px;
  font-weight: 600;
}
.curl-block {
  font-size: 11px;
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  margin: 0;
}
.mcp-result {
  margin-top: 16px;
}
.mcp-result-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}
</style>
