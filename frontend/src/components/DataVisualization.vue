<template>
  <div class="data-viz-panel">
    <div class="viz-header">
      <h3>数据可视化分析</h3>
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button value="blocks">网格分布</el-radio-button>
        <el-radio-button value="variables">变量范围</el-radio-button>
        <el-radio-button value="radar">流场特征</el-radio-button>
        <el-radio-button value="aspect">网格质量</el-radio-button>
      </el-radio-group>
    </div>

    <div class="viz-body">
      <v-chart v-if="activeTab === 'blocks'" :option="blockChartOption" autoresize class="chart" />
      <v-chart v-else-if="activeTab === 'variables'" :option="variableChartOption" autoresize class="chart" />
      <v-chart v-else-if="activeTab === 'radar'" :option="radarChartOption" autoresize class="chart" />
      <v-chart v-else-if="activeTab === 'aspect'" :option="aspectChartOption" autoresize class="chart" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, RadarChart, ScatterChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, RadarComponent
} from 'echarts/components'

use([CanvasRenderer, BarChart, RadarChart, ScatterChart,
     TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent])

const props = defineProps({
  facts: { type: Object, default: () => ({}) }
})

const activeTab = ref('blocks')

const blocks = computed(() => props.facts?.datasets?.blocks || [])
const variables = computed(() => props.facts?.variables || [])
const derived = computed(() => props.facts?.derived_quantities || {})

const blockChartOption = computed(() => {
  const names = blocks.value.map(b => b.name || `Block_${b.blockIndex}`)
  const points = blocks.value.map(b => b.points || 0)
  return {
    title: { text: '网格块节点数分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: '{b}: {c} 节点' },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 35, fontSize: 10 } },
    yAxis: { type: 'value', name: '节点数', axisLabel: { formatter: v => v >= 1000 ? (v / 1000).toFixed(0) + 'K' : v } },
    grid: { left: 60, right: 20, bottom: 60, top: 40 },
    series: [{
      type: 'bar', data: points,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      colorBy: 'data'
    }]
  }
})

const variableChartOption = computed(() => {
  const vars = variables.value
  const names = vars.map(v => `${v.name}\n(${v.guess_variableName || '?'})`)
  const mins = vars.map(v => v.range_min ?? 0)
  const maxs = vars.map(v => v.range_max ?? 0)
  return {
    title: { text: '变量数值范围对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 10 } },
    xAxis: { type: 'value', name: '数值', axisLabel: { formatter: v => v.toExponential(1) } },
    grid: { left: 100, right: 30, bottom: 30, top: 40 },
    series: [
      { name: 'Min', type: 'bar', data: mins, stack: 'range', itemStyle: { color: '#93c5fd' } },
      { name: 'Max', type: 'bar', data: maxs.map((mx, i) => mx - mins[i]), stack: 'range', itemStyle: { color: '#3b82f6' } }
    ]
  }
})

const radarChartOption = computed(() => {
  const d = derived.value
  const densityRatio = parseFloat(d.density_ratio) || 1
  const compressibility = d.compressibility === '高' ? 80 : d.compressibility === '极高' ? 100 : d.compressibility === '中' ? 50 : 20
  const machMax = d.mach_estimate?.max_estimate || 0
  const machScore = Math.min(100, machMax * 100)
  const velMax = d.velocity_estimates?.speed_max || 0
  const velScore = Math.min(100, velMax / 10)
  const hasReverse = variables.value.some(v => (v.range_min ?? 0) < 0 && (v.range_max ?? 0) > 0)
  const threeDScore = hasReverse ? 75 : 30
  const densityScore = Math.min(100, densityRatio * 10)

  return {
    title: { text: '流场特征雷达图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {},
    radar: {
      indicator: [
        { name: '密度变化', max: 100 },
        { name: '马赫数', max: 100 },
        { name: '压缩性', max: 100 },
        { name: '速度量级', max: 100 },
        { name: '三维性', max: 100 }
      ],
      radius: '60%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: [densityScore, machScore, compressibility, velScore, threeDScore],
        name: '流场特征',
        areaStyle: { opacity: 0.25 }
      }]
    }]
  }
})

const aspectChartOption = computed(() => {
  const data = blocks.value.map(b => {
    const dims = b.dims || []
    if (dims.length < 3) return { name: b.name, ratio: 1 }
    const sorted = [...dims].sort((a, b) => b - a)
    return { name: b.name || `Block_${b.blockIndex}`, ratio: sorted[0] / Math.max(sorted[2], 1) }
  })
  return {
    title: { text: '网格块纵横比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}: 纵横比 ${p[0].value.toFixed(1)}` },
    xAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { rotate: 35, fontSize: 10 } },
    yAxis: { type: 'value', name: '纵横比' },
    grid: { left: 50, right: 20, bottom: 60, top: 40 },
    series: [{
      type: 'bar', data: data.map(d => d.ratio),
      itemStyle: { color: p => p.value > 10 ? '#ef4444' : p.value > 5 ? '#f59e0b' : '#10b981', borderRadius: [4, 4, 0, 0] },
      markLine: { data: [{ yAxis: 10, label: { formatter: '警告线' }, lineStyle: { color: '#ef4444', type: 'dashed' } }], silent: true }
    }]
  }
})
</script>

<style scoped>
.data-viz-panel {
  margin: 16px 0;
  border: 1px solid var(--c-border, #e5e7eb);
  border-radius: 8px;
  background: #fafbfc;
}
.viz-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--c-border, #e5e7eb);
}
.viz-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.viz-body {
  padding: 8px;
}
.chart {
  width: 100%;
  height: 320px;
}
</style>
