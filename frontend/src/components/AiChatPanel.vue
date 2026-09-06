<template>
  <div class="ai-chat-panel" :class="{ collapsed: isCollapsed }">
    <!-- 折叠条 -->
    <div class="panel-toggle" @click="isCollapsed = !isCollapsed">
      <el-icon :size="15"><ChatDotRound /></el-icon>
      <span v-if="!isCollapsed" class="toggle-label">AI</span>
      <el-icon :size="11"><component :is="isCollapsed ? ArrowRight : ArrowLeft" /></el-icon>
    </div>

    <div v-if="!isCollapsed" class="panel-body">
      <!-- ═══ Header ═══ -->
      <div class="panel-header">
        <div class="header-title">
          <div class="header-avatar">
            <el-icon :size="13"><Cpu /></el-icon>
          </div>
          <div class="header-text">
            <span class="header-name">数据分析助手</span>
            <span class="header-status">{{ messages.length > 0 ? `${messages.length} 条消息` : '等待对话' }}</span>
          </div>
        </div>
        <div class="header-actions">
          <el-tooltip :content="webSearchEnabled ? '联网搜索已开启' : '联网搜索已关闭'" placement="bottom">
            <div class="action-switch" :class="{ on: webSearchEnabled }" @click="webSearchEnabled = !webSearchEnabled">
              <el-icon :size="12"><Search /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="工具列表" placement="bottom">
            <el-popover placement="bottom-end" :width="260" trigger="click">
              <template #reference>
                <div class="action-btn">
                  <el-icon :size="13"><Tools /></el-icon>
                </div>
              </template>
              <div class="tools-popover">
                <div class="tools-popover-title">MCP 工具 · {{ MCP_TOOL_NAMES.length }}</div>
                <div v-for="tool in MCP_TOOL_NAMES" :key="tool.name" class="tools-popover-item">
                  <code>{{ tool.name }}</code>
                  <span>{{ tool.desc }}</span>
                </div>
              </div>
            </el-popover>
          </el-tooltip>
          <el-tooltip content="清空对话" placement="bottom">
            <div class="action-btn" @click="clearChat">
              <el-icon :size="13"><Delete /></el-icon>
            </div>
          </el-tooltip>
        </div>
      </div>

      <!-- ═══ Message List ═══ -->
      <div class="messages-container" ref="messagesRef">
        <!-- 空状态 -->
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-icon-wrap">
            <el-icon :size="20"><Cpu /></el-icon>
          </div>
          <div class="welcome-title">智能数据分析助手</div>
          <div class="welcome-sub">加载数据包后，可直接提问或让 AI 自动生成报告</div>
          <div class="quick-cards">
            <div v-for="card in quickCards" :key="card.text" class="quick-card" @click="sendQuickQuestion(card.text)">
              <span class="qc-icon">{{ card.icon }}</span>
              <span class="qc-label">{{ card.label }}</span>
            </div>
          </div>
        </div>

        <!-- 消息 -->
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="msg-row"
          :class="msg.role"
        >
          <div class="msg-avatar">
            <el-icon v-if="msg.role === 'assistant'" :size="13"><Cpu /></el-icon>
            <el-icon v-else :size="13"><User /></el-icon>
          </div>
          <div class="msg-body">
            <!-- Tool Calls — 带脉冲动画 -->
            <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="tool-calls-wrap">
              <div
                v-for="(tc, ti) in msg.tool_calls"
                :key="ti"
                class="tool-chip"
                :class="{ workflow: isWorkflowTool(tc.tool), pulse: msg.streaming && ti === msg.tool_calls.length - 1 }"
              >
                <el-icon :size="11">
                  <Promotion v-if="isWorkflowTool(tc.tool)" />
                  <Connection v-else />
                </el-icon>
                <span class="tc-label">{{ getToolLabel(tc.tool) }}</span>
                <span v-if="tc.args && Object.keys(tc.args).length > 0" class="tc-args">{{ formatArgs(tc.args) }}</span>
                <span class="tc-badge" :class="{ workflow: isWorkflowTool(tc.tool) }">
                  {{ isWorkflowTool(tc.tool) ? '执行' : '查询' }}
                </span>
              </div>
            </div>
            <!-- 流程可视化（工具调用链路 + RAG 链路） -->
            <ProcessVisualization
              v-if="!msg.streaming && msg.tool_calls?.length > 0"
              :tool-calls="msg.tool_calls"
              :quality-data="msg.qualityData"
            />
            <!-- 搜索结果卡片（web_search 工具返回时渲染） -->
            <div v-if="msg.searchResults && msg.searchResults.length > 0" class="search-results-wrap">
              <div class="sr-title">🔍 搜索结果</div>
              <a v-for="(sr, si) in msg.searchResults" :key="si" :href="sr.url" target="_blank" rel="noopener" class="sr-card">
                <div class="sr-card-title">{{ sr.title }}</div>
                <div class="sr-card-snippet">{{ sr.snippet }}</div>
                <div class="sr-card-domain">{{ sr.domain }}</div>
              </a>
            </div>
            <!-- 数据可视化卡片（metrics 工具返回时渲染） -->
            <div v-if="msg.dataCards && msg.dataCards.length > 0" class="data-cards-wrap">
              <div v-for="(dc, di) in msg.dataCards" :key="di" class="data-card">
                <div class="dc-header">
                  <span class="dc-name">{{ dc.name }}</span>
                  <span class="dc-semantic">{{ dc.semantic }}</span>
                </div>
                <div class="dc-bar-wrap">
                  <div class="dc-bar" :style="{ width: dc.pct + '%' }"></div>
                </div>
                <div class="dc-values">
                  <span>{{ dc.min }}</span>
                  <span class="dc-span">跨度 {{ dc.span }}</span>
                  <span>{{ dc.max }}</span>
                </div>
              </div>
            </div>
            <!-- 消息内容 -->
            <div v-if="msg.streaming" class="msg-bubble markdown-body streaming-plain">
              {{ msg.content }}<span class="stream-cursor"></span>
            </div>
            <div v-else class="msg-bubble markdown-body" v-html="renderMarkdown(msg.content)"></div>
            <!-- 操作按钮 -->
            <div v-if="msg.role === 'assistant' && msg.actionButtons && idx === lastAssistantIndex" class="action-buttons">
              <button
                v-for="btn in msg.actionButtons"
                :key="btn.label"
                class="action-btn-inline"
                :class="btn.type === 'primary' ? 'primary' : 'secondary'"
                :disabled="loading"
                @click="handleActionButton(btn)"
              >{{ btn.label }}</button>
            </div>
            <div class="msg-meta">{{ msg.time }}</div>
          </div>
        </div>

        <!-- 加载指示器（流式时隐藏，已有 streaming bubble） -->
        <div v-if="loading && !messages.some(m => m.streaming)" class="msg-row assistant">
          <div class="msg-avatar"><el-icon :size="13"><Cpu /></el-icon></div>
          <div class="msg-body">
            <div class="msg-bubble typing-indicator">
              <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ Auto Progress Bar ═══ -->
      <div v-if="autoRunning" class="auto-progress-wrap">
        <div class="auto-progress-head">
          <span class="auto-progress-icon">⚡</span>
          <span class="auto-progress-label">{{ autoMode === 'config_only' ? '自动配置报告' : '一键生成报告' }}</span>
          <span class="auto-progress-pct">{{ autoProgress }}%</span>
        </div>
        <div class="auto-progress-bar">
          <div class="auto-progress-fill" :style="{ width: autoProgress + '%' }"></div>
        </div>
        <div class="auto-progress-text">{{ autoProgressText }}</div>
      </div>

      <!-- ═══ Composer ═══ -->
      <div class="composer">
        <div class="composer-input-wrap">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            :placeholder="composerPlaceholder"
            resize="none"
            @keydown.enter.exact.prevent="sendMessage"
          />
        </div>
        <div class="composer-footer">
          <span class="composer-hint">Enter 发送 · Shift+Enter 换行</span>
          <button class="send-btn" :disabled="!inputText.trim() || loading" @click="sendMessage">
            <el-icon :size="14"><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { marked } from 'marked'
