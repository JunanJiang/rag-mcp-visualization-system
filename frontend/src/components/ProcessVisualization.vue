<template>
  <div class="process-viz">
    <!-- MCP 工具调用时间线 -->
    <div v-if="toolCalls.length > 0" class="viz-section tool-timeline">
      <div class="section-title" @click="showTimeline = !showTimeline">
        <span>🔧 MCP 工具调用链路 ({{ toolCalls.length }})</span>
        <el-icon :size="12"><component :is="showTimeline ? ArrowUp : ArrowDown" /></el-icon>
      </div>
      <transition name="collapse">
        <div v-show="showTimeline" class="timeline-body">
          <div v-for="(tc, i) in toolCalls" :key="i" class="timeline-item" :class="{ error: tc.error }">
            <div class="timeline-dot" :class="getToolCategory(tc.tool)"></div>
            <div class="timeline-content">
              <div class="timeline-header">
                <code class="tool-name">{{ tc.tool }}</code>
                <span class="tool-category" :class="getToolCategory(tc.tool)">{{ getToolCategoryLabel(tc.tool) }}</span>
                <span v-if="tc.duration" class="tool-duration">{{ tc.duration }}ms</span>
              </div>
              <div v-if="tc.args && Object.keys(tc.args).length" class="tool-args">
                <span v-for="(v, k) in tc.args" :key="k" class="arg-chip">{{ k }}: {{ formatArgValue(v) }}</span>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- RAG 检索链路 -->
    <div v-if="ragInfo" class="viz-section rag-chain">
      <div class="section-title" @click="showRag = !showRag">
        <span>📚 RAG 检索链路</span>
        <el-icon :size="12"><component :is="showRag ? ArrowUp : ArrowDown" /></el-icon>
      </div>
      <transition name="collapse">
        <div v-show="showRag" class="rag-body">
          <div class="rag-flow">
            <div class="rag-step">
              <div class="rag-step-icon">🔍</div>
              <div class="rag-step-text">
                <strong>查询</strong>
                <span>{{ ragInfo.query }}</span>
              </div>
            </div>
            <div class="rag-arrow">→</div>
            <div class="rag-step">
              <div class="rag-step-icon">🧮</div>
              <div class="rag-step-text">
                <strong>向量匹配</strong>
                <span>BM25 + 语义检索</span>
              </div>
            </div>
            <div class="rag-arrow">→</div>
            <div class="rag-step">
              <div class="rag-step-icon">📄</div>
              <div class="rag-step-text">
                <strong>Top-{{ ragInfo.chunks?.length || 0 }} 结果</strong>
                <span>注入 Prompt</span>
              </div>
            </div>
          </div>
          <div v-if="ragInfo.chunks?.length" class="rag-results">
            <div v-for="(chunk, i) in ragInfo.chunks" :key="i" class="rag-chunk">
              <div class="chunk-header">
                <span class="chunk-rank">#{{ i + 1 }}</span>
                <span class="chunk-score">相关度: {{ (chunk.score * 100).toFixed(0) }}%</span>
                <span class="chunk-source">{{ chunk.source }}</span>
              </div>
              <div class="chunk-content">{{ chunk.content?.slice(0, 150) }}...</div>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- 质量评估仪表盘 -->
    <div v-if="qualityData" class="viz-section quality-dashboard">
      <div class="section-title">
        <span>📊 质量评估</span>
        <span class="quality-score">{{ qualityData.total_score }}/100</span>
      </div>
      <v-chart :option="qualityRadarOption" autoresize class="quality-chart" />
      <div v-if="qualityData.suggestions?.length" class="quality-suggestions">
        <div v-for="(s, i) in qualityData.suggestions.slice(0, 3)" :key="i" class="suggestion-item">
          💡 {{ s }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, RadarComponent } from 'echarts/components'

use([CanvasRenderer, RadarChart, TitleComponent, TooltipComponent, RadarComponent])

const props = defineProps({
  toolCalls: { type: Array, default: () => [] },
  qualityData: { type: Object, default: null }
})

const showTimeline = ref(true)
const showRag = ref(true)

const ragInfo = computed(() => {
  const ragCall = props.toolCalls.find(tc => tc.tool === 'rag_query')
  if (!ragCall) return null
  return {
    query: ragCall.args?.query || '',
    chunks: ragCall.result?.chunks || []
  }
})

