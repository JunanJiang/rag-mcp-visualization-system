<template>
  <div class="document-preview">
    <div class="preview-header">
      <h2>文档预览</h2>
      <el-button type="primary" size="small" @click="refreshFacts">刷新数据</el-button>
    </div>

    <!-- 槽位导航 -->
    <div class="slot-nav">
      <el-dropdown trigger="click" max-height="400">
        <el-button size="small">
          <el-icon><List /></el-icon> 槽位导航 ({{ slots.length }})
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item 
              v-for="(slot, index) in slots" 
              :key="slot.slot_id"
              @click="navigateToSlot(slot)"
              :class="getSlotNavClass(slot)"
            >
              <span class="slot-nav-index">{{ index + 1 }}.</span>
              <span class="slot-nav-name">{{ getSlotDisplayName(slot.slot_id) }}</span>
              <el-tag :type="getSlotStatusType(slot.status)" size="small">
                {{ getSlotStatusText(slot.status) }}
              </el-tag>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- Word文档样式的内容区 -->
    <div class="word-document">
      <div class="document-page">
        <!-- 加载状态 -->
        <div v-if="loading" style="text-align: center; padding: 40px;">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p>加载数据中...</p>
        </div>

        <template v-else>
          <!-- 报告标题 -->
          <div class="doc-title">
            <h1>仿真分析报告</h1>
            <div class="doc-meta">
              <p><strong>发动机型号：</strong>{{ factsData.project?.engine_model_name || '未指定' }}</p>
              <p><strong>项目代码：</strong>{{ factsData.project?.project_code || '未指定' }}</p>
              <p><strong>数据类型：</strong>{{ factsData.manifest?.dataset_type || 'Plot3D' }}</p>
              <p><strong>生成时间：</strong>{{ formatDate(factsData.manifest?.created_at) }}</p>
            </div>
          </div>

          <div class="doc-divider"></div>

        <!-- 1. 分析目的 -->
        <section class="doc-section" id="section-1">
          <h2 class="doc-heading">1. 分析目的</h2>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('analysis_purpose_1')" 
              :is-active="isSlotActive('analysis_purpose_1')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('analysis_purpose_2')" 
              :is-active="isSlotActive('analysis_purpose_2')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
        </section>

        <!-- 2. 几何结构 -->
        <section class="doc-section" id="section-2">
          <h2 class="doc-heading">2. 几何结构</h2>
          <h3 class="doc-subheading">2.1 模型概述</h3>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('geometry_description')" 
              :is-active="isSlotActive('geometry_description')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
        </section>

        <!-- 2.2 几何模型图 -->
        <section class="doc-section" v-if="getGeometryImage()">
          <h3 class="doc-subheading">2.2 几何模型图</h3>
          <div class="doc-image">
            <img :src="getGeometryImage()" alt="几何结构概览" />
          </div>
        </section>

        <!-- 3. 网格结构 -->
        <section class="doc-section" id="section-3">
          <h2 class="doc-heading">3. 网格结构</h2>
          <h3 class="doc-subheading">3.1 网格信息</h3>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('mesh_description')" 
              :is-active="isSlotActive('mesh_description')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
          
          <!-- 网格块表格 -->
          <table class="doc-table" v-if="factsData.datasets?.blocks?.length">
            <thead>
              <tr>
                <th>块名称</th>
                <th>维度 (nx×ny×nz)</th>
                <th>网格点数</th>
                <th>网格单元数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="block in factsData.datasets.blocks" :key="block.name">
                <td>{{ block.name }}</td>
                <td>{{ formatDims(block.dims) }}</td>
                <td>{{ formatNumber(block.points) }}</td>
                <td>{{ formatNumber(block.cells) }}</td>
              </tr>
              <tr class="total-row">
                <td><strong>合计</strong></td>
                <td><strong>{{ factsData.datasets.blocks.length }} 个块</strong></td>
                <td><strong>{{ formatNumber(factsData.datasets.total_points) }}</strong></td>
                <td><strong>{{ formatNumber(factsData.datasets.total_cells) }}</strong></td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- 3.2 网格图 -->
        <section class="doc-section" v-if="getMeshImage()">
          <h3 class="doc-subheading">3.2 网格图</h3>
          <div class="doc-image">
            <img :src="getMeshImage()" alt="网格概览" />
          </div>
        </section>

        <!-- 4. 后处理 -->
        <section class="doc-section" id="section-4" v-if="factsData.automation_ops?.length">
          <h2 class="doc-heading">4. 后处理</h2>
          <div v-for="op in factsData.automation_ops" :key="op.folder">
            <h3 class="doc-subheading" v-if="op.operation_type">{{ getOperationTypeName(op.operation_type) }}</h3>
            <div class="doc-paragraph" v-if="op.variable_name">
              变量：<strong>{{ op.variable_name }}</strong>
            </div>
            <!-- 后处理图片 -->
            <div v-if="op.images?.length" class="automation-images">
              <div v-for="img in op.images" :key="img" class="doc-image">
                <img :src="getAutomationImage(img)" :alt="op.operation_type" />
              </div>
            </div>
          </div>
        </section>

        <!-- 5. 评定准则 -->
        <section class="doc-section" id="section-5">
          <h2 class="doc-heading">5. 评定准则</h2>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('evaluation_criteria_1')" 
              :is-active="isSlotActive('evaluation_criteria_1')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('evaluation_criteria_2')" 
              :is-active="isSlotActive('evaluation_criteria_2')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
        </section>

        <!-- 6. 分析结果 -->
        <section class="doc-section" id="section-6">
          <h2 class="doc-heading">6. 分析结果</h2>
          <h3 class="doc-subheading">6.1 变量语义说明</h3>
          <div class="doc-paragraph">
            本数据包采用 Plot3D 格式，包含以下变量：
          </div>
          
          <!-- 变量表格 -->
          <table class="doc-table" v-if="factsData.variables?.length">
            <thead>
              <tr>
                <th>变量名</th>
                <th>推断语义</th>
                <th>数值范围</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in factsData.variables" :key="v.name">
                <td>{{ v.name }}</td>
                <td>{{ v.guess_variableName }}</td>
                <td>{{ formatRange(v.range_min, v.range_max) }}</td>
              </tr>
            </tbody>
          </table>

          <!-- 各变量详细说明 -->
          <div v-for="(v, i) in factsData.variables" :key="v.name">
            <h3 class="doc-subheading">6.{{ i + 2 }} {{ getVariableName(v) }}（{{ v.name }}）</h3>
            
            <!-- 变量图片 -->
            <div class="doc-image" v-if="getVariableImage(v.name)">
              <img :src="getVariableImage(v.name)" :alt="v.name + ' 分布图'" />
            </div>
            
            <!-- 变量描述槽位 -->
            <div class="doc-paragraph">
              <SlotRenderer 
                :slot="getSlot('variable_' + v.name)" 
                :is-active="isSlotActive('variable_' + v.name)"
                @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
              >
                <template #context>
                  变量 <strong>{{ v.name }}</strong> 对应 <strong>{{ v.guess_variableName }}</strong>（{{ getVariableName(v) }}），
                  数值范围为 {{ formatRange(v.range_min, v.range_max) }}。
                </template>
              </SlotRenderer>
            </div>
          </div>
        </section>

        <!-- 7. 结论 -->
        <section class="doc-section" id="section-7">
          <h2 class="doc-heading">7. 结论</h2>
          <div class="doc-paragraph">
            <SlotRenderer 
              :slot="getSlot('conclusion')" 
              :is-active="isSlotActive('conclusion')"
              @click="selectSlot" @accept="onSlotAccept" @reject="onSlotReject" @edit="onSlotEdit" @rewrite="onSlotRewrite"
            />
          </div>
        </section>

        <div class="doc-footer">
          <p><em>本报告由 Simuvision 智能仿真报告生成工具自动生成</em></p>
        </div>
        </template>
      </div>
    </div>

    <el-drawer
      v-model="editorVisible"
      direction="rtl"
      size="560px"
      :with-header="false"
      append-to-body
      class="slot-editor-drawer"
    >
      <div v-if="editingSlot" class="slot-editor-panel">
        <div class="slot-editor-head">
          <div>
            <div class="slot-editor-kicker">槽位编辑</div>
            <h3 class="slot-editor-title">{{ formatSlotId(editingSlot.slot_id) }}</h3>
          </div>
          <el-tag :type="getSlotStatusType(editingSlot.status)" size="small">
            {{ getSlotStatusText(editingSlot.status) }}
          </el-tag>
        </div>

        <div class="slot-editor-meta">你可以在右侧完整修改当前段落内容，保存后会同步更新到报告预览中。</div>

        <el-input
          v-model="editContent"
          type="textarea"
          resize="none"
          :autosize="{ minRows: 16, maxRows: 24 }"
          class="slot-editor-textarea"
          placeholder="请输入修改后的段落内容"
        />

        <div class="slot-editor-footer">
          <el-button @click="closeEditor">取消</el-button>
          <el-button type="primary" @click="saveEditor">保存修改</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, h, watch, onMounted, ref } from 'vue'
