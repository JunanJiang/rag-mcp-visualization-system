<template>
  <div class="app-shell">
    <!-- ===== 顶部菜单栏 ===== -->
    <header class="titlebar">
      <div class="titlebar-left">
        <div class="app-logo">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <span class="app-name">SimuVision Suite</span>
        <nav class="menu-bar">
          <span class="menu-item">文件</span>
          <span class="menu-item">编辑</span>
          <span class="menu-item">视图</span>
          <span class="menu-item">仿真</span>
          <span class="menu-item">工具</span>
          <span class="menu-item">帮助</span>
        </nav>
      </div>
      <div class="titlebar-right">
        <span v-if="sessionState.loggedIn && sessionState.user" class="user-pill">
          <el-icon><User /></el-icon>
          {{ sessionState.user.display_name || sessionState.user.username }}
        </span>
      </div>
    </header>

    <!-- ===== 工具栏 ===== -->
    <div class="toolbar">
      <div class="toolbar-group">
        <button class="tb-btn" title="新建项目"><el-icon><FolderAdd /></el-icon></button>
        <button class="tb-btn" title="打开"><el-icon><FolderOpened /></el-icon></button>
        <button class="tb-btn" title="保存"><el-icon><Document /></el-icon></button>
        <span class="tb-sep"></span>
        <button class="tb-btn" title="求解器"><el-icon><Cpu /></el-icon></button>
        <button class="tb-btn" title="网格"><el-icon><Grid /></el-icon></button>
        <button class="tb-btn" title="后处理"><el-icon><Histogram /></el-icon></button>
        <span class="tb-sep"></span>
        <button class="tb-btn tb-highlight" :class="{ active: pluginOpen }" title="SimuReport 智能可视化" @click="pluginOpen = !pluginOpen">
          <el-icon><MagicStick /></el-icon>
          <span>智能可视化</span>
        </button>
      </div>
      <div class="toolbar-status">
        <el-tag size="small" :type="healthOk ? 'success' : 'info'" effect="plain">
          {{ healthOk ? 'SimuReport 已连接' : 'SimuReport 未连接' }}
        </el-tag>
      </div>
    </div>

    <!-- ===== 主工作区 ===== -->
    <div class="workspace">
      <!-- 仿真视口（背景） -->
      <div class="viewport">
        <div class="viewport-grid"></div>
        <div class="viewport-content">
          <div class="viewport-axes">
            <span class="axis-x">X</span>
            <span class="axis-y">Y</span>
            <span class="axis-z">Z</span>
          </div>
          <div class="viewport-label">
            <el-icon><Grid /></el-icon>
            <span>CFD Mesh — 3D Viewport</span>
          </div>
          <div class="viewport-hint" v-if="!pluginOpen">
            点击工具栏 <strong>「智能可视化」</strong> 按钮打开 SimuReport 插件面板
          </div>
        </div>
        <div class="viewport-statusbar">
          <span>面数: 128,406</span>
          <span>节点: 65,203</span>
          <span>单元类型: Hexahedral</span>
          <span>视角: Perspective</span>
        </div>
      </div>

      <!-- ===== SimuReport 插件面板（右侧抽屉） ===== -->
      <transition name="slide">
        <aside v-if="pluginOpen" class="plugin-panel">
          <div class="plugin-header">
            <div class="plugin-title">
              <el-icon><MagicStick /></el-icon>
              <span>SimuReport</span>
            </div>
            <button class="plugin-close" @click="pluginOpen = false">&times;</button>
          </div>

          <!-- 未登录：登录表单 -->
          <div v-if="!sessionState.loggedIn" class="plugin-section">
            <div class="section-title">账号登录</div>
            <div class="pform">
              <el-input v-model="loginForm.username" placeholder="请输入账号" prefix-icon="User" />
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" prefix-icon="Lock" />
              <el-button type="primary" :loading="loggingIn" @click="loginToGraduation" style="width:100%">登录</el-button>
            </div>
          </div>

          <!-- 已登录：用户信息 -->
          <div v-else class="plugin-section">
            <div class="user-card">
              <div class="user-avatar">{{ (sessionState.user?.display_name || sessionState.user?.username || '?').slice(0,1) }}</div>
              <div>
                <div class="user-name">{{ sessionState.user?.display_name || sessionState.user?.username }}</div>
                <div class="user-role">{{ sessionState.user?.role === 'admin' ? '管理员' : '普通用户' }}</div>
              </div>
              <el-button size="small" text class="logout-btn" @click="logout">退出</el-button>
            </div>
            </div>

          <!-- 已登录后的操作区 -->
          <template v-if="sessionState.loggedIn">
            <div class="plugin-panels">
              <section class="plugin-fold" :class="{ collapsed: upperPanelCollapsed }">
                <div class="plugin-fold-header">
                  <div>
                    <div class="plugin-fold-title">工程与生成</div>
                    <div class="plugin-fold-subtitle">工程接入、报告生成与下载</div>
                  </div>
                  <button class="plugin-fold-toggle" @click="upperPanelCollapsed = !upperPanelCollapsed">{{ upperPanelCollapsed ? '展开' : '收起' }}</button>
                </div>
                <div v-show="!upperPanelCollapsed" class="plugin-fold-body plugin-fold-scroll">
                  <!-- 数据包上传 -->
                  <div class="plugin-section">
                    <div class="section-title">当前工程</div>
                    <div class="project-card">
                      <div class="project-card-header">
                        <div class="project-card-main">
                          <div class="project-name">{{ currentProjectName }}</div>
                          <div class="project-subtitle">{{ projectSubtitle }}</div>
                        </div>
                        <el-tag size="small" :type="projectImported ? 'success' : 'info'" effect="plain">
                          {{ projectImported ? '已导入' : '待导入' }}
                        </el-tag>
                      </div>
                      <div class="project-meta">
                        <div class="project-meta-row">
                          <span>工程来源</span>
                          <strong>当前仿真工程</strong>
                        </div>
                        <div class="project-meta-row project-path-row">
                          <span>数据目录</span>
                          <strong :title="resolvedPackagePath || '未配置'">{{ resolvedPackagePath || '未配置' }}</strong>
                        </div>
                      </div>
                    </div>
                    <div class="pform">
                      <el-button type="primary" size="small" :loading="uploading" :disabled="!resolvedPackagePath" @click="uploadPackage" style="width:100%">
                        <el-icon><Upload /></el-icon> {{ projectImported ? '重新导入当前工程' : '导入当前工程' }}
                      </el-button>
                      <el-button size="small" @click="showAdvancedPackage = !showAdvancedPackage" style="width:100%">
                        <el-icon><FolderOpened /></el-icon> {{ showAdvancedPackage ? '收起高级设置' : '高级设置' }}
                      </el-button>
                    </div>
                    <div v-if="showAdvancedPackage" class="advanced-panel">
                      <div class="advanced-tip">如需切换演示案例，可在此调整当前工程对应的数据目录。</div>
                      <el-input v-model="packagePath" placeholder="请输入或粘贴数据包路径" size="small" />
                    </div>
                    <div v-if="sessionState.packageInfo" class="pkg-summary">
                      <div class="pkg-row"><span>类型</span><strong>{{ sessionState.packageInfo.datasetType }}</strong></div>
                      <div class="pkg-row"><span>网格块</span><strong>{{ sessionState.packageInfo.blockCount }}</strong></div>
                      <div class="pkg-row"><span>节点</span><strong>{{ formatNumber(sessionState.packageInfo.totalPoints) }}</strong></div>
                      <div class="pkg-row"><span>变量</span><strong>{{ sessionState.packageInfo.variableCount }}</strong></div>
                    </div>
                  </div>

                  <!-- 报告生成 -->
                  <div class="plugin-section">
                    <div class="section-title">报告生成</div>
                    <div class="action-btns">
                      <el-button type="primary" :disabled="!canUseAi" :loading="workflowRunning" @click="runOneClickReport" style="width:100%">
                        <el-icon><MagicStick /></el-icon> 通过 MCP 一键生成报告
                      </el-button>
                      <el-button :disabled="!sessionState.loggedIn" @click="openGraduationWeb" style="width:100%">
                        <el-icon><TopRight /></el-icon> 打开网页端
                      </el-button>
                    </div>
                  </div>

                  <div class="plugin-section">
                    <div class="section-title">MCP 对外集成</div>
                    <div class="mcp-overview">
                      <div class="mcp-stat-card">
                        <strong>{{ mcpTools.length }}</strong>
                        <span>已发现工具</span>
                      </div>
                      <div class="mcp-stat-card">
                        <strong>{{ recentMcpCalls.length }}</strong>
                        <span>最近调用</span>
                      </div>
                    </div>
                    <div v-if="mcpToolsLoading" class="mcp-empty">正在读取 MCP 工具目录…</div>
                    <div v-else-if="mcpTools.length" class="mcp-tool-cloud">
                      <button
                        v-for="tool in mcpTools"
                        :key="tool.name"
                        class="mcp-tool-chip"
                        :class="{ active: selectedToolName === tool.name }"
                        @click="selectTool(tool)"
                      >
                        {{ tool.name }}
                      </button>
                    </div>
                    <div v-else class="mcp-empty">登录后可从主系统发现可调用的 MCP 工具。</div>

                    <div v-if="selectedMcpTool" class="mcp-tool-card">
                      <div class="mcp-tool-card-title">{{ selectedMcpTool.name }}</div>
                      <div class="mcp-tool-card-desc">{{ selectedMcpTool.description || '该工具未提供额外说明。' }}</div>
                      <pre class="mcp-schema">{{ selectedToolSchemaText }}</pre>
                    </div>
                  </div>

                  <!-- 报告下载 -->
                  <div v-if="lastWorkflow.outputDir" class="plugin-section">
                    <div class="section-title">报告下载</div>
                    <div class="download-grid">
                      <el-button size="small" @click="downloadReport('docx')">Word文档</el-button>
                      <el-button size="small" @click="downloadReport('md')">Markdown</el-button>
                      <el-button size="small" @click="downloadReport('pdf')">PDF</el-button>
                      <el-button size="small" @click="downloadReport('draft')">Draft</el-button>
                    </div>
                  </div>

                  <div class="plugin-section">
                    <div class="section-title">MCP 调用链</div>
                    <div v-if="!recentMcpCalls.length" class="mcp-empty">外部系统尚未产生 MCP 工具调用。</div>
                    <div v-else class="mcp-history">
                      <div v-for="entry in recentMcpCalls" :key="entry.id" class="mcp-history-item" :class="entry.status">
                        <div class="mcp-history-head">
                          <div class="mcp-history-title">
                            <span class="mcp-history-tool">{{ entry.tool }}</span>
                            <span class="mcp-history-source">{{ formatMcpSource(entry.source) }}</span>
                          </div>
                          <span class="mcp-history-status">{{ formatMcpStatus(entry.status) }}</span>
                        </div>
                        <div v-if="entry.note" class="mcp-history-note">{{ entry.note }}</div>
                        <div class="mcp-history-block">
                          <span>args</span>
                          <code>{{ entry.argsText || '{}' }}</code>
                        </div>
                        <div class="mcp-history-block">
                          <span>result</span>
                          <code>{{ entry.resultText || '处理中…' }}</code>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <!-- AI 对话 -->
              <section class="plugin-fold plugin-fold-chat" :class="{ collapsed: chatPanelCollapsed }">
                <div class="plugin-fold-header">
                  <div>
                    <div class="plugin-fold-title">AI 助手</div>
                    <div class="plugin-fold-subtitle">对工程问题进行分析与答复</div>
                  </div>
                  <button class="plugin-fold-toggle" @click="chatPanelCollapsed = !chatPanelCollapsed">{{ chatPanelCollapsed ? '展开' : '收起' }}</button>
                </div>
                <div v-show="!chatPanelCollapsed" class="plugin-fold-body plugin-fold-chat-body">
                  <div class="plugin-section plugin-chat-section">
                    <div class="mini-chat">
                      <div class="mini-messages" ref="messageListRef">
                        <div v-for="message in messages" :key="message.id" class="mini-msg" :class="[message.role, { rich: message.role === 'assistant' }]">
                          <div v-if="message.role === 'assistant'" class="mini-msg-text" v-html="formatAssistantMessage(message.content)"></div>
                          <div v-else class="mini-msg-text" v-html="formatPlainMessage(message.content)"></div>
                          <div v-if="message.tools?.length" class="mini-tools">
                            <span v-for="(tool, i) in message.tools" :key="i">{{ tool.tool }}</span>
                          </div>
                        </div>
                      </div>
                      <div class="mini-composer">
                        <el-input v-model="chatInput" size="small" placeholder="输入问题..." @keyup.enter="sendChat" />
                        <el-button type="primary" size="small" :loading="chatting" :disabled="!canUseAi" @click="sendChat">发送</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </template>
        </aside>
      </transition>
    </div>

    <!-- ===== 底部状态栏 ===== -->
    <footer class="statusbar">
      <span>SimuVision Suite v4.2.1</span>
      <span>项目: {{ currentProjectName }}</span>
      <span>求解器: 空闲</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, DataAnalysis, Document, DocumentAdd, FolderAdd, FolderOpened, Grid, Histogram, Link, Lock, MagicStick, TopRight, Upload, User } from '@element-plus/icons-vue'