import { authFetch } from '../api'
import ProcessVisualization from './ProcessVisualization.vue'
import {
  ChatDotRound, ArrowLeft, ArrowRight, Cpu, Tools, Delete,
  User, Connection, Promotion, Search
} from '@element-plus/icons-vue'
import {
  messages, loading, autoMode, autoRunning, autoProgress, autoProgressText,
  getAbortController, setAbortController, clearChatStore
} from '../stores/chatStore'

// marked 配置：不生成 <p> 包裹，保持紧凑
marked.setOptions({ breaks: true, gfm: true })

// AI 凭证由后端按管理员配置的系统级密钥解析，前端不再注入
const emit = defineEmits(['workflow-action'])

const isCollapsed = ref(false)
const inputText = ref('')
const messagesRef = ref(null)
const webSearchEnabled = ref(false)

const MCP_TOOL_NAMES = [
  { name: 'get_run_info', desc: '查询数据包元信息' },
  { name: 'list_signals', desc: '列出流场变量' },
  { name: 'compute_metrics', desc: '计算统计指标' },
  { name: 'get_mesh_info', desc: '获取网格结构' },
  { name: 'get_derived_quantities', desc: '获取派生物理量' },
  { name: 'rag_query', desc: '知识库检索' },
  { name: 'web_search', desc: '联网搜索' },
  { name: 'auto_configure', desc: '自动配置报告' },
  { name: 'generate_next_slot', desc: '生成下一个槽位' },
  { name: 'generate_all_slots', desc: '生成全部内容' },
  { name: 'accept_all_slots', desc: '确认全部槽位' },
  { name: 'export_report', desc: '导出报告' },
]