import { Loading, List } from '@element-plus/icons-vue'
import api from '../api'
// DataVisualization removed per user request

// 加载状态
const loading = ref(false)

// 本地facts数据
const factsData = ref({})

// 刷新 facts 数据
async function refreshFacts() {
  loading.value = true
  try {
    const res = await api.get('/data-package/facts')
    if (res.data.success && res.data.facts) {
      factsData.value = res.data.facts
      console.log('DocumentPreview refreshed facts:', {
        manifest_block_count: factsData.value.manifest?.block_count,
        datasets_blocks: factsData.value.datasets?.blocks?.length,
        variables_count: factsData.value.variables?.length
      })
    }
  } catch (e) {
    console.error('Failed to refresh facts:', e)
  } finally {
    loading.value = false
  }
}

// 槽位渲染组件（含内联操作栏）
const SlotRenderer = {
  props: ['slot', 'isActive'],
  emits: ['click', 'accept', 'reject', 'edit', 'rewrite'],
  setup(props, { emit: slotEmit, slots }) {
    const handleClick = () => {
      if (props.slot) slotEmit('click', props.slot)
    }
    const stop = (e) => e.stopPropagation()
    const onAccept = (e) => { stop(e); slotEmit('accept', props.slot.slot_id) }
    const onReject = (e) => { stop(e); slotEmit('reject', { slotId: props.slot.slot_id, reason: 'manual', feedback: '' }) }
    const onRewrite = (e) => { stop(e); slotEmit('rewrite', props.slot.slot_id) }
    const onStartEdit = (e) => {
      stop(e)
      slotEmit('edit', { mode: 'open', slot: props.slot })
    }

    return () => {
      if (!props.slot) {
        return h('span', { class: 'slot-missing' }, '[槽位未定义]')
      }

      const status = props.slot.status
      const content = props.slot.content
      const contextSlot = slots.context
      const slotId = props.slot.slot_id

      // 编辑按钮（对 draft / rejected / accepted 状态都可用）
      const editBtn = (status === 'draft' || status === 'rejected' || status === 'accepted' || status === 'user_edited')
        ? h('button', { class: 'slot-action-btn edit', onClick: onStartEdit, title: '手动编辑' }, [
            h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
              h('path', { d: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' }),
              h('path', { d: 'M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z' })
            ]),
            h('span', '编辑')
          ])
        : null

      const actionButtons = []
      if (status === 'draft') {
        actionButtons.push(
          h('button', { class: 'slot-action-btn accept', onClick: onAccept, title: '接受' }, [
            h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
              h('polyline', { points: '20 6 9 17 4 12' })
            ]),
            h('span', '确认')
          ]),
          h('button', { class: 'slot-action-btn reject', onClick: onReject, title: '拒绝' }, [
            h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
              h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
              h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
            ]),
            h('span', '拒绝')
          ])
        )
      } else if (status === 'rejected') {
        actionButtons.push(
          h('button', { class: 'slot-action-btn rewrite', onClick: onRewrite, title: '重新生成' }, [
            h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
              h('polyline', { points: '23 4 23 10 17 10' }),
              h('path', { d: 'M20.49 15a9 9 0 1 1-2.12-9.36L23 10' })
            ]),
            h('span', '重写')
          ])
        )
      }
      if (editBtn) actionButtons.push(editBtn)

      return h('div', { 
        id: `slot-${slotId}`,
        class: ['slot-inline', status, { 'has-content': content, 'is-active': props.isActive }],
        onClick: handleClick
      }, [
        contextSlot ? h('span', { class: 'slot-context' }, contextSlot()) : null,
        h('span', { 
          class: 'slot-content-inline',
          title: '点击查看详情'
        }, [
          status === 'pending' 
            ? h('span', { class: 'slot-placeholder' }, `[${props.slot.placeholder_text || '待生成'}]`)
            : content || '[无内容]'
        ]),
        h('span', { class: 'slot-indicator' }, getStatusIcon(status)),
        actionButtons.length > 0
          ? h('span', { class: 'slot-actions' }, actionButtons)
          : null
      ])
    }
  }
}