import api from './api'

const healthOk = ref(false)
const pluginOpen = ref(false)
const savingConfig = ref(false)
const loggingIn = ref(false)
const uploading = ref(false)
const chatting = ref(false)
const workflowRunning = ref(false)
const mcpToolsLoading = ref(false)
const messageListRef = ref(null)
const showAdvancedPackage = ref(false)
const upperPanelCollapsed = ref(false)
const chatPanelCollapsed = ref(false)

const config = ref({
  coreBackendBase: 'http://127.0.0.1:5000',
  coreFrontendBase: 'http://localhost:3001'
})

const loginForm = ref({
  username: '',
  password: ''
})

const sessionState = ref({
  loggedIn: false,
  user: null,
  packagePath: '',
  packageInfo: null,
  lastOutputDir: ''
})

const packagePath = ref('')
const chatInput = ref('')
const chatApiKey = ref('')
const lastWorkflow = ref({ outputDir: '' })
const mcpTools = ref([])
const mcpCallHistory = ref([])
const selectedToolName = ref('')
const messages = ref([
  {
    id: 'welcome',
    role: 'assistant',
    content: '您好，欢迎使用 SimuReport 智能报告助手。请先登录并导入当前工程。当前演示会显式发现 MCP 工具、展示调用链，并用 MCP 工具编排报告生成过程。',
    tools: []
  }
])