const quickCards = [
  { icon: '📄', label: '自动生成报告', text: '帮我自动生成报告' },
  { icon: '📊', label: '变量统计', text: '帮我分析所有变量的统计指标' },
  { icon: '🌊', label: '流动状态', text: '当前数据的流动状态如何？' },
  { icon: '🔍', label: '网格质量', text: '分析一下网格质量' },
  { icon: '📐', label: '派生物理量', text: '查看派生物理量' },
  { icon: '📚', label: '知识检索', text: '从知识库中检索 Plot3D 格式说明' },
]

const composerPlaceholder = computed(() => {
  if (autoRunning.value) return '自动生成中，请稍候…'
  if (loading.value) return '思考中…'
  return '输入问题或指令… 试试"帮我自动生成报告"'
})

const formatTime = () => {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const WORKFLOW_TOOLS = ['auto_configure', 'generate_next_slot', 'generate_all_slots', 'accept_all_slots', 'export_report']
const isWorkflowTool = (name) => WORKFLOW_TOOLS.includes(name)

const TOOL_LABELS = {
  get_run_info: '查询元信息',
  list_signals: '列出变量',
  compute_metrics: '计算指标',
  get_mesh_info: '获取网格',
  get_derived_quantities: '获取派生量',
  rag_query: '知识库检索',
  web_search: '联网搜索',
  auto_configure: '配置报告',
  generate_next_slot: '生成槽位内容',
  generate_all_slots: '生成全部内容',
  accept_all_slots: '确认全部槽位',
  export_report: '导出报告',
}
const getToolLabel = (name) => TOOL_LABELS[name] || name

const formatArgs = (args) => {
  if (!args) return ''
  const entries = Object.entries(args)
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')
}

// 用 marked 做完整的 Markdown 渲染
const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text.replace(/\n/g, '<br>')
  }
}

// 最后一条 assistant 消息的 index（用于仅显示最新一条的操作按钮）
const lastAssistantIndex = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant') return i
  }
  return -1
})

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

const sendQuickQuestion = (q) => {
  inputText.value = q
  sendMessage()
}

const clearChat = () => clearChatStore()

// 各工作流步骤的前端等待时间（ms），让动画有时间播放
const WORKFLOW_DELAYS = {
  auto_configure: 5000,
  generate_next_slot: 1500,
  generate_all_slots: 2000,
  accept_all_slots: 2000,
  export_report: 1500,
}