function getStatusIcon(status) {
  const icons = {
    pending: '⏳',
    draft: '⚠️',
    accepted: '✓',
    rejected: '✗',
    user_edited: '✏️'
  }
  return icons[status] || ''
}

const props = defineProps({
  slots: { type: Array, default: () => [] },
  facts: { type: Object, default: () => ({}) },
  policy: { type: Object, default: () => ({}) },
  activeSlotId: { type: String, default: null }
})

const editorVisible = ref(false)
const editingSlotId = ref('')
const editContent = ref('')
const editingSlot = computed(() => {
  return editingSlotId.value ? getSlot(editingSlotId.value) : null
})

function openEditor(slot) {
  if (!slot) return
  editingSlotId.value = slot.slot_id
  editContent.value = slot.content || ''
  editorVisible.value = true
  emit('slot-click', slot)
}

function closeEditor() {
  editorVisible.value = false
}

function saveEditor() {
  if (!editingSlotId.value) return
  emit('slot-edit', { slotId: editingSlotId.value, content: editContent.value })
  editorVisible.value = false
}

watch(editorVisible, (visible) => {
  if (!visible) {
    editingSlotId.value = ''
    editContent.value = ''
  }
})

// 滚动到指定槽位
function scrollToSlot(slotId) {
  const element = document.getElementById(`slot-${slotId}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

// 滚动到指定章节
function scrollToSection(sectionId) {
  const element = document.getElementById(sectionId)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 监听activeSlotId变化，自动滚动
watch(() => props.activeSlotId, (newSlotId) => {
  if (newSlotId) {
    // 延迟一点确保DOM已更新
    setTimeout(() => scrollToSlot(newSlotId), 100)
  }
}, { immediate: true })

// 检查槽位是否激活
function isSlotActive(slotId) {
  return props.activeSlotId === slotId
}

// 组件挂载时加载facts
onMounted(() => {
  refreshFacts()
})

// 监听props.slots变化，重新加载facts
watch(() => props.slots, (newSlots) => {
  if (newSlots && newSlots.length > 0) {
    refreshFacts()
    if (editingSlotId.value) {
      const latestSlot = newSlots.find(slot => slot.slot_id === editingSlotId.value)
      if (latestSlot) {
        editContent.value = latestSlot.content || editContent.value
      }
    }
  }
}, { immediate: true })

const emit = defineEmits(['slot-click', 'slot-accept', 'slot-reject', 'slot-edit', 'slot-rewrite'])

function onSlotAccept(slotId) { emit('slot-accept', slotId) }
function onSlotReject(data) { emit('slot-reject', data) }
function onSlotEdit(data) {
  if (data?.mode === 'open') {
    openEditor(data.slot)
    return
  }
  emit('slot-edit', data)
}
function onSlotRewrite(slotId) { emit('slot-rewrite', slotId) }

function selectSlot(slot) {
  emit('slot-click', slot)
}

function getSlot(slotId) {
  return props.slots.find(s => s.slot_id === slotId)
}

// 章节定义
const sectionDefs = {
  '1': { id: '1', title: '1. 分析目的' },
  '2': { id: '2', title: '2. 几何结构' },
  '3': { id: '3', title: '3. 网格结构' },
  '4': { id: '4', title: '4. 后处理' },
  '5': { id: '5', title: '5. 评定准则' },
  '6': { id: '6', title: '6. 分析结果' },
  '7': { id: '7', title: '7. 结论' }
}

// 按章节分组
const groupedSlots = computed(() => {
  const groups = {}
  
  for (const slot of props.slots) {
    const sectionId = slot.section || 'other'
    if (!groups[sectionId]) {
      groups[sectionId] = {
        ...sectionDefs[sectionId] || { id: sectionId, title: `章节 ${sectionId}` },
        slots: []
      }
    }
    groups[sectionId].slots.push(slot)
  }
  
  return Object.values(groups).sort((a, b) => a.id.localeCompare(b.id))
})

// 领域名称映射（面向 SimuVision Desktop 支持的仿真场景）
const domainNames = {
  external_aero: '外流气动分析',
  turbomachinery: '叶轮机械',
  internal_flow: '内流分析',
  heat_transfer: '传热与热防护',
  structural: '结构力学',
  general_cfd: '通用CFD'
}

// 目的名称映射
const purposeNames = {
  show: '展示结果',
  diagnose: '问题诊断',
  compare: '方案对比',
  acceptance: '验收评估'
}

function getDomainName(domain) {
  return domainNames[domain] || domain
}

function getPurposeName(purpose) {
  return purposeNames[purpose] || purpose
}

function formatSlotId(slotId) {
  return getSlotDisplayName(slotId)
}

// 槽位显示名称
function getSlotDisplayName(slotId) {
  const nameMap = {
    analysis_purpose_1: '分析目的 1',
    analysis_purpose_2: '分析目的 2',
    geometry_description: '几何描述',
    mesh_description: '网格描述',
    evaluation_criteria_1: '评定准则 1',
    evaluation_criteria_2: '评定准则 2',
    conclusion: '结论'
  }
  
  if (nameMap[slotId]) return nameMap[slotId]
  
  if (slotId.startsWith('variable_')) {
    return `变量 ${slotId.replace('variable_', '')}`
  }
  
  return slotId
}

// 槽位导航相关函数
function navigateToSlot(slot) {
  scrollToSlot(slot.slot_id)
  selectSlot(slot)
}

function getSlotNavClass(slot) {
  return {
    'slot-nav-active': props.activeSlotId === slot.slot_id,
    'slot-nav-pending': slot.status === 'pending',
    'slot-nav-draft': slot.status === 'draft',
    'slot-nav-accepted': slot.status === 'accepted'
  }
}

function getSlotStatusType(status) {
  const types = {
    pending: 'info',
    draft: 'warning',
    accepted: 'success',
    rejected: 'danger',
    user_edited: 'primary'
  }
  return types[status] || 'info'
}

function getSlotStatusText(status) {
  const texts = {
    pending: '待生成',
    draft: '已生成',
    accepted: '已确认',
    rejected: '已拒绝',
    user_edited: '已编辑'
  }
  return texts[status] || status
}

function getStatusType(status) {
  const types = {
    pending: 'info',
    draft: 'warning',
    accepted: 'success',
    rejected: 'danger',
    user_edited: 'primary'
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    pending: '待生成',
    draft: '待确认',
    accepted: '已接受',
    rejected: '已拒绝',
    user_edited: '已编辑'
  }
  return texts[status] || status
}

function truncateContent(content, maxLen = 150) {
  if (!content) return ''
  if (content.length <= maxLen) return content
  return content.substring(0, maxLen) + '...'
}

function formatDate(dateStr) {
  if (!dateStr) return new Date().toLocaleString('zh-CN')
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatNumber(num) {
  if (!num) return '0'
  return num.toLocaleString()
}

function formatRange(min, max) {
  if (typeof min === 'number' && typeof max === 'number') {
    return `${min.toExponential(2)} ~ ${max.toExponential(2)}`
  }
  return `${min} ~ ${max}`
}

function getVariableName(variable) {
  const nameMap = {
    density: '密度',
    MomentumX: 'X方向动量',
    MomentumY: 'Y方向动量',
    MomentumZ: 'Z方向动量',
    EnergyStagnationDensity: '总能量密度'
  }
  const guess = variable.guess_variableName
  return nameMap[guess] || guess || variable.name
}

function formatDims(dims) {
  if (!dims || !dims.length) return 'N/A'
  return dims.join('×')
}

function getGeometryImage() {
  const images = factsData.value?.images?.geometry || []
  if (images.length > 0) {
    const img = images[0]
    return img.startsWith('/api/') ? `http://localhost:5000${img}` : img
  }
  return null
}