const canUseAi = ref(false)
const resolvedPackagePath = computed(() => {
  return String(packagePath.value || '').trim()
})
const projectImported = computed(() => {
  const importedPath = String(sessionState.value.packagePath || '').trim()
  return !!sessionState.value.packageInfo && !!resolvedPackagePath.value && importedPath === resolvedPackagePath.value
})
const currentProjectName = computed(() => {
  const normalized = resolvedPackagePath.value.replace(/\\/g, '/').split('/').filter(Boolean)
  const lastPart = normalized[normalized.length - 1] || ''
  if (!lastPart || lastPart === '数据包') return 'Plot3D_BackStep_Demo'
  return lastPart
})
const projectSubtitle = computed(() => {
  if (!resolvedPackagePath.value) return '请在高级设置中指定当前工程的数据目录。'
  if (projectImported.value) return '当前工程已接入 SimuReport，可直接继续生成或打开网页端。'
  return '已识别当前工程的标准数据目录，可一键导入到 SimuReport。'
})
const recentMcpCalls = computed(() => mcpCallHistory.value.slice(0, 8))
const selectedMcpTool = computed(() => mcpTools.value.find(tool => tool.name === selectedToolName.value) || null)
const selectedToolSchemaText = computed(() => {
  if (!selectedMcpTool.value?.inputSchema) return '{}'
  return JSON.stringify(selectedMcpTool.value.inputSchema, null, 2)
})

function formatNumber(value) {
  if (value === undefined || value === null || value === '') return '--'
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString() : String(value)
}