// ─── 用户点击操作按钮 ───
const handleActionButton = async (btn) => {
  // 移除所有消息上的 actionButtons（防止重复点击）
  messages.value.forEach(m => { m.actionButtons = undefined })
  // 发送对应文本
  messages.value.push({ role: 'user', content: btn.text, time: formatTime() })
  loading.value = true
  await scrollToBottom()
  try {
    await _doChat()
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

// ── 意图检测：区分一键生成报告 vs 仅配置 vs 普通对话 ──
const FULL_REPORT_KEYWORDS = ['一键生成报告', '帮我自动生成报告', '自动生成报告', '从头到尾生成报告', '直接生成报告', '全自动生成', '帮我生成报告']
const CONFIG_ONLY_KEYWORDS = ['自动生成报告配置', '自动配置报告', '帮我配置报告', '只配置报告', '仅配置']

function detectAutoMode(text) {
  const t = text.trim()
  // 先检测 config_only（更具体的优先）
  if (CONFIG_ONLY_KEYWORDS.some(k => t.includes(k))) return 'config_only'
  // 再检测 full_report
  if (FULL_REPORT_KEYWORDS.some(k => t.includes(k))) return 'full_report'
  return null
}

// ── 全自动工作流执行器 ──
async function runAutoWorkflow(mode, assistantMsg) {
  autoMode.value = mode
  autoRunning.value = true
  autoProgress.value = 0
  autoProgressText.value = mode === 'config_only' ? '开始自动填写报告配置…' : '开始一键生成报告…'

  try {
    const resp = await authFetch('/api/workflow/auto-generate-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      cache: 'no-store',
      body: JSON.stringify({ mode })
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
        const line = block.split('\n').find(l => l.startsWith('data:'))
        if (!line) continue
        const raw = line.replace(/^data:\s*/, '')
        if (!raw) continue
        let evt
        try { evt = JSON.parse(raw) } catch { continue }

        if (evt.type === 'progress') {
          autoProgress.value = Math.max(0, Math.min(100, Number(evt.percent || 0)))
          autoProgressText.value = evt.message || ''
        } else if (evt.type === 'tool_call') {
          assistantMsg.tool_calls.push({ tool: evt.name, args: evt.args || {} })
          await scrollToBottom()
        } else if (evt.type === 'tool_result') {
          // 静默处理
        } else if (evt.type === 'done') {
          autoProgress.value = 100
          autoProgressText.value = evt.message || '已完成'
          if (mode === 'config_only') {
            assistantMsg.content = `✅ 已自动完成报告配置（${evt.slot_count || '?'} 个槽位，领域：${evt.domain || '?'}），按要求已停止在配置阶段。\n\n如需继续生成报告，请说「一键生成报告」。`
          } else {
            assistantMsg.content = `✅ 报告已自动生成并导出完成！\n\n📁 输出目录：${evt.output_dir || '未知'}\n📄 共生成 ${evt.slot_count || '?'} 个槽位`
          }
          assistantMsg.streaming = false
          // 通知父组件
          emit('workflow-action', { action: 'export_report', result: evt })
        } else if (evt.type === 'error') {
          throw new Error(evt.error || '自动工作流失败')
        }
      }
    }
  } catch (err) {
    assistantMsg.content = `❌ 自动工作流失败：${err.message}`
    assistantMsg.streaming = false
  } finally {
    // 延迟关闭进度条，让用户看到 100%
    setTimeout(() => {
      autoRunning.value = false
      autoProgress.value = 0
      autoProgressText.value = ''
    }, 2000)
  }
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text, time: formatTime() })
  inputText.value = ''
  loading.value = true
  await scrollToBottom()

  // ── 检测是否为自动生成意图 ──
  const detectedMode = detectAutoMode(text)
  if (detectedMode) {
    // 创建一条 assistant 消息用于显示进度
    messages.value.push({
      role: 'assistant',
      content: '',
      tool_calls: [],
      time: formatTime(),
      streaming: true
    })
    const assistantMsg = messages.value[messages.value.length - 1]
    await scrollToBottom()

    try {
      await runAutoWorkflow(detectedMode, assistantMsg)
    } finally {
      loading.value = false
      await scrollToBottom()
    }
    return
  }

  try {
    await _doChat()
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

// ─── 核心聊天请求（SSE 流式）───
const _doChat = async () => {
  // Cancel any in-flight stream before starting a new one
  if (getAbortController()) {
    getAbortController().abort()
    setAbortController(null)
  }
  const abortController = new AbortController()
  setAbortController(abortController)

  const historyMessages = messages.value
    .filter(m => m.role === 'user' || m.role === 'assistant')
    .map(m => ({ role: m.role, content: m.content }))

  messages.value.push({
    role: 'assistant',
    content: '',
    tool_calls: [],
    time: formatTime(),
    streaming: true
  })
  const assistantMsg = messages.value[messages.value.length - 1]
  await scrollToBottom()

  let resp
  try {
    resp = await authFetch('/api/mcp-chat-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      cache: 'no-store',
      signal: abortController.signal,
      body: JSON.stringify({
        messages: historyMessages,
        webSearchEnabled: webSearchEnabled.value
      })
    })
  } catch (err) {
    if (err.name === 'AbortError') return
    assistantMsg.content = `❌ 网络请求失败：${err.message}`
    assistantMsg.streaming = false
    return
  }

  if (!resp.ok) {
    assistantMsg.content = `❌ 请求失败：${resp.status}`
    assistantMsg.streaming = false
    return
  }

  if (!resp.body) {
    assistantMsg.content = '❌ 未收到可读取的流式响应'
    assistantMsg.streaming = false
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let lastWorkflowAction = null
  let lastWorkflowResult = null
  let deltaQueue = []
  let flushingDelta = false
  let flushPromise = Promise.resolve()
  const BASE_CHAR_DELAY_MS = 35

  const charDelay = (ch) => {
    if (/[,，.。!?！？;；:\n]/.test(ch)) {
      return BASE_CHAR_DELAY_MS + 70
    }
    return BASE_CHAR_DELAY_MS
  }

  const flushDeltaQueue = async () => {
    if (flushingDelta) return flushPromise
    flushingDelta = true
    flushPromise = (async () => {
      let renderTick = 0
      while (deltaQueue.length > 0) {
        const ch = deltaQueue.shift()
        assistantMsg.content += ch
        await nextTick()
        renderTick += 1
        // 降低滚动频率，避免每个字符都触发重排
        if (renderTick % 8 === 0 || deltaQueue.length === 0) {
          await scrollToBottom()
        }
        await new Promise(r => setTimeout(r, charDelay(ch)))
      }
      flushingDelta = false
    })()
    return flushPromise
  }

  const enqueueDelta = (text) => {
    if (!text) return
    for (const ch of text) {
      deltaQueue.push(ch)
    }
    void flushDeltaQueue()
  }

  const parseSseEvent = (block) => {
    const dataLines = block
      .split('\n')
      .map(line => line.replace(/\r$/, ''))
      .filter(line => line.startsWith('data:'))
    if (dataLines.length === 0) return null

    const payload = dataLines
      .map(line => line.slice(5).trimStart())
      .join('\n')
      .trim()
    if (!payload) return null

    try {
      return JSON.parse(payload)
    } catch {
      return null
    }
  }

  const handleSseEvent = async (evt) => {
    if (evt.type === 'tool_call') {
      // 工具调用进行中 — 加入 tool_calls 数组实时显示
      assistantMsg.tool_calls.push({ tool: evt.name, args: evt.args })

      // 解析工具结果 → 富卡片
      if (evt.tool === 'web_search' && evt.result?.results) {
        assistantMsg.searchResults = (evt.result.results || []).slice(0, 5).map(r => ({
          url: r.url, title: r.title, snippet: (r.snippet || '').slice(0, 120), domain: r.domain || ''
        }))
      }
      if ((evt.tool === 'compute_metrics' || evt.tool === 'list_signals') && evt.result) {
        const metrics = evt.result.metrics || {}
        const signals = evt.result.signals || []
        const cards = []
        // from compute_metrics
        for (const [name, m] of Object.entries(metrics)) {
          const span = (m.max - m.min) || 1
          cards.push({ name, semantic: m.semantic || '', min: m.min?.toExponential(2), max: m.max?.toExponential(2), span: span.toExponential(2), pct: Math.min(100, Math.max(5, 50)) })
        }
        // from list_signals
        for (const s of signals) {
          if (s.range_min != null && s.range_max != null) {
            const span = s.range_max - s.range_min || 1
            cards.push({ name: s.name, semantic: s.semantic || '', min: s.range_min?.toExponential(2), max: s.range_max?.toExponential(2), span: span.toExponential(2), pct: Math.min(100, Math.max(5, 50)) })
          }
        }
        if (cards.length > 0) assistantMsg.dataCards = cards
      }

      await scrollToBottom()

    } else if (evt.type === 'delta') {
      // 入队后逐字渲染，确保视觉上“一个字一个字”输出
      enqueueDelta(evt.content)

    } else if (evt.type === 'done') {
      // done 前先把已收到的流式内容完整渲染完
      await flushDeltaQueue()
      // 流结束，补全 tool_calls 信息
      assistantMsg.tool_calls = evt.tool_calls || []
      assistantMsg.streaming = false

      // 通知父组件 workflow 事件
      for (const tc of assistantMsg.tool_calls) {
        if (tc.action) {
          lastWorkflowAction = tc.action
          lastWorkflowResult = tc.result || {}
          emit('workflow-action', { action: tc.action, result: tc.result || {} })
        }
      }

      const paused = evt.workflow_paused || false
      if (paused) {
        lastWorkflowAction = evt.workflow_action || lastWorkflowAction
        lastWorkflowResult = evt.workflow_result || lastWorkflowResult || {}
        // 补发 workflow-action（流式版本通过 done 事件携带）
        if (lastWorkflowAction) {
          emit('workflow-action', { action: lastWorkflowAction, result: lastWorkflowResult })
        }

        const delay = WORKFLOW_DELAYS[lastWorkflowAction] || 2000
        await new Promise(r => setTimeout(r, delay))

        if (lastWorkflowAction === 'generate_next_slot' && !lastWorkflowResult?.all_done) {
          assistantMsg.actionButtons = [
            { label: '✅ 继续生成下一个', text: '继续下一步', type: 'primary' },
            { label: '⏸ 暂停', text: '暂停，我想先看看', type: 'default' }
          ]
        } else if (lastWorkflowAction === 'generate_next_slot' && lastWorkflowResult?.all_done) {
          assistantMsg.actionButtons = [
            { label: '✅ 全部确认并导出', text: '是，全部确认并导出报告', type: 'primary' },
            { label: '❌ 暂不需要', text: '否，暂时不需要', type: 'default' }
          ]
        } else if (lastWorkflowAction === 'auto_configure') {
          assistantMsg.actionButtons = [
            { label: '✅ 开始生成', text: '继续下一步', type: 'primary' },
            { label: '⏸ 稍等', text: '稍等，我想调整配置', type: 'default' }
          ]
        } else if (lastWorkflowAction === 'accept_all_slots') {
          assistantMsg.actionButtons = [
            { label: '📄 导出报告', text: '继续下一步', type: 'primary' },
            { label: '⏸ 稍后', text: '稍等，先不导出', type: 'default' }
          ]
        }
        await scrollToBottom()
      }

    } else if (evt.type === 'error') {
      await flushDeltaQueue()
      assistantMsg.content = `❌ 错误：${evt.error}`
      assistantMsg.streaming = false
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const eventBlocks = buffer.split('\n\n')
      buffer = eventBlocks.pop() || ''

      for (const block of eventBlocks) {
        const evt = parseSseEvent(block)
        if (!evt) continue
        await handleSseEvent(evt)
      }
    }

    buffer += decoder.decode()
    if (buffer.trim()) {
      const evt = parseSseEvent(buffer)
      if (evt) {
        await handleSseEvent(evt)
      }
    }
  } catch (streamErr) {
    if (streamErr.name === 'AbortError') return
    console.error('[SSE] 流中断:', streamErr)
    await flushDeltaQueue()
    if (assistantMsg.streaming) {
      assistantMsg.content += '\n\n❌ 连接中断，请重新发送消息'
    }
  } finally {
    assistantMsg.streaming = false
    if (getAbortController() === abortController) {
      setAbortController(null)
    }
    await scrollToBottom()
  }
}
</script>

<style scoped>
/* ═══════════════════════════════════════
   AI Chat Panel — Notion/Linear 风格
   ═══════════════════════════════════════ */

/* ── 面板容器 ── */
.ai-chat-panel {
  display: flex;
  flex-direction: row;
  width: 400px;
  min-width: 400px;
  max-width: 400px;
  height: 100%;
  flex-shrink: 0;
  background: var(--c-bg-card);
  border-right: 1px solid var(--c-border);
  transition: width 0.2s var(--ease-default), min-width 0.2s var(--ease-default), max-width 0.2s var(--ease-default);
  overflow: hidden;
}
.ai-chat-panel.collapsed {
  width: 36px; min-width: 36px; max-width: 36px;
}

/* ── 折叠条 ── */
.panel-toggle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: var(--sp-3);
  gap: var(--sp-1);
  width: 36px;
  min-width: 36px;
  height: 100%;
  cursor: pointer;
  background: var(--c-gray-900);
  color: rgba(255,255,255,0.8);
  user-select: none;
  transition: background var(--duration-fast) var(--ease-default);
}
.panel-toggle:hover { background: var(--c-gray-700); }
.toggle-label {
  writing-mode: vertical-rl;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 2px;
}

