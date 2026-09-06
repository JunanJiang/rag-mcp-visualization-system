<template>
  <div class="page-container">
    <el-row :gutter="24">
      <!-- 左侧：卡片列表 -->
      <el-col :span="12">
        <div class="card">
          <div class="card-title">
            <el-icon><Collection /></el-icon>
            知识卡片列表
            <el-button 
              type="primary" 
              size="small" 
              @click="showCreateDialog"
              style="margin-left: auto;"
            >
              <el-icon><Plus /></el-icon>
              新建卡片
            </el-button>
          </div>

          <!-- 搜索栏 -->
          <el-input
            v-model="searchQuery"
            placeholder="搜索知识卡片..."
            clearable
            style="margin-bottom: 16px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-state">
            <el-skeleton :rows="5" animated />
          </div>

          <!-- 卡片列表 -->
          <div v-else class="card-list">
            <div
              v-for="card in filteredCards"
              :key="card.id"
              class="card-item"
              :class="{ active: selectedCard?.id === card.id }"
              @click="selectCard(card)"
            >
              <div class="card-item-title">{{ card.title }}</div>
              <div class="card-item-tags">
                <el-tag 
                  v-for="tag in card.tags?.slice(0, 3)" 
                  :key="tag" 
                  size="small"
                  type="info"
                >
                  {{ tag }}
                </el-tag>
              </div>
              <div class="card-item-preview">{{ card.content_preview }}</div>
            </div>

            <el-empty v-if="filteredCards.length === 0" description="暂无卡片" />
          </div>
        </div>
      </el-col>

      <!-- 右侧：卡片详情/编辑 -->
      <el-col :span="12">
        <div class="card">
          <div class="card-title">
            <el-icon><Document /></el-icon>
            {{ isEditing ? '编辑卡片' : '卡片详情' }}
            <div v-if="selectedCard && !isEditing" style="margin-left: auto; display: flex; gap: 8px;">
              <el-button size="small" @click="startEdit">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="confirmDelete">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>

          <!-- 无选中状态 -->
          <div v-if="!selectedCard && !isCreating" class="empty-state">
            <el-empty description="请选择一个知识卡片查看详情" />
          </div>

          <!-- 查看模式 -->
          <div v-else-if="!isEditing && !isCreating" class="detail-view">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="ID">
                <code>{{ selectedCard.id }}</code>
              </el-descriptions-item>
              <el-descriptions-item label="标题">
                {{ selectedCard.title }}
              </el-descriptions-item>
              <el-descriptions-item label="标签">
                <el-tag 
                  v-for="tag in selectedCard.tags" 
                  :key="tag" 
                  size="small"
                  style="margin-right: 4px;"
                >
                  {{ tag }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="报告模块">
                <el-tag 
                  v-for="mod in selectedCard.report_modules" 
                  :key="mod" 
                  size="small"
                  type="success"
                  style="margin-right: 4px;"
                >
                  {{ mod }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="源文件">
                <code>{{ selectedCard.source_file }}</code>
              </el-descriptions-item>
            </el-descriptions>

            <div class="content-section">
              <h4>内容</h4>
              <div class="content-text markdown-body" v-html="renderMd(selectedCard.content)"></div>
            </div>
          </div>

          <!-- 编辑/创建模式 -->
          <div v-else class="edit-view">
            <el-form :model="editForm" label-width="100px">
              <el-form-item label="ID" v-if="isCreating">
                <el-input v-model="editForm.id" placeholder="自动生成或自定义" />
              </el-form-item>
              <el-form-item label="标题" required>
                <el-input v-model="editForm.title" placeholder="请输入标题" />
              </el-form-item>
              <el-form-item label="标签">
                <el-select
                  v-model="editForm.tags"
                  multiple
                  filterable
                  allow-create
                  placeholder="选择或输入标签"
                  style="width: 100%;"
                >
                  <el-option
                    v-for="tag in commonTags"
                    :key="tag"
                    :label="tag"
                    :value="tag"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="报告模块">
                <el-select
                  v-model="editForm.report_modules"
                  multiple
                  placeholder="选择相关报告模块"
                  style="width: 100%;"
                >
                  <el-option label="分析目的" value="purpose" />
                  <el-option label="几何模型" value="geometry" />
                  <el-option label="分析模型" value="model" />
                  <el-option label="评定准则" value="criteria" />
                  <el-option label="分析结果" value="results" />
                  <el-option label="结论" value="conclusion" />
                </el-select>
              </el-form-item>
              <el-form-item label="内容" required>
                <el-input
                  v-model="editForm.content"
                  type="textarea"
                  :rows="12"
                  placeholder="请输入 Markdown 内容"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveCard" :loading="saving">
                  {{ isCreating ? '创建' : '保存' }}
                </el-button>
                <el-button @click="cancelEdit">取消</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import { marked } from 'marked'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Collection, Plus, Search, Document, 
  Edit, Delete 
} from '@element-plus/icons-vue'

marked.setOptions({ breaks: true, gfm: true })
const renderMd = (text) => { try { return marked.parse(text || '') } catch { return text || '' } }

const loading = ref(false)
const saving = ref(false)
const cards = ref([])
const selectedCard = ref(null)
const searchQuery = ref('')
const isEditing = ref(false)
const isCreating = ref(false)

const editForm = reactive({
  id: '',
  title: '',
  tags: [],
  report_modules: [],
  content: ''
})

const commonTags = [
  'plot3d', 'cfd', '变量解释', '结果解读', 
  '数据格式', '后处理', '网格', '边界条件'
]

const filteredCards = computed(() => {
  if (!searchQuery.value) return cards.value
  const query = searchQuery.value.toLowerCase()
  return cards.value.filter(card => 
    card.title?.toLowerCase().includes(query) ||
    card.tags?.some(t => t.toLowerCase().includes(query)) ||
    card.content_preview?.toLowerCase().includes(query)
  )
})

const loadCards = async () => {
  loading.value = true
  try {
    const response = await api.get('/kb/cards')
    if (response.data.success) {
      cards.value = response.data.cards
    }
  } catch (error) {
    ElMessage.error('加载知识卡片失败')
  } finally {
    loading.value = false
  }
}

const selectCard = async (card) => {
  try {
    const response = await api.get(`/kb/cards/${card.id}`)
    if (response.data.success) {
      selectedCard.value = response.data.card
      isEditing.value = false
      isCreating.value = false
    }
  } catch (error) {
    ElMessage.error('获取卡片详情失败')
  }
}

const showCreateDialog = () => {
  selectedCard.value = null
  isCreating.value = true
  isEditing.value = false
  Object.assign(editForm, {
    id: '',
    title: '',
    tags: [],
    report_modules: [],
    content: ''
  })
}

const startEdit = () => {
  isEditing.value = true
  Object.assign(editForm, {
    id: selectedCard.value.id,
    title: selectedCard.value.title,
    tags: selectedCard.value.tags || [],
    report_modules: selectedCard.value.report_modules || [],
    content: selectedCard.value.content || ''
  })
}

const cancelEdit = () => {
  isEditing.value = false
  isCreating.value = false
}

const saveCard = async () => {
  if (!editForm.title || !editForm.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }

  saving.value = true
  try {
    let response
    if (isCreating.value) {
      response = await api.post('/kb/cards', editForm)
    } else {
      response = await api.put(`/kb/cards/${editForm.id}`, editForm)
    }

    if (response.data.success) {
      ElMessage.success(isCreating.value ? '创建成功' : '保存成功')
      isEditing.value = false
      isCreating.value = false
      await loadCards()
    } else {
      ElMessage.error(response.data.error)
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const confirmDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除知识卡片「${selectedCard.value.title}」吗？`,
      '删除确认',
      { type: 'warning' }
    )
    
    const response = await api.delete(`/kb/cards/${selectedCard.value.id}`)
    if (response.data.success) {
      ElMessage.success('删除成功')
      selectedCard.value = null
      await loadCards()
    } else {
      ElMessage.error(response.data.error)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadCards()
})
</script>

<style scoped>
.page-container {
  padding: var(--sp-6);
  height: 100%;
  box-sizing: border-box;
  overflow: auto;
}

.card {
  background: var(--c-bg-card);
  border: 1px solid var(--c-border-muted);
  border-radius: var(--radius-2xl);
  padding: var(--sp-5);
  box-shadow: var(--shadow-sm);
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--c-text-1);
  margin-bottom: var(--sp-4);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--c-border-muted);
}

.card-list {
  height: calc(100vh - 220px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--c-gray-300) transparent;
  padding-right: var(--sp-1);
}

.card-item {
  padding: var(--sp-4);
  border: 1.5px solid var(--c-border);
  border-radius: var(--radius-lg);
  margin-bottom: var(--sp-2);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
  background: var(--c-bg-card);
}

.card-item:hover {
  border-color: var(--c-primary-muted);
  background: var(--c-primary-light);
}

.card-item.active {
  border-color: var(--c-primary);
  background: var(--c-primary-light);
  box-shadow: var(--shadow-focus);
}

.card-item-title {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--c-text-1);
  margin-bottom: var(--sp-2);
  line-height: 1.4;
}

.card-item-tags {
  margin-bottom: var(--sp-2);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}

.card-item-preview {
  font-size: var(--text-sm);
  color: var(--c-text-4);
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.loading-state {
  padding: var(--sp-5) 0;
}

.empty-state {
  padding: 80px 0;
}

.detail-view {
  padding: var(--sp-2) 0;
}

.content-section {
  margin-top: var(--sp-5);
}

.content-section h4 {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--c-text-2);
  margin: 0 0 var(--sp-3);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--c-border-muted);
}

.content-text {
  line-height: 1.7;
  font-size: var(--text-sm);
  color: var(--c-text-2);
  background: var(--c-bg-sunken);
  padding: var(--sp-4) var(--sp-5);
  border-radius: var(--radius-lg);
  max-height: calc(100vh - 440px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--c-gray-300) transparent;
}

/* Markdown 渲染样式约束 */
.content-text :deep(h1),
.content-text :deep(h2),
.content-text :deep(h3),
.content-text :deep(h4),
.content-text :deep(h5) {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--c-text-1);
  margin: var(--sp-3) 0 var(--sp-2);
  padding: 0;
  line-height: 1.5;
  border: none;
}
.content-text :deep(h1) { font-size: 15px; }
.content-text :deep(h2) { font-size: 14px; }
.content-text :deep(h3),
.content-text :deep(h4),
.content-text :deep(h5) { font-size: 13px; }

.content-text :deep(p) {
  margin: var(--sp-1) 0;
  line-height: 1.7;
}

.content-text :deep(ul),
.content-text :deep(ol) {
  margin: var(--sp-1) 0;
  padding-left: var(--sp-5);
}

.content-text :deep(li) {
  margin: 2px 0;
  line-height: 1.6;
}

.content-text :deep(strong) {
  font-weight: 600;
  color: var(--c-text-1);
}

.content-text :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--c-bg-card);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  color: var(--c-primary);
}

.content-text :deep(blockquote) {
  margin: var(--sp-2) 0;
  padding: var(--sp-2) var(--sp-3);
  border-left: 3px solid var(--c-primary-muted);
  background: var(--c-bg-card);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--c-text-3);
}

.content-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--c-border-muted);
  margin: var(--sp-3) 0;
}

.edit-view {
  padding: var(--sp-2) 0;
}
</style>
