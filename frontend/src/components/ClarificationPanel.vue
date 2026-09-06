<template>
  <div class="clarification-panel">
    <div class="clarification-card">
      <div class="card-header">
        <el-icon :size="32" color="#2563eb"><QuestionFilled /></el-icon>
        <div>
          <h2>报告配置</h2>
          <p>请回答以下问题，以便生成更准确的报告</p>
        </div>
      </div>

      <!-- AI 动画指示条 -->
      <div v-if="aiAnimating" class="ai-animating-bar">
        <div class="ai-bar-dot"></div>
        <span>AI 正在自动配置报告参数…</span>
      </div>

      <el-form :model="answers" label-position="top" class="questions-form">
        <!-- 额外输入：型号和项目代码 -->
        <div class="extra-inputs">
          <el-form-item label="模型/项目名称（可选）">
            <el-input v-model="answers.engineModelName" placeholder="如：WP-7测试型" />
          </el-form-item>
          <el-form-item label="项目代码（可选）">
            <el-input v-model="answers.projectCode" placeholder="如：TEST-001" />
          </el-form-item>
        </div>

        <!-- 报告模板选择 -->
        <div class="template-section" v-if="templateList.length">
          <el-form-item label="报告模板" required>
            <div class="template-cards">
              <div
                v-for="t in templateList"
                :key="t.id"
                class="template-option"
                :class="{ selected: answers.template_id === t.id }"
                @click="answers.template_id = t.id"
              >
                <div class="tpl-radio">
                  <div class="tpl-radio-dot" :class="{ active: answers.template_id === t.id }"></div>
                </div>
                <div class="tpl-info">
                  <div class="tpl-name">{{ t.name }}</div>
                  <div class="tpl-desc">{{ t.description }}</div>
                </div>
              </div>
            </div>
          </el-form-item>
        </div>

        <!-- 动态问题 -->
        <div v-for="q in props.questions" :key="q.id" :ref="el => { if (el) questionRefs[q.id] = el }" class="question-item" :class="{ 'ai-highlight': aiHighlightQuestion === q.id }">
          <el-form-item :label="q.question" :required="q.required">
            <!-- 单选 -->
            <template v-if="q.type === 'single_choice'">
              <el-radio-group v-model="answers[q.id]" class="radio-group">
                <el-radio 
                  v-for="opt in q.options" 
                  :key="opt.id" 
                  :value="opt.id"
                  class="radio-option"
                >
                  <div class="option-content">
                    <span class="option-label">{{ opt.label }}</span>
                    <span class="option-desc">{{ opt.description }}</span>
                  </div>
                </el-radio>
              </el-radio-group>
            </template>

            <!-- 多选 -->
            <template v-else-if="q.type === 'multi_choice'">
              <el-checkbox-group v-model="answers[q.id]" class="checkbox-group">
                <el-checkbox 
                  v-for="opt in q.options" 
                  :key="opt.id" 
                  :label="opt.id"
                  class="checkbox-option"
                >
                  <div class="option-content">
                    <span class="option-label">{{ opt.label }}</span>
                    <span class="option-desc">{{ opt.description }}</span>
                  </div>
                </el-checkbox>
              </el-checkbox-group>
            </template>

            <!-- 确认 -->
            <template v-else-if="q.type === 'confirm'">
              <el-switch v-model="answers[q.id]" />
            </template>

            <!-- 文本输入 -->
            <template v-else-if="q.type === 'text'">
              <el-input 
                v-model="answers[q.id]" 
                placeholder="请输入..."
                clearable
              />
            </template>

            <div v-if="q.why_needed" class="why-needed">
              <el-icon><InfoFilled /></el-icon>
              {{ q.why_needed }}
            </div>
          </el-form-item>
        </div>
      </el-form>

      <div class="card-footer">
        <el-button @click="$emit('back')">返回</el-button>
        <el-button type="primary" @click="submit" :loading="submitting">
          开始生成报告
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick, onMounted } from 'vue'
import { QuestionFilled, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  questions: { type: Array, default: () => [] },
  domains: { type: Array, default: () => [] },
  phenomena: { type: Array, default: () => [] },
  purposes: { type: Array, default: () => [] }
})

const emit = defineEmits(['submit', 'back'])

const templateList = ref([])

const answers = reactive({
  engineModelName: '',
  projectCode: '',
  template_id: 'cfd_standard'
})

async function loadTemplates() {
  try {
    const res = await api.get('/templates')
    if (res.data.success) {
      templateList.value = res.data.templates
      if (templateList.value.length && !answers.template_id) {
        answers.template_id = templateList.value[0].id
      }
    }
  } catch { /* ignore */ }
}

onMounted(() => { loadTemplates() })
const submitting = ref(false)
const aiAnimating = ref(false)
const aiHighlightQuestion = ref(null)
const questionRefs = reactive({})

// 初始化默认值
watch(() => props.questions, (questions) => {
  for (const q of questions) {
    if (q.default_value !== undefined && answers[q.id] === undefined) {
      answers[q.id] = q.default_value
    }
  }
}, { immediate: true })

function submit() {
  // 验证必填项
  for (const q of props.questions) {
    if (q.required && !answers[q.id]) {
      ElMessage.warning(`请回答：${q.question}`)
      return
    }
  }

  submitting.value = true
  emit('submit', { ...answers })
  
  // 模拟延迟后重置
  setTimeout(() => {
    submitting.value = false
  }, 1000)
}