/* ── 主体 ── */
.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  min-width: 0;
}

/* ══ Header ══ */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-3);
  height: 48px;
  min-height: 48px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg-card);
  flex-shrink: 0;
}
.header-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.header-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-lg);
  background: var(--c-gray-900);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.header-text {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.header-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--c-text-1);
  line-height: 1.2;
}
.header-status {
  font-size: var(--text-xs);
  color: var(--c-text-4);
  line-height: 1.3;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}
.action-switch {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--c-text-4);
  transition: all var(--duration-fast) var(--ease-default);
}
.action-switch:hover { background: var(--c-gray-100); color: var(--c-text-2); }
.action-switch.on {
  color: var(--c-primary);
  background: var(--c-primary-light);
}
.action-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--c-text-4);
  transition: all var(--duration-fast) var(--ease-default);
}
.action-btn:hover { background: var(--c-gray-100); color: var(--c-text-2); }

/* ── Tools Popover ── */
.tools-popover { padding: var(--sp-1) 0; }
.tools-popover-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-text-3);
  margin-bottom: var(--sp-2);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--c-border-muted);
}
.tools-popover-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 3px 0;
  font-size: var(--text-sm);
}
.tools-popover-item code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--c-primary);
  background: var(--c-primary-light);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.tools-popover-item span {
  color: var(--c-text-4);
  font-size: var(--text-xs);
}