function prettyJson(value) {
  if (value === undefined || value === null || value === '') return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function previewJson(value, limit = 260) {
  const text = prettyJson(value)
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

function formatMcpSource(source) {
  if (source === 'workflow') return '一键生成'
  if (source === 'chat') return 'AI 对话'
  return 'MCP'
}

function formatMcpStatus(status) {
  if (status === 'success') return '成功'
  if (status === 'error') return '失败'
  return '执行中'
}

function ensureToolBadge(message, toolName) {
  if (!toolName) return
  if (!Array.isArray(message.tools)) message.tools = []
  if (!message.tools.some(item => item.tool === toolName)) {
    message.tools.push({ tool: toolName })
  }
}

function selectTool(tool) {
  const toolName = typeof tool === 'string' ? tool : tool?.name
  if (!toolName) return
  selectedToolName.value = toolName
}

function addMcpCallStart(source, tool, args = {}, note = '') {
  mcpCallHistory.value.unshift({
    id: `${source}-${tool}-${Date.now()}-${Math.random()}`,
    source,
    tool,
    status: 'running',
    note,
    argsText: previewJson(args) || '{}',
    resultText: '',
  })
}

function settleMcpCall(source, tool, result = {}, note = '') {
  const target = mcpCallHistory.value.find(item => item.source === source && item.tool === tool && item.status === 'running')
  const isError = !!(result && typeof result === 'object' && result.error)
  if (target) {
    target.status = isError ? 'error' : 'success'
    target.note = note || target.note
    target.resultText = previewJson(result) || (isError ? '调用失败' : '调用成功')
    return
  }
  mcpCallHistory.value.unshift({
    id: `${source}-${tool}-${Date.now()}-${Math.random()}`,
    source,
    tool,
    status: isError ? 'error' : 'success',
    note,
    argsText: '{}',
    resultText: previewJson(result) || (isError ? '调用失败' : '调用成功'),
  })
}

function failMcpCall(source, tool, errorMessage, note = '') {
  const target = mcpCallHistory.value.find(item => item.source === source && item.tool === tool && item.status === 'running')
  if (target) {
    target.status = 'error'
    target.note = note || target.note
    target.resultText = String(errorMessage || '调用失败')
    return
  }
  mcpCallHistory.value.unshift({
    id: `${source}-${tool || 'unknown'}-${Date.now()}-${Math.random()}`,
    source,
    tool: tool || 'unknown',
    status: 'error',
    note,
    argsText: '{}',
    resultText: String(errorMessage || '调用失败'),
  })
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatInlineMarkdown(value) {
  let html = escapeHtml(value)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>')
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>')
  html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  return html
}

function formatPlainMessage(value) {
  return escapeHtml(value).replace(/\n/g, '<br>')
}

function formatAssistantMessage(value) {
  const lines = String(value ?? '').replace(/\r\n/g, '\n').split('\n')
  const parts = []
  let paragraphLines = []
  let codeLines = []
  let inCodeBlock = false

  const flushParagraph = () => {
    if (!paragraphLines.length) return
    parts.push(`<p class="msg-paragraph">${paragraphLines.map(line => formatInlineMarkdown(line)).join('<br>')}</p>`)
    paragraphLines = []
  }

  const flushCode = () => {
    parts.push(`<pre class="msg-code"><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
    codeLines = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (/^```/.test(trimmed)) {
      flushParagraph()
      if (inCodeBlock) {
        flushCode()
        inCodeBlock = false
      } else {
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    if (!trimmed) {
      flushParagraph()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      flushParagraph()
      parts.push(`<div class="msg-heading msg-heading-${headingMatch[1].length}">${formatInlineMarkdown(headingMatch[2])}</div>`)
      continue
    }

    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (orderedMatch) {
      flushParagraph()
      parts.push(`<div class="msg-list-item msg-list-numbered"><span class="msg-bullet">${orderedMatch[1]}.</span><span>${formatInlineMarkdown(orderedMatch[2])}</span></div>`)
      continue
    }

    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/)
    if (bulletMatch) {
      flushParagraph()
      parts.push(`<div class="msg-list-item"><span class="msg-bullet">•</span><span>${formatInlineMarkdown(bulletMatch[1])}</span></div>`)
      continue
    }

    paragraphLines.push(line)
  }

  flushParagraph()
  if (inCodeBlock) {
    flushCode()
  }

  return parts.join('') || '<p class="msg-paragraph">AI 已完成本轮分析。</p>'
}

function pushAssistantMessage(content, tools = []) {
  messages.value.push({
    id: `assistant-${Date.now()}-${Math.random()}`,
    role: 'assistant',
    content,
    tools
  })
}

function pushUserMessage(content) {
  messages.value.push({
    id: `user-${Date.now()}-${Math.random()}`,
    role: 'user',
    content,
    tools: []
  })
}

async function scrollToBottom() {
  await nextTick()
  const el = messageListRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

async function refreshSession() {
  const [configRes, authRes] = await Promise.all([
    api.get('/config'),
    api.get('/auth/session')
  ])
  if (configRes.data.success) {
    config.value = {
      coreBackendBase: configRes.data.coreBackendBase,
      coreFrontendBase: configRes.data.coreFrontendBase
    }
    packagePath.value = configRes.data.packagePath || configRes.data.defaultPackagePath || ''
  }
  if (authRes.data.success) {
    sessionState.value = {
      loggedIn: !!authRes.data.loggedIn,
      user: authRes.data.user,
      packagePath: authRes.data.packagePath || '',
      packageInfo: authRes.data.packageInfo || null,
      lastOutputDir: authRes.data.lastOutputDir || ''
    }
    canUseAi.value = !!(sessionState.value.loggedIn && sessionState.value.packageInfo)
    lastWorkflow.value.outputDir = authRes.data.lastOutputDir || ''
    if (sessionState.value.loggedIn) {
      await loadMcpTools()
    } else {
      mcpTools.value = []
      selectedToolName.value = ''
    }
  }
}

async function loadMcpTools() {
  if (!sessionState.value.loggedIn) {
    mcpTools.value = []
    return
  }
  mcpToolsLoading.value = true
  try {
    const res = await api.get('/mcp/tools/list')
    if (res.data.success) {
      mcpTools.value = res.data.tools || []
      if (!selectedToolName.value || !mcpTools.value.some(tool => tool.name === selectedToolName.value)) {
        if (mcpTools.value[0]?.name) selectTool(mcpTools.value[0])
      }
    }
  } catch (error) {
    mcpTools.value = []
    ElMessage.error(error.response?.data?.error || error.message || '读取 MCP 工具列表失败')
  } finally {
    mcpToolsLoading.value = false
  }
}

async function checkHealth() {
  try {
    const res = await api.get('/health')
    healthOk.value = !!res.data.success
  } catch {
    healthOk.value = false
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    const res = await api.post('/config', config.value)
    if (res.data.success) {
      ElMessage.success('接入配置已保存')
      await refreshSession()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || '保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

async function loginToGraduation() {
  loggingIn.value = true
  try {
    const res = await api.post('/auth/login', loginForm.value)
    if (res.data.success) {
      ElMessage.success('已登录 SimuReport 系统')
      await refreshSession()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || '登录失败')
  } finally {
    loggingIn.value = false
  }
}

async function logout() {
  try {
    await api.post('/auth/logout')
    ElMessage.success('已退出')
    await refreshSession()
    lastWorkflow.value = { outputDir: '' }
    mcpTools.value = []
    mcpCallHistory.value = []
    selectedToolName.value = ''
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || '退出失败')
  }
}

async function uploadPackage() {
  const targetPath = resolvedPackagePath.value
  if (!targetPath) {
    ElMessage.warning('请先配置当前工程的数据目录')
    return
  }
  uploading.value = true
  try {
    const res = await api.post('/package/upload-path', { path: targetPath })
    if (res.data.success) {
      ElMessage.success('当前工程已导入到 SimuReport 系统')
      await refreshSession()
      pushAssistantMessage(`当前工程已接入 SimuReport 系统：${res.data.path}`)
      await scrollToBottom()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function openGraduationWeb() {
  try {
    const res = await api.get('/web/open-link')
    if (res.data.success && res.data.url) {
      window.open(res.data.url, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || '打开网页端失败')
  }
}

async function runOneClickReport() {
  workflowRunning.value = true
  pushUserMessage('请通过 MCP 工具链一键生成可视化报告')
  const assistant = {
    id: `assistant-${Date.now()}-${Math.random()}`,
    role: 'assistant',
    content: '外部系统正在发现 MCP 工具并编排调用链...',
    tools: []
  }
  messages.value.push(assistant)
  await scrollToBottom()

  try {
    const resp = await fetch('/api/workflow/one-click-stream', {
      method: 'POST',
      credentials: 'include'
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`请求失败: ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''

      for (const block of blocks) {
        const line = block.split('\n').find(item => item.startsWith('data:'))
        if (!line) continue
        const raw = line.replace(/^data:\s*/, '')
        if (!raw) continue
        let evt
        try {
          evt = JSON.parse(raw)
        } catch {
          continue
        }

        if (evt.type === 'tool_catalog') {
          assistant.content = `已发现 ${evt.count || 0} 个 MCP 工具，开始按工具链编排执行。`
        } else if (evt.type === 'progress') {
          assistant.content = evt.message || '处理中...'
        } else if (evt.type === 'tool_call') {
          const toolName = evt.name || evt.tool || 'workflow'
          ensureToolBadge(assistant, toolName)
          addMcpCallStart('workflow', toolName, evt.args || {}, evt.message || '外部系统编排 MCP 工具')
        } else if (evt.type === 'tool_result') {
          settleMcpCall('workflow', evt.name || evt.tool || 'workflow', evt.content || {}, evt.message || '外部系统编排 MCP 工具')
        } else if (evt.type === 'done') {
          assistant.content = evt.message || '报告已自动生成完成'
          if (evt.output_dir) {
            lastWorkflow.value.outputDir = evt.output_dir
          }
          ;(evt.tool_chain || []).forEach(toolName => ensureToolBadge(assistant, toolName))
        } else if (evt.type === 'error') {
          failMcpCall('workflow', evt.tool || 'workflow', evt.error || '自动工作流失败', '外部系统编排 MCP 工具')
          throw new Error(evt.error || '自动工作流失败')
        }
        await scrollToBottom()
      }
    }

    await refreshSession()
    ElMessage.success('报告已由 SimuReport 系统生成完成')
  } catch (error) {
    assistant.content = `一键生成失败：${error.message || error}`
    ElMessage.error(error.message || '一键生成失败')
  } finally {
    workflowRunning.value = false
    await scrollToBottom()
  }
}

async function sendChat() {
  if (!chatInput.value.trim()) return
  const content = chatInput.value.trim()
  pushUserMessage(content)
  chatInput.value = ''
  const assistant = {
    id: `assistant-${Date.now()}-${Math.random()}`,
    role: 'assistant',
    content: '',
    tools: []
  }
  messages.value.push(assistant)
  chatting.value = true
  await scrollToBottom()

  try {
    const historyMessages = messages.value
      .filter(item => item.id !== assistant.id)
      .filter(item => item.role === 'user' || item.role === 'assistant')
      .map(item => ({ role: item.role, content: item.content }))

    const payload = {
      messages: historyMessages,
      apiKey: chatApiKey.value || undefined,
      webSearchEnabled: false
    }

    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(payload)
    })

    if (!resp.ok || !resp.body) {
      throw new Error(`请求失败: ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''

      for (const block of blocks) {
        const line = block.split('\n').find(item => item.startsWith('data:'))
        if (!line) continue
        const raw = line.replace(/^data:\s*/, '')
        if (!raw) continue
        let evt
        try {
          evt = JSON.parse(raw)
        } catch {
          continue
        }

        if (evt.type === 'delta') {
          assistant.content += evt.content || ''
        } else if (evt.type === 'tool_call') {
          const toolName = evt.tool || 'tool'
          ensureToolBadge(assistant, toolName)
          addMcpCallStart('chat', toolName, evt.args || {}, 'AI 通过 MCP 调用工具')
        } else if (evt.type === 'done') {
          ;(evt.tool_calls || []).forEach(call => {
            ensureToolBadge(assistant, call.tool)
            settleMcpCall('chat', call.tool, call.result || {}, call.action || 'AI 通过 MCP 调用工具')
          })
          if (evt.workflow_result?.output_dir) {
            lastWorkflow.value.outputDir = evt.workflow_result.output_dir
          }
        } else if (evt.type === 'error') {
          failMcpCall('chat', 'tool', evt.error || 'AI 对话失败', 'AI 通过 MCP 调用工具')
          throw new Error(evt.error || 'AI 对话失败')
        }
        await scrollToBottom()
      }
    }

    if (!assistant.content.trim()) {
      assistant.content = 'AI 已完成本轮分析。'
    }
    await refreshSession()
  } catch (error) {
    assistant.content = `AI 对话失败：${error.message || error}`
    ElMessage.error(error.message || 'AI 对话失败')
  } finally {
    chatting.value = false
    await scrollToBottom()
  }
}

async function downloadReport(type) {
  try {
    const response = await fetch(`/api/report/download/${type}?dir=${encodeURIComponent(lastWorkflow.value.outputDir || '')}`, {
      credentials: 'include'
    })
    if (!response.ok) {
      throw new Error(`下载失败: ${response.status}`)
    }
    const blob = await response.blob()
    const nameMap = { docx: 'report.docx', md: 'report.md', draft: 'draft.json', pdf: 'report.pdf' }
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = nameMap[type] || 'download'
    anchor.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error.message || '下载失败')
  }
}

onMounted(async () => {
  await checkHealth()
  await refreshSession()
  await scrollToBottom()
})
</script>

<style scoped>
/* ── 全局壳 ── */
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1e1e2e;
  color: #cdd6f4;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  overflow: hidden;
}

/* ── 标题栏 ── */
.titlebar {
  height: 36px;
  background: #181825;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid #313244;
  flex-shrink: 0;
}
.titlebar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.app-logo {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  color: #89b4fa; font-size: 16px;
}
.app-name {
  font-size: 13px; font-weight: 700; color: #cdd6f4;
  margin-right: 16px;
}
.menu-bar {
  display: flex; gap: 2px;
}
.menu-item {
  padding: 4px 10px; border-radius: 4px; font-size: 12px; color: #a6adc8;
  cursor: default; user-select: none;
}
.menu-item:hover { background: #313244; color: #cdd6f4; }
.titlebar-right { display: flex; align-items: center; gap: 10px; }
.user-pill {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: #a6adc8;
  padding: 2px 10px; border-radius: 999px;
  background: rgba(137,180,250,0.1);
}

/* ── 工具栏 ── */
.toolbar {
  height: 42px; background: #1e1e2e;
  border-bottom: 1px solid #313244;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 12px; flex-shrink: 0;
}
.toolbar-group { display: flex; align-items: center; gap: 2px; }
.toolbar-status { display: flex; align-items: center; }
.tb-btn {
  border: none; outline: none; background: transparent; color: #a6adc8;
  height: 32px; padding: 0 10px; border-radius: 6px;
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 13px; cursor: pointer; transition: 0.15s;
}
.tb-btn:hover { background: #313244; color: #cdd6f4; }
.tb-highlight {
  color: #89b4fa; font-weight: 600;
}
.tb-highlight.active {
  background: rgba(137,180,250,0.15);
  color: #89b4fa;
  box-shadow: inset 0 -2px 0 #89b4fa;
}
.tb-sep {
  width: 1px; height: 20px; background: #313244; margin: 0 6px;
}

/* ── 工作区 ── */
.workspace {
  flex: 1; display: flex; overflow: hidden; position: relative;
}

/* ── 3D 视口 ── */
.viewport {
  flex: 1; position: relative; overflow: hidden;
  background: #11111b;
}
.viewport-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(69,71,90,0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(69,71,90,0.18) 1px, transparent 1px);
  background-size: 40px 40px;
}
.viewport-content {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.viewport-axes {
  position: absolute; bottom: 60px; left: 24px;
  display: flex; flex-direction: column; gap: 2px; font-size: 11px; font-weight: 700;
}
.axis-x { color: #f38ba8; }
.axis-y { color: #a6e3a1; }
.axis-z { color: #89b4fa; }
.viewport-label {
  display: flex; align-items: center; gap: 8px;
  color: #585b70; font-size: 14px; user-select: none;
}
.viewport-hint {
  margin-top: 20px; padding: 14px 24px; border-radius: 10px;
  background: rgba(49,50,68,0.7); color: #a6adc8; font-size: 13px;
  backdrop-filter: blur(6px);
}
.viewport-statusbar {
  position: absolute; bottom: 0; left: 0; right: 0;
  height: 26px; background: rgba(24,24,37,0.85);
  display: flex; align-items: center; gap: 20px;
  padding: 0 14px; font-size: 11px; color: #585b70;
}

/* ── 插件面板 ── */
.plugin-panel {
  width: 430px; flex-shrink: 0;
  background: #1e1e2e;
  border-left: 1px solid #313244;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.plugin-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid #313244;
  flex-shrink: 0;
}
.plugin-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 700; color: #89b4fa;
}
.plugin-close {
  border: none; background: transparent; color: #6c7086;
  font-size: 20px; cursor: pointer; line-height: 1;
  padding: 2px 6px; border-radius: 4px;
}
.plugin-close:hover { background: #313244; color: #cdd6f4; }

.plugin-section {
  padding: 14px 16px;
  border-bottom: 1px solid #313244;
}
.plugin-panels {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  overflow: hidden;
}
.plugin-fold {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #313244;
  border-radius: 12px;
  background: rgba(17, 17, 27, 0.72);
  overflow: hidden;
}
.plugin-fold.collapsed {
  flex: 0 0 auto;
}
.plugin-fold-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: rgba(30, 30, 46, 0.95);
  border-bottom: 1px solid #313244;
}
.plugin-fold.collapsed .plugin-fold-header {
  border-bottom: 0;
}
.plugin-fold-title {
  font-size: 13px;
  font-weight: 700;
  color: #cdd6f4;
}
.plugin-fold-subtitle {
  margin-top: 2px;
  font-size: 11px;
  color: #6c7086;
}
.plugin-fold-toggle {
  border: 1px solid #45475a;
  background: #313244;
  color: #cdd6f4;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
}
.plugin-fold-toggle:hover {
  background: #3b3f56;
}
.plugin-fold-body {
  min-height: 0;
}
.plugin-fold-scroll {
  overflow-y: auto;
}
.plugin-fold-chat {
  flex: 1;
}
.plugin-fold-chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.section-title {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: #6c7086; margin-bottom: 10px;
}
.pform {
  display: flex; flex-direction: column; gap: 8px;
}

.pform :deep(.el-input),
.pform :deep(.el-button),
.action-btns :deep(.el-button),
.mini-composer :deep(.el-button),
.download-grid :deep(.el-button) {
  width: 100%;
}

.plugin-panel :deep(.el-input__wrapper) {
  background: #11111b;
  box-shadow: 0 0 0 1px #313244 inset;
}

.plugin-panel :deep(.el-input__inner) {
  color: #cdd6f4;
}

.plugin-panel :deep(.el-input__inner::placeholder) {
  color: #6c7086;
}

.plugin-panel :deep(.el-button) {
  min-height: 36px;
  border-radius: 8px;
  border-color: #45475a;
  background: #313244;
  color: #cdd6f4;
}

.pform :deep(.el-button > span),
.action-btns :deep(.el-button > span),
.mini-composer :deep(.el-button > span),
.download-grid :deep(.el-button > span) {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.plugin-panel :deep(.el-button:hover) {
  background: #3b3f56;
  border-color: #5b6078;
  color: #eef2ff;
}

.plugin-panel :deep(.el-button--primary) {
  background: linear-gradient(135deg, #5b9dff, #7cb8ff);
  border-color: transparent;
  color: #f8fbff;
}

.plugin-panel :deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #6aa8ff, #90c3ff);
  border-color: transparent;
  color: #ffffff;
}

/* 用户卡片 */
.user-card {
  display: flex; align-items: center; gap: 10px;
}
.user-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #89b4fa, #74c7ec);
  color: #1e1e2e; font-weight: 700; font-size: 14px; flex-shrink: 0;
}
.user-card > div:not(.user-avatar) {
  min-width: 0;
}
.user-name { font-size: 13px; font-weight: 600; color: #cdd6f4; }
.user-role { font-size: 11px; color: #6c7086; }
.user-card .el-button { margin-left: auto; }

.user-card :deep(.logout-btn) {
  min-height: auto;
  padding: 4px 8px;
  border: 0;
  background: transparent;
  color: #9399b2;
}

.user-card :deep(.logout-btn:hover) {
  background: rgba(137, 180, 250, 0.1);
  color: #cdd6f4;
}

.user-card :deep(.logout-btn > span) {
  width: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.project-card {
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(49, 50, 68, 0.95), rgba(24, 24, 37, 0.95));
  border: 1px solid #313244;
  margin-bottom: 10px;
}

.project-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.project-card-main {
  min-width: 0;
}

.project-name {
  font-size: 14px;
  font-weight: 700;
  color: #cdd6f4;
}

.project-subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #9399b2;
}

.project-meta {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.project-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  font-size: 12px;
}

.project-meta-row span {
  color: #6c7086;
  flex-shrink: 0;
}

.project-meta-row strong {
  color: #cdd6f4;
  text-align: right;
  font-weight: 600;
}

.project-path-row strong {
  word-break: break-all;
}

.advanced-panel {
  margin-top: 10px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(17, 17, 27, 0.9);
  border: 1px solid #313244;
}

.advanced-tip {
  margin-bottom: 8px;
  font-size: 12px;
  line-height: 1.5;
  color: #9399b2;
}

/* 数据包摘要 */
.pkg-summary {
  margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
}
.pkg-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 10px; border-radius: 6px; background: #313244; font-size: 12px;
}
.pkg-row span { color: #6c7086; }
.pkg-row strong { color: #cdd6f4; }

/* 操作按钮 */
.action-btns {
  display: flex; flex-direction: column; gap: 8px;
}

.action-btns :deep(.el-button + .el-button),
.download-grid :deep(.el-button + .el-button),
.pform :deep(.el-button + .el-button) {
  margin-left: 0 !important;
}

.mcp-overview {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 10px;
}

.mcp-stat-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #313244;
  background: rgba(17, 17, 27, 0.9);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mcp-stat-card strong {
  font-size: 18px;
  color: #89b4fa;
}

.mcp-stat-card span {
  font-size: 11px;
  color: #9399b2;
}

.mcp-empty {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px dashed #45475a;
  color: #9399b2;
  font-size: 12px;
  background: rgba(17, 17, 27, 0.65);
}

.mcp-tool-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.mcp-tool-chip {
  border: 1px solid #45475a;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(49, 50, 68, 0.85);
  color: #cdd6f4;
  font-size: 11px;
  cursor: pointer;
  transition: 0.15s ease;
}

.mcp-tool-chip:hover,
.mcp-tool-chip.active {
  background: rgba(137, 180, 250, 0.18);
  border-color: rgba(137, 180, 250, 0.55);
  color: #eef4ff;
}

.mcp-tool-card {
  margin: 10px 0;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #313244;
  background: rgba(17, 17, 27, 0.92);
}

.mcp-tool-card-title {
  font-size: 13px;
  font-weight: 700;
  color: #cdd6f4;
}

.mcp-tool-card-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #9399b2;
}

.mcp-schema {
  margin-top: 10px;
  padding: 10px;
  border-radius: 8px;
  background: #0b0b12;
  border: 1px solid rgba(137, 180, 250, 0.15);
  color: #bacdf8;
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 180px;
  overflow: auto;
}

.mcp-history {
  display: grid;
  gap: 8px;
}

.mcp-history-item {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #313244;
  background: rgba(17, 17, 27, 0.9);
}

.mcp-history-item.success {
  border-color: rgba(166, 227, 161, 0.35);
}

.mcp-history-item.error {
  border-color: rgba(243, 139, 168, 0.35);
}

.mcp-history-item.running {
  border-color: rgba(137, 180, 250, 0.35);
}

.mcp-history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.mcp-history-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mcp-history-tool {
  font-size: 12px;
  font-weight: 700;
  color: #eef4ff;
}

.mcp-history-source,
.mcp-history-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(49, 50, 68, 0.9);
  color: #bac2de;
}

.mcp-history-note {
  margin-top: 6px;
  font-size: 11px;
  color: #9399b2;
}

.mcp-history-block {
  margin-top: 8px;
  display: grid;
  gap: 4px;
}

.mcp-history-block span {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6c7086;
}

.mcp-history-block code {
  padding: 8px 10px;
  border-radius: 8px;
  background: #0b0b12;
  color: #dce3fb;
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 迷你聊天 */
.plugin-chat-section {
  display: flex; flex-direction: column; flex: 1; min-height: 0;
  border-bottom: 0;
  padding: 0;
}
.mini-chat {
  display: flex; flex-direction: column; flex: 1; min-height: 0;
  border-radius: 0; border: 0; overflow: hidden;
  background: #11111b;
}
.mini-messages {
  flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px;
}
.mini-msg {
  max-width: 92%; font-size: 12px; line-height: 1.6;
  padding: 8px 10px; border-radius: 10px;
  word-break: break-word;
}
.mini-msg.assistant { background: #313244; color: #cdd6f4; align-self: flex-start; }
.mini-msg.user { background: #89b4fa; color: #1e1e2e; align-self: flex-end; }
.mini-msg-text {
  white-space: normal;
}
.mini-msg.rich {
  min-width: min(100%, 280px);
}
.mini-msg.rich .mini-msg-text {
  display: grid;
  gap: 12px;
}
.mini-msg.rich .mini-msg-text :deep(*) {
  margin: 0;
}
.mini-msg.rich .mini-msg-text :deep(strong) {
  color: #f5f7ff;
}
.mini-msg.rich .mini-msg-text :deep(em) {
  color: #cfe2ff;
}
.mini-msg.rich .mini-msg-text :deep(code) {
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(17, 17, 27, 0.7);
  color: #f9e2af;
  font-family: Consolas, 'Courier New', monospace;
}
.mini-msg.rich .mini-msg-text :deep(.msg-paragraph) {
  line-height: 1.75;
  color: #dce3fb;
}
.mini-msg.rich .mini-msg-text :deep(.msg-paragraph + .msg-paragraph) {
  margin-top: 2px;
}
.mini-msg.rich .mini-msg-text :deep(.msg-heading) {
  font-weight: 700;
  line-height: 1.45;
  padding-left: 10px;
  border-left: 3px solid rgba(137, 180, 250, 0.45);
  letter-spacing: 0.01em;
}
.mini-msg.rich .mini-msg-text :deep(.msg-heading-1) {
  font-size: 17px;
  color: #ffffff;
  border-left-color: #89b4fa;
  margin-top: 2px;
}
.mini-msg.rich .mini-msg-text :deep(.msg-heading-2) {
  font-size: 15px;
  color: #cfe2ff;
  border-left-color: rgba(116, 199, 236, 0.75);
}
.mini-msg.rich .mini-msg-text :deep(.msg-heading-3) {
  font-size: 13px;
  color: #bacdf8;
  border-left-color: rgba(166, 227, 161, 0.65);
}
.mini-msg.rich .mini-msg-text :deep(.msg-list-item) {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: start;
  line-height: 1.7;
  color: #d7def6;
}
.mini-msg.rich .mini-msg-text :deep(.msg-heading + .msg-paragraph),
.mini-msg.rich .mini-msg-text :deep(.msg-heading + .msg-list-item),
.mini-msg.rich .mini-msg-text :deep(.msg-list-item + .msg-paragraph),
.mini-msg.rich .mini-msg-text :deep(.msg-paragraph + .msg-list-item),
.mini-msg.rich .mini-msg-text :deep(.msg-code + .msg-paragraph),
.mini-msg.rich .mini-msg-text :deep(.msg-heading + .msg-code) {
  margin-top: 2px;
}
.mini-msg.rich .mini-msg-text :deep(.msg-bullet) {
  color: #89b4fa;
  font-weight: 700;
}
.mini-msg.rich .mini-msg-text :deep(.msg-code) {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(17, 17, 27, 0.88);
  border: 1px solid rgba(137, 180, 250, 0.18);
  color: #cdd6f4;
  white-space: pre-wrap;
  overflow-x: auto;
}
.mini-tools {
  display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;
}
.mini-tools span {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: rgba(0,0,0,0.2); color: #a6adc8;
}
.mini-composer {
  display: grid; grid-template-columns: minmax(0, 1fr) 76px; gap: 6px; padding: 8px; border-top: 1px solid #313244;
  background: #1e1e2e;
  align-items: center;
}
.mini-composer .el-input { flex: 1; }

.mini-composer :deep(.el-button) {
  min-height: 32px;
}

/* 下载网格 */
.download-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
}

/* ── 底部状态栏 ── */
.statusbar {
  height: 24px; background: #89b4fa; color: #1e1e2e;
  display: flex; align-items: center; gap: 20px;
  padding: 0 14px; font-size: 11px; font-weight: 600;
  flex-shrink: 0;
}

/* ── 过渡动画 ── */
.slide-enter-active, .slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%); opacity: 0;
}
</style>