const TOOL_CATEGORIES = {
  get_run_info: 'data', list_signals: 'data', compute_metrics: 'data',
  get_mesh_info: 'data', get_derived_quantities: 'data',
  rag_query: 'knowledge', web_search: 'knowledge',
  auto_configure: 'workflow', generate_next_slot: 'workflow',
  generate_all_slots: 'workflow', accept_all_slots: 'workflow', export_report: 'workflow'
}

function getToolCategory(name) { return TOOL_CATEGORIES[name] || 'other' }
function getToolCategoryLabel(name) {
  const labels = { data: '数据查询', knowledge: '知识检索', workflow: '流程控制' }
  return labels[getToolCategory(name)] || '其他'
}
function formatArgValue(v) {
  if (typeof v === 'string') return v.length > 30 ? v.slice(0, 30) + '...' : v
  return JSON.stringify(v)
}

const qualityRadarOption = computed(() => {
  if (!props.qualityData?.dimensions) return {}
  const dims = props.qualityData.dimensions
  return {
    radar: {
      indicator: [
        { name: '数据覆盖', max: 100 },
        { name: '可追溯性', max: 100 },
        { name: '专业度', max: 100 },
        { name: '连贯性', max: 100 }
      ],
      radius: '65%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: [dims.data_coverage || 0, dims.traceability || 0, dims.professionalism || 0, dims.coherence || 0],
        name: '质量评分',
        areaStyle: { opacity: 0.3 }
      }]
    }]
  }
})
</script>

<style scoped>
.process-viz {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.viz-section {
  border: 1px solid var(--c-border, #e5e7eb);
  border-radius: 8px;
  background: var(--c-bg-card, #fff);
  overflow: hidden;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  background: var(--c-bg-sunken, #f9fafb);
}

.collapse-enter-active, .collapse-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.collapse-enter-from, .collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

/* Timeline */
.timeline-body { padding: 8px 12px; }
.timeline-item {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f3f4f6;
}
.timeline-item:last-child { border-bottom: none; }
.timeline-dot {
  width: 10px; height: 10px;
  border-radius: 50%; margin-top: 4px; flex-shrink: 0;
}
.timeline-dot.data { background: #3b82f6; }
.timeline-dot.knowledge { background: #8b5cf6; }
.timeline-dot.workflow { background: #10b981; }
.timeline-dot.other { background: #9ca3af; }
.timeline-header { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tool-name { font-size: 12px; font-weight: 600; color: #1f2937; background: #f3f4f6; padding: 1px 6px; border-radius: 3px; }
.tool-category { font-size: 10px; padding: 1px 6px; border-radius: 8px; color: white; }
.tool-category.data { background: #3b82f6; }
.tool-category.knowledge { background: #8b5cf6; }
.tool-category.workflow { background: #10b981; }
.tool-duration { font-size: 10px; color: #9ca3af; }
.tool-args { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.arg-chip { font-size: 10px; background: #f3f4f6; padding: 1px 6px; border-radius: 4px; color: #6b7280; }

/* RAG Chain */
.rag-body { padding: 8px 12px; }
.rag-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.rag-step { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #f3f4f6; border-radius: 6px; }
.rag-step-icon { font-size: 16px; }
.rag-step-text { display: flex; flex-direction: column; }
.rag-step-text strong { font-size: 11px; }
.rag-step-text span { font-size: 10px; color: #6b7280; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rag-arrow { color: #9ca3af; font-size: 14px; }
.rag-results { display: flex; flex-direction: column; gap: 6px; }
.rag-chunk { padding: 6px 10px; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 6px; }
.chunk-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.chunk-rank { font-size: 10px; font-weight: 700; color: #7c3aed; }
.chunk-score { font-size: 10px; color: #6b7280; }
.chunk-source { font-size: 10px; color: #9ca3af; margin-left: auto; }
.chunk-content { font-size: 11px; color: #374151; line-height: 1.4; }

/* Quality */
.quality-score { font-size: 16px; font-weight: 700; color: #10b981; }
.quality-chart { width: 100%; height: 200px; }
.quality-suggestions { padding: 8px 12px; border-top: 1px solid #f3f4f6; }
.suggestion-item { font-size: 11px; color: #6b7280; padding: 3px 0; }
</style>