/* ══ Messages ══ */
.messages-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--sp-4) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  scroll-behavior: smooth;
}

/* ── Welcome / Empty State ── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--sp-10) var(--sp-4) var(--sp-5);
  gap: var(--sp-2);
}
.welcome-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-xl);
  background: var(--c-gray-900);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: var(--sp-1);
}
.welcome-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--c-text-1);
}
.welcome-sub {
  font-size: var(--text-sm);
  color: var(--c-text-4);
  max-width: 260px;
  line-height: var(--lh-sm);
}
/* ── Quick Action Cards ── */
.quick-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  width: 100%;
  max-width: 300px;
}
.quick-card {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 8px var(--sp-3);
  background: var(--c-bg-card);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.quick-card:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-light);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(37,99,235,0.08);
}
.qc-icon { font-size: 16px; flex-shrink: 0; }
.qc-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--c-text-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Message Row ── */
.msg-row {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-start;
  flex-shrink: 0;
}
.msg-row.user { flex-direction: row-reverse; }

.msg-avatar {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
.msg-row.assistant .msg-avatar {
  background: var(--c-gray-900);
  color: white;
}
.msg-row.user .msg-avatar {
  background: var(--c-primary-muted);
  color: var(--c-primary);
}

.msg-body {
  max-width: calc(100% - 36px);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.msg-row.user .msg-body { align-items: flex-end; }

/* ── Tool Calls ── */
.tool-calls-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 2px;
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs);
  color: var(--c-text-3);
  background: var(--c-bg-sunken);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 3px var(--sp-2);
  transition: all var(--duration-fast);
}
.tool-chip.workflow {
  background: var(--c-primary-light);
  border-color: var(--c-primary-muted);
  color: var(--c-primary-hover);
}
.tc-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--c-primary);
}
.tc-args {
  color: var(--c-text-4);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100px;
}
.tc-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 0 4px;
  border-radius: var(--radius-sm);
  background: var(--c-success-light);
  color: var(--c-success);
}
.tc-badge.workflow {
  background: var(--c-primary-light);
  color: var(--c-primary);
}