/**
 * AI 动画播放：逐个设置答案并高亮当前问题，最后自动提交
 * @param {Object} aiAnswers - AI 选择的答案
 */
async function playAiAnimation(aiAnswers) {
  aiAnimating.value = true
  
  // 逐个问题动画设置答案
  for (const q of props.questions) {
    if (aiAnswers[q.id] !== undefined) {
      aiHighlightQuestion.value = q.id
      await nextTick()
      // 滚动到当前问题，让视角跟随 AI
      const el = questionRefs[q.id]
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
      await sleep(600)
      answers[q.id] = aiAnswers[q.id]
      await nextTick()
      await sleep(400)
    }
  }
  
  // 设置额外字段
  if (aiAnswers.engineModelName) {
    answers.engineModelName = aiAnswers.engineModelName
    await sleep(300)
  }
  if (aiAnswers.projectCode) {
    answers.projectCode = aiAnswers.projectCode
    await sleep(300)
  }
  
  aiHighlightQuestion.value = null
  await sleep(500)
  
  // 自动提交
  aiAnimating.value = false
  submit()
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

defineExpose({ playAiAnimation })
</script>

<style scoped>
.clarification-panel {
  width: 100%;
  max-width: 960px;
  max-height: 90vh;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--c-gray-300) transparent;
}

.clarification-card {
  background: var(--c-bg-card);
  border-radius: var(--radius-2xl);
  padding: var(--sp-8) var(--sp-8);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--c-border-muted);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin-bottom: var(--sp-6);
  padding-bottom: var(--sp-5);
  border-bottom: 1px solid var(--c-border-muted);
}

.card-header h2 {
  margin: 0 0 2px;
  color: var(--c-text-1);
  font-size: var(--text-xl);
  font-weight: 700;
}

.card-header p {
  margin: 0;
  color: var(--c-text-4);
  font-size: var(--text-sm);
}

.extra-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-5);
}

.extra-inputs :deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
  box-shadow: 0 0 0 1px var(--c-border);
}
.extra-inputs :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--c-primary-muted);
}
.extra-inputs :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1.5px var(--c-primary);
}

/* ── 模板选择器 ── */
.template-section {
  margin-bottom: var(--sp-2);
}

.template-cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  width: 100%;
}

.template-option {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border: 1.5px solid var(--c-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
  background: var(--c-bg-card);
}

.template-option:hover {
  border-color: var(--c-primary-muted);
  background: var(--c-primary-light);
}

.template-option.selected {
  border-color: var(--c-primary);
  background: var(--c-primary-light);
  box-shadow: var(--shadow-focus);
}

.tpl-radio {
  margin-top: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--c-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.2s;
}

.template-option.selected .tpl-radio {
  border-color: var(--c-primary);
}

.tpl-radio-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;
  transition: background 0.2s;
}

.tpl-radio-dot.active {
  background: var(--c-primary);
}

.tpl-info {
  flex: 1;
}

.tpl-name {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--c-text-1);
  line-height: 1.4;
}

.tpl-desc {
  font-size: var(--text-xs);
  color: var(--c-text-4);
  line-height: 1.4;
  margin-top: 2px;
}

.question-item {
  margin-bottom: var(--sp-5);
}

.question-item :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--c-text-2);
  font-size: var(--text-base);
  padding-bottom: var(--sp-2);
}

.radio-group,
.checkbox-group {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--sp-2);
  width: 100%;
}

.radio-option,
.checkbox-option {
  display: flex;
  align-items: flex-start;
  padding: var(--sp-3) var(--sp-4);
  border: 1.5px solid var(--c-border);
  border-radius: var(--radius-lg);
  margin: 0;
  height: auto;
  min-height: 60px;
  transition: all var(--duration-normal) var(--ease-default);
  background: var(--c-bg-card);
  box-sizing: border-box;
}

.radio-option:hover,
.checkbox-option:hover {
  border-color: var(--c-primary-muted);
  background: var(--c-primary-light);
}

.radio-option.is-checked,
.checkbox-option.is-checked {
  border-color: var(--c-primary);
  background: var(--c-primary-light);
  box-shadow: var(--shadow-focus);
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-label {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--c-text-1);
  line-height: 1.4;
}

.option-desc {
  font-size: var(--text-xs);
  color: var(--c-text-4);
  line-height: 1.4;
}

.why-needed {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  margin-top: var(--sp-2);
  font-size: var(--text-xs);
  color: var(--c-text-4);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-3);
  margin-top: var(--sp-6);
  padding-top: var(--sp-5);
  border-top: 1px solid var(--c-border-muted);
}

.card-footer .el-button--primary {
  padding: var(--sp-2) var(--sp-6);
  font-weight: 600;
  border-radius: var(--radius-lg);
}

/* ── AI 动画 ── */
.ai-animating-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-4);
  margin-bottom: var(--sp-4);
  background: var(--c-primary-light);
  border: 1px solid var(--c-primary-muted);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--c-primary-hover);
  animation: aiFadeIn 0.3s var(--ease-default);
}

.ai-bar-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-primary);
  animation: aiPulse 1s ease-in-out infinite;
}

@keyframes aiPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}

@keyframes aiFadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.question-item.ai-highlight {
  background: var(--c-primary-light);
  border: 1.5px solid var(--c-primary-muted);
  border-radius: var(--radius-lg);
  padding: var(--sp-3);
  margin-left: calc(-1 * var(--sp-3));
  margin-right: calc(-1 * var(--sp-3));
  transition: all 0.35s var(--ease-default);
  box-shadow: var(--shadow-focus);
}

</style>