function getMeshImage() {
  const images = factsData.value?.images?.mesh || []
  if (images.length > 0) {
    const img = images[0]
    return img.startsWith('/api/') ? `http://localhost:5000${img}` : img
  }
  return null
}

function getVariableImage(varName) {
  const images = factsData.value?.images?.variables || []
  const img = images.find(p => p.includes(varName))
  if (img) {
    return img.startsWith('/api/') ? `http://localhost:5000${img}` : img
  }
  return null
}

function getAutomationImage(imgPath) {
  if (!imgPath) return null
  if (imgPath.startsWith('/api/')) {
    return `http://localhost:5000${imgPath}`
  }
  if (imgPath.startsWith('http')) {
    return imgPath
  }
  // 相对路径，构建API路径
  return `http://localhost:5000/api/images/${imgPath}`
}

defineExpose({ scrollToSlot, scrollToSection, refreshFacts })

function getOperationTypeName(opType) {
  const typeNames = {
    'contourLine': '等值线图',
    'isosurface': '等值面图',
    'streamline': '流线图',
    'slice': '切片图',
    'vector': '矢量图'
  }
  return typeNames[opType] || opType
}
</script>

<style scoped>
.document-preview {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--c-bg-sunken);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-3) var(--sp-5);
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
}

.preview-header h2 {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--c-text-1);
}