/* ── Bubble ── */
.msg-bubble {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  line-height: 1.65;
  word-break: break-word;
}
.msg-row.assistant .msg-bubble {
  background: var(--c-bg-sunken);
  border-top-left-radius: var(--radius-sm);
  color: var(--c-text-1);
}
.msg-row.user .msg-bubble {
  background: var(--c-primary);
  color: white;
  border-top-right-radius: var(--radius-sm);
}

/* ── Markdown ── */
.msg-bubble.markdown-body :deep(p) { margin: 0 0 6px; }
.msg-bubble.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.streaming-plain {
  white-space: pre-wrap;
}
.msg-bubble.markdown-body :deep(h1),
.msg-bubble.markdown-body :deep(h2),
.msg-bubble.markdown-body :deep(h3),
.msg-bubble.markdown-body :deep(h4) {
  margin: 4px 0 4px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--c-text-1);
}
.msg-bubble.markdown-body :deep(h1) { font-size: var(--text-lg); }
.msg-bubble.markdown-body :deep(h2) { font-size: var(--text-md); }
.msg-bubble.markdown-body :deep(h3) { font-size: var(--text-base); }
.msg-bubble.markdown-body :deep(ul),
.msg-bubble.markdown-body :deep(ol) {
  margin: 2px 0 6px;
  padding-left: 18px;
}
.msg-bubble.markdown-body :deep(li) { margin-bottom: 2px; }
.msg-bubble.markdown-body :deep(strong) { font-weight: 600; }
.msg-bubble.markdown-body :deep(code) {
  background: rgba(0,0,0,0.05);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.msg-bubble.markdown-body :deep(pre) {
  background: rgba(0,0,0,0.04);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: 4px 0;
}
.msg-bubble.markdown-body :deep(pre code) { background: none; padding: 0; }
.msg-bubble.markdown-body :deep(blockquote) {
  margin: 4px 0;
  padding: 3px var(--sp-3);
  border-left: 3px solid var(--c-primary-muted);
  color: var(--c-text-3);
  background: rgba(37,99,235,0.03);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.msg-bubble.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 4px 0;
  font-size: var(--text-sm);
  width: 100%;
}
.msg-bubble.markdown-body :deep(th),
.msg-bubble.markdown-body :deep(td) {
  border: 1px solid var(--c-border);
  padding: 3px var(--sp-2);
  text-align: left;
}
.msg-bubble.markdown-body :deep(th) {
  background: var(--c-bg-sunken);
  font-weight: 600;
}
.msg-bubble.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--c-border);
  margin: 6px 0;
}
.msg-row.user .msg-bubble :deep(code) { background: rgba(255,255,255,0.15); }

/* ── Action Buttons ── */
.action-buttons {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-1);
  flex-wrap: wrap;
}
.action-btn-inline {
  padding: 5px var(--sp-3);
  font-size: var(--text-sm);
  font-weight: 500;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid var(--c-border);
  background: var(--c-bg-card);
  color: var(--c-text-2);
  font-family: var(--font-sans);
  transition: all var(--duration-fast) var(--ease-default);
}
.action-btn-inline:hover { border-color: var(--c-gray-300); background: var(--c-gray-50); }
.action-btn-inline.primary {
  background: var(--c-primary);
  color: white;
  border-color: var(--c-primary);
}
.action-btn-inline.primary:hover {
  background: var(--c-primary-hover);
  border-color: var(--c-primary-hover);
}
.action-btn-inline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Typing Indicator ── */
.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: var(--sp-3) var(--sp-4);
}
.typing-dot {
  width: 6px;
  height: 6px;
  background: var(--c-gray-400);
  border-radius: 50%;
  animation: typing-bounce 1.2s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.15s; }
.typing-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.stream-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--c-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  border-radius: 1px;
  animation: cursor-blink 0.7s step-end infinite;
}
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.msg-meta {
  font-size: 10px;
  color: var(--c-gray-300);
  padding: 0 2px;
}

/* ══ Composer ══ */
.composer {
  padding: var(--sp-3);
  border-top: 1px solid var(--c-border);
  background: var(--c-bg-card);
  flex-shrink: 0;
}
.composer-input-wrap :deep(.el-textarea__inner) {
  font-size: var(--text-base);
  font-family: var(--font-sans);
  border-radius: var(--radius-lg) !important;
  resize: none;
  border-color: var(--c-border) !important;
  background: var(--c-bg-sunken);
  line-height: 1.55;
  padding: var(--sp-2) var(--sp-3);
  box-shadow: none !important;
}
.composer-input-wrap :deep(.el-textarea__inner):focus {
  border-color: var(--c-primary-muted) !important;
  background: var(--c-bg-card);
  box-shadow: var(--shadow-focus) !important;
}
.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--sp-2);
}
.composer-hint {
  font-size: 10px;
  color: var(--c-gray-300);
}
.send-btn {
  width: 32px;
  height: 28px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--c-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.send-btn:hover { background: var(--c-primary-hover); }
.send-btn:focus-visible,
.action-btn-inline:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}
.send-btn:disabled {
  background: var(--c-gray-200);
  color: var(--c-gray-400);
  cursor: not-allowed;
}

/* ══ Auto Progress Bar ══ */
.auto-progress-wrap {
  padding: var(--sp-3);
  border-top: 1px solid var(--c-border);
  background: linear-gradient(135deg, rgba(37,99,235,0.04), rgba(37,99,235,0.08));
  flex-shrink: 0;
}
.auto-progress-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}
.auto-progress-icon {
  font-size: var(--text-md);
}
.auto-progress-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-text-1);
  flex: 1;
}
.auto-progress-pct {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--c-primary);
  font-family: var(--font-mono);
}
.auto-progress-bar {
  height: 6px;
  background: var(--c-gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--sp-1);
}
.auto-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-primary), var(--c-primary-hover));
  border-radius: var(--radius-full);
  transition: width 0.4s ease;
}
.auto-progress-text {
  font-size: var(--text-xs);
  color: var(--c-text-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Tool Chip Pulse Animation ── */
.tool-chip.pulse {
  animation: chip-pulse 1.5s infinite;
}
@keyframes chip-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37,99,235,0.3); }
  50% { box-shadow: 0 0 0 4px rgba(37,99,235,0.08); }
}

/* ── Search Result Cards ── */
.search-results-wrap {
  margin: 4px 0 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sr-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--c-text-3);
  margin-bottom: 2px;
}
.sr-card {
  display: block;
  padding: 6px 10px;
  background: var(--c-bg-card);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: all var(--duration-fast) var(--ease-default);
}
.sr-card:hover {
  border-color: var(--c-primary-muted);
  background: var(--c-primary-light);
}
.sr-card-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-primary);
  line-height: 1.3;
  margin-bottom: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sr-card-snippet {
  font-size: 11px;
  color: var(--c-text-3);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sr-card-domain {
  font-size: 10px;
  color: var(--c-text-4);
  margin-top: 2px;
}

/* ── Data Visualization Cards ── */
.data-cards-wrap {
  margin: 4px 0 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.data-card {
  padding: 8px 10px;
  background: var(--c-bg-card);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
}
.dc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.dc-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-text-1);
  font-family: var(--font-mono);
}
.dc-semantic {
  font-size: 10px;
  color: var(--c-text-4);
  background: var(--c-bg-sunken);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}
.dc-bar-wrap {
  height: 6px;
  background: var(--c-gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: 4px;
}
.dc-bar {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: var(--radius-full);
  transition: width 0.6s ease;
}
.dc-values {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--c-text-4);
  font-family: var(--font-mono);
}
.dc-span {
  color: var(--c-text-3);
  font-weight: 500;
}

@media (max-width: 1280px) {
  .ai-chat-panel {
    width: 360px;
    min-width: 360px;
    max-width: 360px;
  }
}

@media (max-width: 900px) {
  .ai-chat-panel {
    width: 100%;
    min-width: 100%;
    max-width: 100%;
    height: 320px;
    border-right: none;
    border-bottom: 1px solid var(--c-border);
  }

  .ai-chat-panel.collapsed {
    height: 40px;
    min-height: 40px;
  }

  .ai-chat-panel.collapsed .panel-toggle {
    width: 100%;
    min-width: 100%;
    flex-direction: row;
    justify-content: center;
    padding-top: 0;
    gap: var(--sp-2);
  }

  .ai-chat-panel.collapsed .toggle-label {
    writing-mode: horizontal-tb;
    letter-spacing: 0.4px;
  }

  .panel-header {
    padding: 0 var(--sp-2);
  }

  .header-name {
    font-size: var(--text-sm);
  }
}
</style>