.legend {
  display: flex;
  gap: var(--sp-2);
}

.legend-item {
  font-size: var(--text-xs);
  padding: 2px var(--sp-2);
  border-radius: var(--radius-sm);
}

.legend-item.pending { background: var(--c-bg-sunken); color: var(--c-text-4); }
.legend-item.draft { background: #fff3cd; color: #856404; }
.legend-item.accepted { background: #d4edda; color: #155724; }
.legend-item.rejected { background: #f8d7da; color: #721c24; }
.legend-item.user_edited { background: #d1ecf1; color: #0c5460; }

/* Word文档样式 */
.word-document {
  flex: 1;
  overflow: auto;
  padding: 32px 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--c-gray-300) transparent;
}

.document-page {
  max-width: 820px;
  margin: 0 auto;
  background: #fff;
  padding: 56px 72px;
  box-shadow: var(--shadow-md);
  min-height: 100%;
  font-family: 'Times New Roman', '宋体', serif;
  line-height: 1.8;
  color: #000;
}

.doc-title {
  text-align: center;
  margin-bottom: 40px;
}

.doc-title h1 {
  font-size: 28px;
  font-weight: bold;
  margin: 0 0 20px;
  color: #000;
}

.doc-meta {
  text-align: left;
  margin-top: 30px;
}

.doc-meta p {
  margin: 8px 0;
  font-size: 14px;
}

.doc-divider {
  border-top: 2px solid #000;
  margin: 30px 0;
}

.doc-section {
  margin-bottom: 30px;
}

.doc-heading {
  font-size: 20px;
  font-weight: bold;
  margin: 24px 0 12px;
  color: #000;
}

.doc-subheading {
  font-size: 16px;
  font-weight: bold;
  margin: 16px 0 8px;
  color: #000;
}

.doc-paragraph {
  margin: 12px 0;
  text-indent: 2em;
  font-size: 14px;
  text-align: justify;
}

.doc-image {
  margin: 16px 0;
  text-align: center;
}

.doc-image img {
  max-width: 100%;
  max-height: 400px;
  border: 1px solid #ddd;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.total-row {
  background: #f5f5f5;
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 13px;
}

.doc-table th,
.doc-table td {
  border: 1px solid #000;
  padding: 8px 12px;
  text-align: left;
}

.doc-table th {
  background: #f0f0f0;
  font-weight: bold;
}

.doc-footer {
  margin-top: 60px;
  text-align: center;
  font-size: 12px;
  color: #666;
}

/* 槽位导航 */
.slot-nav {
  margin-bottom: var(--sp-2);
  padding: 0 var(--sp-4);
  flex-shrink: 0;
}

.slot-nav .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-4);
}

.slot-nav-index {
  color: var(--c-text-4);
  font-size: var(--text-xs);
  min-width: 20px;
}

.slot-nav-name {
  flex: 1;
  font-size: var(--text-sm);
}

.slot-nav-active {
  background: var(--c-primary-light) !important;
}

.slot-nav-pending .slot-nav-name { color: var(--c-text-4); }
.slot-nav-draft .slot-nav-name { color: #e6a23c; }
.slot-nav-accepted .slot-nav-name { color: #67c23a; font-weight: 500; }

/* 槽位内联样式 */
.slot-inline {
  display: inline;
  position: relative;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
  border-radius: var(--radius-sm);
}

.slot-inline.is-active {
  outline: 2px solid var(--c-primary);
  outline-offset: 3px;
  background: var(--c-primary-light);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { outline-color: var(--c-primary); }
  50% { outline-color: var(--c-primary-muted); }
}

.slot-context { color: #000; }

.slot-content-inline {
  display: inline;
  padding: 1px 3px;
  border-radius: 3px;
  transition: all var(--duration-fast) var(--ease-default);
}

.slot-inline.pending .slot-content-inline {
  background: #fff9e6;
  border-bottom: 2px dashed #e6a23c;
  color: #856404;
}

.slot-inline.draft .slot-content-inline {
  background: #fff3cd;
  border-bottom: 2px solid #ffc107;
  color: #000;
}

.slot-inline.accepted .slot-content-inline {
  background: transparent;
  color: #000;
}

.slot-inline.rejected .slot-content-inline {
  background: #f8d7da;
  border-bottom: 2px solid #dc3545;
  color: #721c24;
}

.slot-inline.user_edited .slot-content-inline {
  background: #fff7ed;
  border-bottom: 2px solid #f59e0b;
  color: #92400e;
}

.slot-inline:hover .slot-content-inline {
  background: var(--c-primary-light);
  box-shadow: 0 0 0 2px var(--c-primary-muted);
}

.slot-indicator { margin-left: 3px; font-size: 11px; }

.slot-inline.user_edited .slot-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f59e0b;
  color: white;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 9px;
  vertical-align: middle;
}

.slot-placeholder { font-style: italic; color: #999; }
.slot-missing { color: #ccc; font-style: italic; }

.slot-actions {
  display: none;
  margin-left: 8px;
  gap: 6px;
  vertical-align: middle;
  animation: slotActionsFadeIn 0.16s ease-out;
}
@keyframes slotActionsFadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}
.slot-inline:hover .slot-actions,
.slot-inline.is-active .slot-actions {
  display: inline-flex;
}
.slot-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid currentColor;
  border-radius: 999px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  background: #ffffff;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}
.slot-action-btn svg {
  flex-shrink: 0;
}
.slot-action-btn:hover {
  transform: translateY(-1px);
}
.slot-action-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.14);
}
.slot-action-btn.accept {
  color: #16a34a;
  border-color: #86efac;
}
.slot-action-btn.accept:hover {
  background: #16a34a;
  border-color: #16a34a;
  color: #ffffff;
}
.slot-action-btn.reject {
  color: #dc2626;
  border-color: #fca5a5;
}
.slot-action-btn.reject:hover {
  background: #dc2626;
  border-color: #dc2626;
  color: #ffffff;
}
.slot-action-btn.rewrite {
  color: #2563eb;
  border-color: #93c5fd;
}
.slot-action-btn.rewrite:hover {
  background: #2563eb;
  border-color: #2563eb;
  color: #ffffff;
}
.slot-action-btn.edit {
  color: #7c3aed;
  border-color: #c4b5fd;
}
.slot-action-btn.edit:hover {
  background: #7c3aed;
  border-color: #7c3aed;
  color: #ffffff;
}
.slot-action-btn.save {
  color: #16a34a;
  border-color: #86efac;
}
.slot-action-btn.save:hover {
  background: #16a34a;
  border-color: #16a34a;
  color: #ffffff;
}
.slot-action-btn.cancel {
  color: #6b7280;
  border-color: #d1d5db;
}
.slot-action-btn.cancel:hover {
  background: #6b7280;
  border-color: #6b7280;
  color: #ffffff;
}

:deep(.slot-editor-drawer .el-drawer) {
  background: #ffffff;
}

:deep(.slot-editor-drawer .el-drawer__body) {
  padding: 0;
}

.slot-editor-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 28px 24px 20px;
  background: linear-gradient(180deg, #ffffff 0%, #faf7ff 100%);
}

.slot-editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.slot-editor-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #7c3aed;
  text-transform: uppercase;
}

.slot-editor-title {
  margin: 6px 0 0;
  font-size: 22px;
  line-height: 1.35;
  color: #111827;
}

.slot-editor-meta {
  margin-bottom: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}

.slot-editor-textarea {
  flex: 1;
}

.slot-editor-textarea :deep(.el-textarea__inner) {
  min-height: 100% !important;
  font-size: 15px;
  line-height: 1.9;
  color: #111827;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}

.slot-editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}
</style>
