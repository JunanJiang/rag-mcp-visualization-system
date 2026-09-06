<template>
  <div class="kb-panel">
    <div class="kb-header">
      <h2>知识库管理</h2>
      <p class="kb-subtitle">管理系统知识卡片、个人文档与组织共享资料，供 AI 生成报告时参考</p>
    </div>

    <div class="kb-overview">
      <div class="kb-source-card">
        <div class="kb-source-head">
          <div>
            <div class="kb-source-title">系统知识库</div>
            <div class="kb-source-desc">内置知识卡片，适合用作报告生成时的术语和背景补充</div>
          </div>
          <el-switch
            v-model="kbPreferences.enableSystemKb"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
            @change="onKbPreferenceChange"
          />
        </div>
        <div class="kb-source-footer">
          <span>共 {{ systemCards.length }} 张知识卡片</span>
          <el-button text @click="toggleSection('system')">{{ expandedSections.includes('system') ? '收起详情' : '展开详情' }}</el-button>
          <el-button v-if="isAdmin" type="primary" @click="openCardEditor(null)">
            <el-icon><Plus /></el-icon> 新建卡片
          </el-button>
        </div>
      </div>
      <div class="kb-source-card">
        <div class="kb-source-head">
          <div>
            <div class="kb-source-title">个人知识库</div>
            <div class="kb-source-desc">你的私有文档与上传资料，仅你自己可见并可参与生成</div>
          </div>
          <el-switch
            v-model="kbPreferences.enablePersonalKb"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
            @change="onKbPreferenceChange"
          />
        </div>
        <div class="kb-source-footer">
          <span>共 {{ personalDocs.length }} 个个人文档</span>
          <el-button text @click="toggleSection('personal')">{{ expandedSections.includes('personal') ? '收起详情' : '展开详情' }}</el-button>
        </div>
      </div>
      <div v-if="hasOrganizations" class="kb-source-card">
        <div class="kb-source-head">
          <div>
            <div class="kb-source-title">组织知识库</div>
            <div class="kb-source-desc">每个组织对应一个共享知识库，成员可直接上传文件，也可从个人知识库导入文档</div>
          </div>
          <el-switch
            v-model="kbPreferences.enableOrgKb"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
            @change="onKbPreferenceChange"
          />
        </div>
        <div class="kb-source-footer">
          <span>当前组织共 {{ orgDocs.length }} 个共享文档</span>
          <el-button text @click="toggleSection('org')">{{ expandedSections.includes('org') ? '收起详情' : '展开详情' }}</el-button>
        </div>
      </div>
    </div>

    <div class="kb-selection-bar">
      <span class="kb-selection-label">报告生成当前将使用：</span>
      <el-tag v-for="label in enabledKbLabels" :key="label" size="small">{{ label }}</el-tag>
      <span v-if="enabledKbLabels.length === 0" class="kb-selection-empty">当前已关闭所有知识库，报告生成将不使用知识库检索</span>
    </div>

    <el-collapse v-model="expandedSections" class="kb-collapse">
      <!-- ─── 系统知识库 ─── -->
      <el-collapse-item name="system">
        <template #title>
          <div class="kb-collapse-titlebar">
            <span class="kb-collapse-title">系统知识库</span>
            <span class="kb-collapse-badge">知识卡片</span>
          </div>
        </template>
        <div class="system-toolbar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索知识卡片..."
            clearable
            size="default"
            class="search-input"
            @input="debouncedLoadCards"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button v-if="isAdmin" type="primary" @click="openCardEditor(null)">
            <el-icon><Plus /></el-icon> 新建卡片
          </el-button>
        </div>

        <!-- 标签筛选 -->
        <div class="filter-bar" v-if="allTags.length > 0">
          <span class="filter-label">标签筛选：</span>
          <el-tag
            v-for="tag in allTags"
            :key="tag"
            :type="selectedTags.includes(tag) ? '' : 'info'"
            :effect="selectedTags.includes(tag) ? 'dark' : 'plain'"
            class="filter-tag"
            @click="toggleTag(tag)"
          >{{ tag }}</el-tag>
          <el-button v-if="selectedTags.length > 0" text size="small" @click="selectedTags = []; loadCards()">
            清除筛选
          </el-button>
        </div>

        <!-- 卡片网格 -->
        <div v-loading="loadingCards" class="cards-grid">
          <div
            v-for="card in systemCards"
            :key="card.id"
            class="card-item"
            @click="viewCard(card)"
          >
            <div class="card-title">{{ card.title }}</div>
            <div class="card-tags">
              <el-tag v-for="t in card.tags" :key="t" size="small" type="info" effect="plain" class="card-tag">{{ t }}</el-tag>
              <span v-if="!card.tags?.length" class="text-muted">未设置标签</span>
            </div>
            <div class="card-tags card-tags-secondary">
              <el-tag v-for="m in card.report_modules" :key="m" size="small" type="warning" effect="plain" class="card-tag card-module-tag">{{ m }}</el-tag>
              <span v-if="!card.report_modules?.length" class="text-muted">未设置报告模块</span>
            </div>
            <div class="card-source">来源：{{ formatSourcesSummary(card.sources) }}</div>
            <div class="card-preview">{{ card.content_preview }}</div>
            <div class="card-footer">
              <span class="card-footnote">{{ extractFileName(card.source_file) || '系统知识卡片' }}</span>
              <span class="card-modules">{{ card.id }}</span>
            </div>
          </div>
        </div>

        <div v-if="systemCards.length === 0 && !loadingCards" class="empty-tip">
          <el-empty description="暂无知识卡片" :image-size="80">
            <el-button v-if="isAdmin" type="primary" @click="openCardEditor(null)">创建第一张卡片</el-button>
          </el-empty>
        </div>

        <div class="cards-count" v-if="systemCards.length > 0">
          共 {{ systemCards.length }} 张知识卡片
        </div>
      </el-collapse-item>

      <!-- ─── 组织知识库 ─── -->
      <el-collapse-item v-if="hasOrganizations" name="org">
        <template #title>
          <div class="kb-collapse-titlebar">
            <span class="kb-collapse-title">组织知识库</span>
            <span class="kb-collapse-badge">共享文档</span>
          </div>
        </template>
        <div class="system-toolbar">
          <el-select v-model="selectedOrgId" class="search-input" placeholder="选择组织" style="max-width: 240px">
            <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
          <el-input
            v-model="orgSearchQuery"
            placeholder="搜索组织文档..."
            clearable
            size="default"
            class="search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button v-if="selectedOrgId" type="primary" @click="openUploadDialog('org')">
            <el-icon><Upload /></el-icon> 上传到组织
          </el-button>
          <el-button v-if="selectedOrgId" @click="showImportDialog = true">从个人知识库导入</el-button>
        </div>

        <div v-loading="loadingOrgDocs" class="cards-grid">
          <div
            v-for="doc in filteredOrgDocs"
            :key="doc.id || doc.filename"
            class="card-item"
            @click="viewOrgDoc(doc)"
          >
            <div class="card-title">{{ doc.filename }}</div>
            <div class="card-tags">
              <el-tag v-for="tag in doc.tags" :key="tag" size="small" type="info" effect="plain" class="card-tag">{{ tag }}</el-tag>
              <span v-if="!doc.tags?.length" class="text-muted">未设置标签</span>
            </div>
            <div class="card-tags card-tags-secondary">
              <el-tag v-for="module in doc.report_modules" :key="module" size="small" type="warning" effect="plain" class="card-tag card-module-tag">{{ module }}</el-tag>
              <span v-if="!doc.report_modules?.length" class="text-muted">未设置报告模块</span>
            </div>
            <div class="card-source">来源：{{ formatSourcesSummary(doc.sources) }}</div>
            <div class="card-preview">{{ doc.content_preview || '暂无预览' }}</div>
            <div class="card-footer">
              <span class="card-footnote">{{ formatDocFootnote(doc) }}</span>
              <span class="card-modules">{{ doc.created_at }}</span>
            </div>
          </div>
        </div>

        <div v-if="filteredOrgDocs.length === 0 && !loadingOrgDocs" class="empty-tip">
          <el-empty description="当前组织暂无文档" :image-size="80">
            <el-button v-if="selectedOrgId" type="primary" @click="openUploadDialog('org')">上传第一个组织文档</el-button>
          </el-empty>
        </div>

        <div class="cards-count" v-if="filteredOrgDocs.length > 0">
          共 {{ filteredOrgDocs.length }} 个组织文档
        </div>
      </el-collapse-item>

      <!-- ─── 个人知识库 ─── -->
      <el-collapse-item name="personal">
        <template #title>
          <div class="kb-collapse-titlebar">
            <span class="kb-collapse-title">个人知识库</span>
            <span class="kb-collapse-badge">个人文档</span>
          </div>
        </template>
        <div class="system-toolbar">
          <el-input
            v-model="personalSearchQuery"
            placeholder="搜索个人文档..."
            clearable
            size="default"
            class="search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" :loading="uploading" @click="openUploadDialog('personal')">
            <el-icon><Upload /></el-icon> 上传文档
          </el-button>
        </div>

        <!-- 文档卡片网格 -->
        <div v-loading="loadingPersonal" class="cards-grid">
          <div
            v-for="doc in filteredPersonalDocs"
            :key="doc.id || doc.filename"
            class="card-item"
            @click="viewPersonalDoc(doc)"
          >
            <div class="card-title">{{ doc.filename }}</div>
            <div class="card-tags">
              <el-tag v-for="tag in doc.tags" :key="tag" size="small" type="info" effect="plain" class="card-tag">{{ tag }}</el-tag>
              <span v-if="!doc.tags?.length" class="text-muted">未设置标签</span>
            </div>
            <div class="card-tags card-tags-secondary">
              <el-tag v-for="module in doc.report_modules" :key="module" size="small" type="warning" effect="plain" class="card-tag card-module-tag">{{ module }}</el-tag>
              <span v-if="!doc.report_modules?.length" class="text-muted">未设置报告模块</span>
            </div>
            <div class="card-source">来源：{{ formatSourcesSummary(doc.sources) }}</div>
            <div class="card-preview">{{ doc.content_preview || '暂无预览' }}</div>
            <div class="card-footer">
              <span class="card-footnote">{{ formatDocFootnote(doc) }}</span>
              <span class="card-modules">{{ doc.created_at }}</span>
            </div>
          </div>
        </div>

        <div v-if="filteredPersonalDocs.length === 0 && !loadingPersonal" class="empty-tip">
          <el-empty description="暂无文档，点击上传文档按钮添加" :image-size="80">
            <el-button type="primary" @click="openUploadDialog('personal')">上传第一个文档</el-button>
          </el-empty>
        </div>

        <div class="cards-count" v-if="filteredPersonalDocs.length > 0">
          共 {{ filteredPersonalDocs.length }} 个个人文档
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- ─── 卡片详情抽屉 ─── -->
    <el-drawer
      v-model="detailVisible"
      :title="detailCard?.title || '卡片详情'"
      direction="rtl"
      size="520px"
    >
      <div v-if="detailCard">
        <div class="detail-meta">
          <div class="detail-meta-row">
            <span class="detail-label">标签</span>
            <div>
              <el-tag v-for="t in detailCard.tags" :key="t" size="small" class="detail-tag">{{ t }}</el-tag>
              <span v-if="!detailCard.tags?.length" class="text-muted">无标签</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">报告模块</span>
            <div>
              <el-tag v-for="m in detailCard.report_modules" :key="m" size="small" type="warning" class="detail-tag">{{ m }}</el-tag>
              <span v-if="!detailCard.report_modules?.length" class="text-muted">未指定</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">来源</span>
            <div class="detail-sources">
              <div v-for="(s, i) in detailCard.sources" :key="i" class="source-item">{{ s }}</div>
              <span v-if="!detailCard.sources?.length" class="text-muted">未填写</span>
            </div>
          </div>
        </div>
        <el-divider />
        <div class="detail-content" v-html="renderedDetailContent"></div>
      </div>
      <template #footer v-if="isAdmin">
        <el-button @click="openCardEditor(detailCard)" :disabled="!detailCard">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
        <el-button type="danger" @click="deleteCard(detailCard?.id)" :disabled="!detailCard">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
      </template>
    </el-drawer>

    <!-- ─── 个人文档详情抽屉 ─── -->
    <el-drawer
      v-model="personalDetailVisible"
      :title="personalDetailDoc?.filename || '文档详情'"
      direction="rtl"
      size="520px"
    >
      <div v-if="personalDetailDoc">
        <div class="detail-meta">
          <div class="detail-meta-row">
            <span class="detail-label">标签</span>
            <div>
              <el-tag v-for="tag in personalDetailDoc.tags" :key="tag" size="small" class="detail-tag">{{ tag }}</el-tag>
              <span v-if="!personalDetailDoc.tags?.length" class="text-muted">无标签</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">报告模块</span>
            <div>
              <el-tag v-for="m in personalDetailDoc.report_modules" :key="m" size="small" type="warning" class="detail-tag">{{ m }}</el-tag>
              <span v-if="!personalDetailDoc.report_modules?.length" class="text-muted">未指定</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">来源</span>
            <div class="detail-sources">
              <div v-for="(s, i) in personalDetailDoc.sources" :key="i" class="source-item">{{ s }}</div>
              <span v-if="!personalDetailDoc.sources?.length" class="text-muted">未填写</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">文档信息</span>
            <span class="text-muted">{{ formatDocFootnote(personalDetailDoc) }}</span>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">上传时间</span>
            <span class="text-muted">{{ personalDetailDoc.created_at }}</span>
          </div>
        </div>
        <el-divider />
        <div class="detail-content" v-html="renderedPersonalContent"></div>
      </div>
      <template #footer>
        <el-button @click="openDocMetaEditor('personal', personalDetailDoc)" :disabled="!personalDetailDoc">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
        <el-button type="danger" @click="deletePersonalDoc(personalDetailDoc)" :disabled="!personalDetailDoc">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
      </template>
    </el-drawer>

    <el-drawer
      v-model="orgDetailVisible"
      :title="orgDetailDoc?.filename || '组织文档详情'"
      direction="rtl"
      size="520px"
    >
      <div v-if="orgDetailDoc">
        <div class="detail-meta">
          <div class="detail-meta-row">
            <span class="detail-label">标签</span>
            <div>
              <el-tag v-for="tag in orgDetailDoc.tags" :key="tag" size="small" class="detail-tag">{{ tag }}</el-tag>
              <span v-if="!orgDetailDoc.tags?.length" class="text-muted">无标签</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">报告模块</span>
            <div>
              <el-tag v-for="m in orgDetailDoc.report_modules" :key="m" size="small" type="warning" class="detail-tag">{{ m }}</el-tag>
              <span v-if="!orgDetailDoc.report_modules?.length" class="text-muted">未指定</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">组织</span>
            <span class="text-muted">{{ currentOrgName }}</span>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">来源</span>
            <div class="detail-sources">
              <div v-for="(s, i) in orgDetailDoc.sources" :key="i" class="source-item">{{ s }}</div>
              <span v-if="!orgDetailDoc.sources?.length" class="text-muted">未填写</span>
            </div>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">文档信息</span>
            <span class="text-muted">{{ formatDocFootnote(orgDetailDoc) }}</span>
          </div>
          <div class="detail-meta-row">
            <span class="detail-label">上传时间</span>
            <span class="text-muted">{{ orgDetailDoc.created_at }}</span>
          </div>
        </div>
        <el-divider />
        <div class="detail-content" v-html="renderedOrgContent"></div>
      </div>
      <template #footer>
        <el-button @click="openDocMetaEditor('org', orgDetailDoc)" :disabled="!orgDetailDoc || !selectedOrgId">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
        <el-button type="danger" @click="deleteOrgDoc(orgDetailDoc)" :disabled="!orgDetailDoc || !selectedOrgId">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="showImportDialog" title="导入个人知识库到组织" width="720px">
      <div class="import-dialog-tip">选择你自己的个人知识库文档，将其复制导入当前组织共享知识库。</div>
      <el-table :data="filteredImportableDocs" stripe size="small" max-height="420" empty-text="暂无可导入的个人文档">
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column prop="file_type" label="类型" width="90" />
        <el-table-column prop="chunk_count" label="分块" width="80" />
        <el-table-column prop="created_at" label="上传时间" min-width="160" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" text :loading="importingDocId === row.id" @click="importPersonalDocToOrg(row)">导入</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" :title="uploadDialogTitle" width="720px" :close-on-click-modal="false">
      <el-form label-position="top" class="upload-dialog-form">
        <el-form-item label="标签" required>
          <el-select v-model="uploadForm.tags" multiple filterable allow-create default-first-option placeholder="选择或输入标签" style="width:100%">
            <el-option v-for="tag in knownTagOptions" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="报告模块" required>
              <el-select v-model="uploadForm.report_modules" multiple placeholder="选择适用模块" style="width:100%">
                <el-option v-for="m in MODULE_OPTIONS" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源" required>
              <el-select v-model="uploadForm.sources" multiple filterable allow-create default-first-option placeholder="选择或输入来源" style="width:100%">
                <el-option v-for="source in knownSourceOptions" :key="source" :label="source" :value="source" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="上传文件" required>
          <el-upload
            :auto-upload="false"
            :limit="1"
            :file-list="uploadFileList"
            :on-change="handleUploadFileChange"
            :on-remove="handleUploadFileRemove"
            :on-exceed="handleUploadExceed"
            :accept="ACCEPT"
            drag
            class="upload-file-picker"
          >
            <el-icon><Upload /></el-icon>
            <div class="upload-hint">拖拽文件到此处，或点击选择文件</div>
            <div class="text-muted">支持格式：docx、md、txt、pdf、doc</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">确认上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="docMetaDialogVisible" :title="docMetaDialogTitle" width="820px" :close-on-click-modal="false" top="6vh">
      <el-form label-position="top" class="upload-dialog-form" v-loading="docMetaLoadingContent">
        <el-form-item label="标签" required>
          <el-select v-model="docMetaForm.tags" multiple filterable allow-create default-first-option placeholder="选择或输入标签" style="width:100%">
            <el-option v-for="tag in knownTagOptions" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="报告模块" required>
              <el-select v-model="docMetaForm.report_modules" multiple placeholder="选择适用模块" style="width:100%">
                <el-option v-for="m in MODULE_OPTIONS" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源" required>
              <el-select v-model="docMetaForm.sources" multiple filterable allow-create default-first-option placeholder="选择或输入来源" style="width:100%">
                <el-option v-for="source in knownSourceOptions" :key="source" :label="source" :value="source" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 正文内容：仅 md / markdown / txt 支持在线编辑 -->
        <el-form-item v-if="docMetaCanEditContent">
          <template #label>
            <span>正文内容（{{ docMetaForm.file_type }}）</span>
            <el-tag v-if="docMetaContentDirty" size="small" type="warning" effect="plain" style="margin-left:8px">已修改 · 保存时将重建向量索引</el-tag>
          </template>
          <el-input
            v-model="docMetaForm.content"
            type="textarea"
            :autosize="{ minRows: 14, maxRows: 28 }"
            placeholder="正在加载正文..."
          />
        </el-form-item>
        <el-alert
          v-else
          :title="`文件类型 .${docMetaForm.file_type || '?'} 不支持在线编辑正文，此处仅可修改属性（标签 / 报告模块 / 来源）`"
          type="info"
          :closable="false"
          show-icon
          style="margin-top:8px"
        />
      </el-form>
      <template #footer>
        <el-button @click="docMetaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="docMetaSaving" @click="submitDocMetaUpdate">
          {{ docMetaContentDirty ? '保存属性与正文' : '保存属性' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editorVisible"
      :title="editorIsNew ? '新建知识卡片' : '编辑知识卡片'"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form :model="editorForm" label-width="90px" label-position="top">
        <el-form-item label="卡片标题" required>
          <el-input v-model="editorForm.title" placeholder="例：Plot3D Q变量物理含义" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="标签">
              <el-select v-model="editorForm.tags" multiple filterable allow-create default-first-option placeholder="选择或输入标签" style="width:100%">
                <el-option v-for="t in knownTagOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="报告模块">
              <el-select v-model="editorForm.report_modules" multiple placeholder="选择适用模块" style="width:100%">
                <el-option v-for="m in MODULE_OPTIONS" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="来源">
          <el-select v-model="editorForm.sources" multiple filterable allow-create default-first-option placeholder="选择或输入来源" style="width:100%">
            <el-option v-for="source in knownSourceOptions" :key="source" :label="source" :value="source" />
          </el-select>
        </el-form-item>
        <el-form-item label="卡片内容（Markdown）" required>
          <el-input
            v-model="editorForm.content"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 24 }"
            placeholder="使用 Markdown 格式编写知识内容..."
          />
        </el-form-item>
        <el-collapse class="yaml-preview-collapse">
          <el-collapse-item title="YAML Front Matter 预览" name="yaml">
            <pre class="yaml-preview">{{ yamlPreview }}</pre>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="editorSaving" @click="saveCard">
          {{ editorIsNew ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { marked } from 'marked'
import api from '../api'

const route = useRoute()
const ACCEPT = '.pdf,.docx,.doc,.txt,.md'
const apiBase = '/api'
const KB_PREFERENCES_KEY = 'kb_generation_preferences'
const MODULE_OPTIONS = [
  'analysis_purpose', 'grid_description', 'variable_analysis',
  'assessment_criteria', 'conclusions', 'geometry'
]
const currentUser = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || '{}') } catch { return {} }
})
const isAdmin = computed(() => currentUser.value.role === 'admin')

function loadKbPreferences() {
  try {
    const raw = localStorage.getItem(KB_PREFERENCES_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return {
      enableSystemKb: parsed.enableSystemKb !== false,
      enablePersonalKb: parsed.enablePersonalKb !== false,
      enableOrgKb: parsed.enableOrgKb !== false
    }
  } catch {
    return {
      enableSystemKb: true,
      enablePersonalKb: true,
      enableOrgKb: true
    }
  }
}

const expandedSections = ref(['system', 'personal'])
const kbPreferences = ref(loadKbPreferences())
const uploading = ref(false)
const organizations = ref([])
const selectedOrgId = ref(null)
const hasOrganizations = computed(() => organizations.value.length > 0)
const currentOrg = computed(() => organizations.value.find(org => org.id === selectedOrgId.value) || null)
const currentOrgName = computed(() => currentOrg.value?.name || '当前组织')

const enabledKbLabels = computed(() => {
  const labels = []
  if (kbPreferences.value.enableSystemKb) labels.push('系统知识库')
  if (kbPreferences.value.enablePersonalKb) labels.push('个人知识库')
  if (kbPreferences.value.enableOrgKb && hasOrganizations.value) labels.push('组织知识库')
  return labels
})

function persistKbPreferences() {
  localStorage.setItem(KB_PREFERENCES_KEY, JSON.stringify(kbPreferences.value))
}

function buildKbPolicyPayload() {
  return {
    enable_system_kb: kbPreferences.value.enableSystemKb,
    enable_personal_kb: kbPreferences.value.enablePersonalKb,
    enable_org_kb: kbPreferences.value.enableOrgKb
  }
}

function toggleSection(name) {
  if (expandedSections.value.includes(name)) {
    expandedSections.value = expandedSections.value.filter(item => item !== name)
  } else {
    expandedSections.value = [...expandedSections.value, name]
  }
}

function onKbPreferenceChange() {
  persistKbPreferences()
  ElMessage.success('知识库开关已更新，下次报告生成时将按当前设置使用')
}

function normalizeMetaList(value) {
  if (value === null || value === undefined) return []
  if (Array.isArray(value)) return value.map(item => String(item).trim()).filter(Boolean)
  return String(value)
    .split(/[,，\n]/)
    .map(item => item.trim())
    .filter(Boolean)
}

function parseMetaValue(rawValue) {
  if (rawValue === null || rawValue === undefined) return []
  const text = String(rawValue).trim()
  if (!text) return []
  if (text.startsWith('[') && text.endsWith(']')) {
    try {
      const parsed = JSON.parse(text.replace(/'/g, '"'))
      return normalizeMetaList(parsed)
    } catch {
      return text.slice(1, -1)
        .split(/[,，]/)
        .map(item => item.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean)
    }
  }
  return normalizeMetaList(text)
}

function extractMarkdownTitle(text, fallbackName = '') {
  const match = String(text || '').match(/^#\s+(.+)$/m)
  if (match?.[1]) return match[1].trim()
  return extractFileName(fallbackName).replace(/\.[^.]+$/, '')
}

function extractMetaFromText(text) {
  const meta = { tags: [], report_modules: [], sources: [] }
  const lines = String(text || '').split(/\r?\n/).slice(0, 40)
  for (const line of lines) {
    const match = line.match(/^\s*(tags|report_modules|sources)\s*:\s*(.+?)\s*$/i)
    if (!match) continue
    const key = match[1].toLowerCase()
    const values = parseMetaValue(match[2])
    if (key === 'tags') meta.tags = values
    else if (key === 'report_modules') meta.report_modules = values
    else if (key === 'sources') meta.sources = values
  }
  return meta
}

function inferReportModules(text) {
  const content = String(text || '').toLowerCase()
  const modules = []
  const rules = [
    ['analysis_purpose', ['需求', '目标', '场景', '定位', '用途', '背景', 'scope', 'purpose']],
    ['grid_description', ['网格', 'grid']],
    ['variable_analysis', ['变量', '速度', '压力', '流线', '云图', '回流', '再附着', '分析', 'variable']],
    ['assessment_criteria', ['评估', '质量', '规范', '标准', '准则', '复核', '审核', 'criteria', 'quality']],
    ['conclusions', ['结论', '建议', '总结', '影响', '要求', 'conclusion', 'recommendation']],
    ['geometry', ['几何', '结构', '台阶', '通道', 'geometry']]
  ]
  for (const [module, keywords] of rules) {
    if (keywords.some(keyword => content.includes(keyword))) modules.push(module)
  }
  return modules.length ? modules : ['analysis_purpose']
}

function inferTags(doc, title, text) {
  const tags = []
  const push = (value) => {
    const next = String(value || '').trim().replace(/^[\s\-—_、，,。；;:：]+|[\s\-—_、，,。；;:：]+$/g, '')
    if (next.length >= 2 && !tags.includes(next)) tags.push(next)
  }
  const cleanedTitle = String(title || '').replace(/\s+/g, ' ').trim()
  for (const part of cleanedTitle.split(/[\-—]/)) {
    if (part.trim().length >= 2) push(part)
  }
  const keywordPairs = [
    ['组织', '组织协作'],
    ['团队', '团队规范'],
    ['规范', '文档规范'],
    ['需求', '需求清单'],
    ['场景', '场景分析'],
    ['质量', '质量评估'],
    ['评估', '质量评估'],
    ['报告', '报告编制'],
    ['变量', '变量分析'],
    ['回流', '回流分析'],
    ['压力', '压力分析'],
    ['可视化', '可视化']
  ]
  const sourceText = `${cleanedTitle}\n${String(text || '')}`
  for (const [keyword, tag] of keywordPairs) {
    if (sourceText.includes(keyword)) push(tag)
  }
  if (doc?.scope === 'org') push('组织知识库')
  if (doc?.scope === 'personal') push('个人知识库')
  return tags.slice(0, 4)
}

function inferSources(doc) {
  const filename = doc?.filename || '未命名文档'
  if (doc?.scope === 'org') {
    return ['组织共享文档', `原始文件：${filename}`]
  }
  return ['个人知识文档', `原始文件：${filename}`]
}

function hydrateDocMeta(doc, rawText = '') {
  const base = { ...(doc || {}) }
  const content = String(rawText || '')
  const extracted = extractMetaFromText(content)
  const title = extractMarkdownTitle(content, base.filename || '')
  const mergedText = `${title}\n${content}`
  base.tags = normalizeMetaList(base.tags).length ? normalizeMetaList(base.tags) : (extracted.tags.length ? extracted.tags : inferTags(base, title, mergedText))
  base.report_modules = normalizeMetaList(base.report_modules).length ? normalizeMetaList(base.report_modules) : (extracted.report_modules.length ? extracted.report_modules : inferReportModules(mergedText))
  base.sources = normalizeMetaList(base.sources).length ? normalizeMetaList(base.sources) : (extracted.sources.length ? extracted.sources : inferSources(base))
  return base
}

function stripLeadingDocMeta(text) {
  let content = String(text || '').replace(/^\uFEFF/, '')
  content = content.replace(/^---\s*\r?\n[\s\S]*?\r?\n---\s*(\r?\n)?/, '')
  const lines = content.split(/\r?\n/)
  let start = 0
  while (start < lines.length && !lines[start].trim()) start += 1
  let end = start
  let sawMeta = false
  while (end < lines.length) {
    const line = lines[end].trim()
    if (!line) break
    if (/^(id|title|tags|report_modules|confidence|sources)\s*:/i.test(line)) {
      sawMeta = true
      end += 1
      continue
    }
    break
  }
  if (sawMeta) {
    while (end < lines.length && !lines[end].trim()) end += 1
    content = lines.slice(end).join('\n')
  }
  return content.trim()
}

function formatSourcesSummary(sources) {
  const items = normalizeMetaList(sources)
  if (!items.length) return '未填写'
  const text = items.join('；')
  return text.length > 44 ? `${text.slice(0, 44)}…` : text
}

function extractFileName(path) {
  if (!path) return ''
  return String(path).split(/[\\/]/).pop() || String(path)
}

function formatDocFootnote(doc) {
  const parts = []
  if (doc?.file_type) parts.push(String(doc.file_type).toUpperCase())
  if (doc?.chunk_count) parts.push(`${doc.chunk_count} 分块`)
  return parts.join(' · ') || '文档'
}

function keywordMatchesDoc(doc, query) {
  const text = [
    doc?.filename,
    doc?.file_type,
    ...(doc?.tags || []),
    ...(doc?.report_modules || []),
    ...(doc?.sources || [])
  ].join(' ').toLowerCase()
  return text.includes(query)
}

// ───── 系统知识库 ─────
const systemCards = ref([])
const loadingCards = ref(false)
const searchQuery = ref('')
const selectedTags = ref([])
const allTags = ref([])
const allModules = ref([])

let debounceTimer = null
function debouncedLoadCards() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadCards(), 300)
}

async function loadCards() {
  loadingCards.value = true
  try {
    const params = {}
    if (searchQuery.value) params.q = searchQuery.value
    if (selectedTags.value.length) {
      // axios 会自动把数组序列化为 tag=a&tag=b
      params.tag = selectedTags.value
    }
    const res = await api.get('/kb/cards', { params })
    if (res.data.success) {
      systemCards.value = res.data.cards
      allTags.value = res.data.all_tags || []
      allModules.value = res.data.all_modules || []
    }
  } catch { /* ignore */ } finally { loadingCards.value = false }
}

const knownTagOptions = computed(() => {
  const values = new Set(allTags.value)
  for (const doc of personalDocs.value) {
    for (const tag of normalizeMetaList(doc.tags)) values.add(tag)
  }
  for (const doc of orgDocs.value) {
    for (const tag of normalizeMetaList(doc.tags)) values.add(tag)
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

const knownSourceOptions = computed(() => {
  const values = new Set()
  for (const card of systemCards.value) {
    for (const source of normalizeMetaList(card.sources)) values.add(source)
  }
  for (const doc of personalDocs.value) {
    for (const source of normalizeMetaList(doc.sources)) values.add(source)
  }
  for (const doc of orgDocs.value) {
    for (const source of normalizeMetaList(doc.sources)) values.add(source)
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

function toggleTag(tag) {
  const idx = selectedTags.value.indexOf(tag)
  if (idx >= 0) selectedTags.value.splice(idx, 1)
  else selectedTags.value.push(tag)
  loadCards()
}

// ───── 卡片详情 ─────
const detailVisible = ref(false)
const detailCard = ref(null)
const detailFullContent = ref('')

const renderedDetailContent = computed(() => {
  if (!detailFullContent.value) return ''
  const cleaned = stripLeadingDocMeta(detailFullContent.value)
  try { return marked(cleaned) } catch { return cleaned }
})

async function viewCard(card) {
  detailCard.value = card
  detailVisible.value = true
  try {
    const res = await api.get(`/kb/cards/${card.id}`)
    if (res.data.success) {
      detailCard.value = { ...card, ...res.data.card }
      detailFullContent.value = res.data.card.content || ''
    }
  } catch { detailFullContent.value = card.content_preview || '' }
}

async function viewOrgDoc(doc) {
  if (!selectedOrgId.value) return
  orgDetailDoc.value = hydrateDocMeta(doc, doc?.content_preview || '')
  orgDetailVisible.value = true
  orgFullContent.value = ''
  try {
    const res = await api.get(`/kb/orgs/${selectedOrgId.value}/documents/${doc.id}`)
    if (res.data.success) {
      orgFullContent.value = res.data.content || ''
      orgDetailDoc.value = hydrateDocMeta({ ...doc, ...res.data.document }, orgFullContent.value)
    }
  } catch { orgFullContent.value = doc.content_preview || '' }
}

// ───── 个人文档详情 ─────
const personalDetailVisible = ref(false)
const personalDetailDoc = ref(null)
const personalFullContent = ref('')

const renderedPersonalContent = computed(() => {
  if (!personalFullContent.value) return ''
  const cleaned = stripLeadingDocMeta(personalFullContent.value)
  try { return marked(cleaned) } catch { return cleaned }
})

// ───── 组织文档详情 ─────
const orgDetailVisible = ref(false)
const orgDetailDoc = ref(null)
const orgFullContent = ref('')

const renderedOrgContent = computed(() => {
  if (!orgFullContent.value) return ''
  const cleaned = stripLeadingDocMeta(orgFullContent.value)
  try { return marked(cleaned) } catch { return cleaned }
})

const docMetaDialogVisible = ref(false)
const docMetaTargetScope = ref('personal')
const docMetaSaving = ref(false)
const docMetaLoadingContent = ref(false)
// 允许在线编辑正文的文件类型，需与后端 KBManager._EDITABLE_CONTENT_SUFFIXES 保持一致
const EDITABLE_CONTENT_TYPES = ['md', 'markdown', 'txt']
const docMetaForm = reactive({
  id: null,
  filename: '',
  file_type: '',
  tags: [],
  report_modules: [],
  sources: [],
  content: '',
  originalContent: ''
})

const docMetaDialogTitle = computed(() => {
  const scopeLabel = docMetaTargetScope.value === 'org' ? '组织文档' : '个人文档'
  return docMetaForm.filename ? `编辑${scopeLabel} · ${docMetaForm.filename}` : `编辑${scopeLabel}`
})

const docMetaCanEditContent = computed(() => {
  return EDITABLE_CONTENT_TYPES.includes(String(docMetaForm.file_type || '').toLowerCase())
})

const docMetaContentDirty = computed(() => {
  return docMetaCanEditContent.value && docMetaForm.content !== docMetaForm.originalContent
})

async function viewPersonalDoc(doc) {
  personalDetailDoc.value = hydrateDocMeta(doc, doc?.content_preview || '')
  personalDetailVisible.value = true
  personalFullContent.value = ''
  try {
    const res = await api.get(`/kb/documents/${doc.id}`)
    if (res.data.success) {
      personalFullContent.value = res.data.content || ''
      personalDetailDoc.value = hydrateDocMeta({ ...doc, ...res.data.document }, personalFullContent.value)
    }
  } catch { personalFullContent.value = doc.content_preview || '' }
}

async function openDocMetaEditor(scope, doc) {
  if (!doc) return
  docMetaTargetScope.value = scope
  docMetaForm.id = doc.id
  docMetaForm.filename = doc.filename || ''
  docMetaForm.file_type = String(doc.file_type || '').toLowerCase()
  docMetaForm.tags = normalizeMetaList(doc.tags)
  docMetaForm.report_modules = normalizeMetaList(doc.report_modules)
  docMetaForm.sources = normalizeMetaList(doc.sources)
  docMetaForm.content = ''
  docMetaForm.originalContent = ''
  docMetaDialogVisible.value = true

  // 对文本类文件，额外拉最新正文内容用于在线编辑
  if (EDITABLE_CONTENT_TYPES.includes(docMetaForm.file_type)) {
    docMetaLoadingContent.value = true
    try {
      const endpoint = scope === 'org'
        ? `/kb/orgs/${selectedOrgId.value}/documents/${doc.id}`
        : `/kb/documents/${doc.id}`
      const res = await api.get(endpoint)
      if (res.data.success) {
        const text = res.data.content || ''
        docMetaForm.content = text
        docMetaForm.originalContent = text
      }
    } catch (e) {
      ElMessage.warning('加载正文失败，仅可编辑属性：' + (e.response?.data?.error || e.message))
    } finally {
      docMetaLoadingContent.value = false
    }
  }
}

async function submitDocMetaUpdate() {
  const tags = normalizeMetaList(docMetaForm.tags)
  const reportModules = normalizeMetaList(docMetaForm.report_modules)
  const sources = normalizeMetaList(docMetaForm.sources)
  if (!docMetaForm.id) return ElMessage.warning('未找到待编辑文档')
  if (!tags.length) return ElMessage.warning('请至少填写一个标签')
  if (!reportModules.length) return ElMessage.warning('请至少选择一个报告模块')
  if (!sources.length) return ElMessage.warning('请至少填写一个来源')

  const payload = {
    tags,
    report_modules: reportModules,
    sources
  }
  // 只有可编辑类型且正文被改动过，才把 content 一起提交
  if (docMetaContentDirty.value) {
    if (!docMetaForm.content.trim()) {
      return ElMessage.warning('正文内容不能为空')
    }
    payload.content = docMetaForm.content
  }

  const endpoint = docMetaTargetScope.value === 'org'
    ? `/kb/orgs/${selectedOrgId.value}/documents/${docMetaForm.id}`
    : `/kb/documents/${docMetaForm.id}`

  docMetaSaving.value = true
  try {
    const res = await api.put(endpoint, payload)
    const updatedDoc = res.data.document || payload
    if (docMetaTargetScope.value === 'org') {
      orgDetailDoc.value = orgDetailDoc.value && orgDetailDoc.value.id === docMetaForm.id
        ? { ...orgDetailDoc.value, ...updatedDoc }
        : orgDetailDoc.value
      if (orgDetailDoc.value?.id === docMetaForm.id && payload.content) {
        orgFullContent.value = payload.content
      }
      await loadOrgDocs()
    } else {
      personalDetailDoc.value = personalDetailDoc.value && personalDetailDoc.value.id === docMetaForm.id
        ? { ...personalDetailDoc.value, ...updatedDoc }
        : personalDetailDoc.value
      if (personalDetailDoc.value?.id === docMetaForm.id && payload.content) {
        personalFullContent.value = payload.content
      }
      await loadPersonalDocs()
    }
    ElMessage.success(res.data.message || (payload.content ? '文档已更新（属性 + 正文）' : '文档属性已更新'))
    docMetaDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '更新失败')
  } finally {
    docMetaSaving.value = false
  }
}

// ───── 卡片编辑器 ─────
const editorVisible = ref(false)
const editorIsNew = ref(true)
const editorSaving = ref(false)
const editorForm = reactive({
  id: '',
  title: '',
  tags: [],
  report_modules: [],
  sources: [],
  content: ''
})

const yamlPreview = computed(() => {
  const fm = {
    id: editorForm.id || '(auto)',
    title: editorForm.title || '(未填写)',
    tags: editorForm.tags,
    report_modules: editorForm.report_modules,
    sources: editorForm.sources
  }
  return `---\n${Object.entries(fm).map(([k, v]) =>
    `${k}: ${Array.isArray(v) ? `[${v.join(', ')}]` : v}`
  ).join('\n')}\n---`
})

function openCardEditor(card) {
  if (card) {
    editorIsNew.value = false
    editorForm.id = card.id
    editorForm.title = card.title
    editorForm.tags = [...(card.tags || [])]
    editorForm.report_modules = [...(card.report_modules || [])]
    editorForm.sources = [...(card.sources || [])]
    editorForm.content = detailFullContent.value || card.content_preview || ''
  } else {
    editorIsNew.value = true
    editorForm.id = ''
    editorForm.title = ''
    editorForm.tags = []
    editorForm.report_modules = []
    editorForm.sources = []
    editorForm.content = ''
  }
  editorVisible.value = true
}

async function saveCard() {
  if (!editorForm.title.trim()) return ElMessage.warning('请输入卡片标题')
  if (!editorForm.tags.length) return ElMessage.warning('请至少填写一个标签')
  if (!editorForm.report_modules.length) return ElMessage.warning('请至少选择一个报告模块')
  if (!editorForm.sources.length) return ElMessage.warning('请至少填写一个来源')
  if (!editorForm.content.trim()) return ElMessage.warning('请输入卡片内容')
  editorSaving.value = true
  try {
    const payload = {
      title: editorForm.title,
      content: editorForm.content,
      tags: editorForm.tags,
      report_modules: editorForm.report_modules,
      sources: editorForm.sources
    }
    if (editorIsNew.value) {
      if (editorForm.id) payload.id = editorForm.id
      await api.post('/kb/cards', payload)
      ElMessage.success('卡片创建成功')
    } else {
      await api.put(`/kb/cards/${editorForm.id}`, payload)
      ElMessage.success('卡片更新成功')
    }
    editorVisible.value = false
    detailVisible.value = false
    await loadCards()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally { editorSaving.value = false }
}

async function deleteCard(cardId) {
  try {
    await ElMessageBox.confirm('确定删除该知识卡片？删除后不可恢复。', '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.delete(`/kb/cards/${cardId}`)
    ElMessage.success('卡片已删除')
    detailVisible.value = false
    await loadCards()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.error || '删除失败')
  }
}

// ───── 个人知识库 ─────
const personalDocs = ref([])
const loadingPersonal = ref(false)
const personalLog = ref([])
const loadingPersonalLog = ref(false)
const personalSearchQuery = ref('')
const showImportDialog = ref(false)
const importingDocId = ref(null)
const uploadDialogVisible = ref(false)
const uploadTargetScope = ref('personal')
const uploadFileList = ref([])
const uploadForm = reactive({
  tags: [],
  report_modules: [],
  sources: [],
  file: null
})

const uploadDialogTitle = computed(() => (
  uploadTargetScope.value === 'org'
    ? `上传到组织知识库 · ${currentOrgName.value}`
    : '上传到个人知识库'
))

const filteredPersonalDocs = computed(() => {
  if (!personalSearchQuery.value) return personalDocs.value
  const q = personalSearchQuery.value.toLowerCase()
  return personalDocs.value.filter(doc => keywordMatchesDoc(doc, q))
})

const filteredImportableDocs = computed(() => {
  if (!selectedOrgId.value) return []
  const orgDocNames = new Set(orgDocs.value.map(doc => `${doc.filename}::${doc.file_type}`))
  return personalDocs.value.filter(doc => !orgDocNames.has(`${doc.filename}::${doc.file_type}`))
})

async function loadPersonalDocs() {
  loadingPersonal.value = true
  try {
    const res = await api.get('/kb/documents')
    if (res.data.success) personalDocs.value = (res.data.documents || []).map(doc => hydrateDocMeta(doc, doc?.content_preview || ''))
  } catch { /* ignore */ } finally { loadingPersonal.value = false }
}

async function loadPersonalLog() {
  loadingPersonalLog.value = true
  try {
    const res = await api.get('/kb/changelog')
    if (res.data.success) personalLog.value = res.data.logs
  } catch { /* ignore */ } finally { loadingPersonalLog.value = false }
}

function resetUploadForm() {
  uploadForm.tags = []
  uploadForm.report_modules = []
  uploadForm.sources = []
  uploadForm.file = null
  uploadFileList.value = []
}

function openUploadDialog(scope) {
  if (scope === 'org' && !selectedOrgId.value) {
    ElMessage.warning('请先选择组织')
    return
  }
  uploadTargetScope.value = scope
  resetUploadForm()
  uploadDialogVisible.value = true
}

function handleUploadFileChange(file, fileList) {
  uploadForm.file = file.raw || null
  uploadFileList.value = fileList.slice(-1)
}

function handleUploadFileRemove() {
  uploadForm.file = null
  uploadFileList.value = []
}

function handleUploadExceed() {
  ElMessage.warning('一次只能选择一个文件')
}

async function submitUpload() {
  const tags = normalizeMetaList(uploadForm.tags)
  const reportModules = normalizeMetaList(uploadForm.report_modules)
  const sources = normalizeMetaList(uploadForm.sources)
  if (!uploadForm.file) return ElMessage.warning('请选择要上传的文件')
  if (!tags.length) return ElMessage.warning('请至少填写一个标签')
  if (!reportModules.length) return ElMessage.warning('请至少选择一个报告模块')
  if (!sources.length) return ElMessage.warning('请至少填写一个来源')

  const formData = new FormData()
  formData.append('file', uploadForm.file)
  formData.append('tags', JSON.stringify(tags))
  formData.append('report_modules', JSON.stringify(reportModules))
  formData.append('sources', JSON.stringify(sources))

  const endpoint = uploadTargetScope.value === 'org'
    ? `/kb/orgs/${selectedOrgId.value}/upload`
    : '/kb/upload'

  uploading.value = true
  try {
    const res = await api.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    if (!res.data.success) {
      throw new Error(res.data.error || '上传失败')
    }
    ElMessage.success(uploadTargetScope.value === 'org' ? '组织文档上传成功' : '个人文档上传成功')
    uploadDialogVisible.value = false
    resetUploadForm()
    if (uploadTargetScope.value === 'org') {
      await loadOrgDocs()
    } else {
      await loadPersonalDocs()
      await loadPersonalLog()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function deletePersonalDoc(doc) {
  try {
    await ElMessageBox.confirm(`确定删除「${doc.filename}」？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.delete(`/kb/documents/${doc.id}`)
    ElMessage.success('已删除')
    personalDetailVisible.value = false
    await loadPersonalDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.error || '删除失败')
  }
}

// ───── 组织知识库 ─────
const orgDocs = ref([])
const loadingOrgDocs = ref(false)
const orgSearchQuery = ref('')

const filteredOrgDocs = computed(() => {
  if (!orgSearchQuery.value) return orgDocs.value
  const q = orgSearchQuery.value.toLowerCase()
  return orgDocs.value.filter(doc => keywordMatchesDoc(doc, q))
})

async function loadOrganizations() {
  try {
    const res = await api.get('/orgs')
    if (res.data.success) {
      organizations.value = res.data.organizations || []
      const requestedOrgId = Number(route.query.org || 0)
      const matchedOrg = organizations.value.find(org => org.id === requestedOrgId)
      if (matchedOrg) {
        selectedOrgId.value = matchedOrg.id
      } else if (organizations.value.length > 0 && !selectedOrgId.value) {
        selectedOrgId.value = organizations.value[0].id
      }
      if (organizations.value.length > 0 && !expandedSections.value.includes('org')) {
        expandedSections.value = [...expandedSections.value, 'org']
      }
    }
  } catch {
    organizations.value = []
  }
}

async function loadOrgDocs() {
  if (!selectedOrgId.value) {
    orgDocs.value = []
    return
  }
  loadingOrgDocs.value = true
  try {
    const res = await api.get(`/kb/orgs/${selectedOrgId.value}/documents`)
    if (res.data.success) orgDocs.value = (res.data.documents || []).map(doc => hydrateDocMeta(doc, doc?.content_preview || ''))
  } catch {
    orgDocs.value = []
  } finally {
    loadingOrgDocs.value = false
  }
}

async function importPersonalDocToOrg(doc) {
  if (!selectedOrgId.value) return ElMessage.warning('请先选择组织')
  importingDocId.value = doc.id
  try {
    const res = await api.post(`/kb/orgs/${selectedOrgId.value}/import-personal`, { doc_id: doc.id })
    if (res.data.success) {
      ElMessage.success(res.data.message || '导入成功')
      await loadOrgDocs()
    } else {
      ElMessage.error(res.data.error || '导入失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '导入失败')
  } finally {
    importingDocId.value = null
  }
}

async function deleteOrgDoc(doc) {
  if (!selectedOrgId.value) return
  try {
    await ElMessageBox.confirm(`确定删除「${doc.filename}」？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.delete(`/kb/orgs/${selectedOrgId.value}/documents/${doc.id}`)
    ElMessage.success('已删除')
    orgDetailVisible.value = false
    await loadOrgDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.error || '删除失败')
  }
}

watch(selectedOrgId, () => {
  loadOrgDocs()
})

watch(() => route.query.org, (nextOrg) => {
  const targetId = Number(nextOrg || 0)
  if (targetId && organizations.value.some(org => org.id === targetId)) {
    selectedOrgId.value = targetId
    if (!expandedSections.value.includes('org')) {
      expandedSections.value = [...expandedSections.value, 'org']
    }
  }
})

// ───── 初始化 ─────
onMounted(async () => {
  persistKbPreferences()
  await loadOrganizations()
  await loadCards()
  await loadPersonalDocs()
  await loadPersonalLog()
  await loadOrgDocs()
})
</script>

<style scoped>
.kb-panel {
  padding: var(--sp-6) var(--sp-8);
  max-width: 1060px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
}

.kb-header {
  margin-bottom: 24px;
}

.kb-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text-primary);
  margin: 0 0 4px;
}

.kb-subtitle {
  font-size: 13px;
  color: var(--c-text-muted);
  margin: 0;
}

.kb-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.kb-source-card {
  background: var(--c-bg-card, #fff);
  border: 1px solid var(--c-border, #e4e7ed);
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

.kb-source-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.kb-source-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text-primary);
  margin-bottom: 6px;
}

.kb-source-desc {
  font-size: 12px;
  line-height: 1.7;
  color: var(--c-text-muted);
}

.kb-source-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border, #e4e7ed);
  font-size: 12px;
  color: var(--c-text-muted);
}

.kb-selection-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
  padding: 12px 14px;
  background: var(--c-bg-sunken, #f5f7fa);
  border: 1px solid var(--c-border, #e4e7ed);
  border-radius: 10px;
}

.kb-selection-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary);
}

.kb-selection-empty {
  font-size: 12px;
  color: var(--c-text-muted);
}

.kb-collapse {
  border-top: none;
  border-bottom: none;
}

.kb-collapse :deep(.el-collapse-item__header) {
  padding: 0 20px;
  height: 52px;
  font-size: 14px;
  background: var(--c-bg-card, #fff);
  border-radius: 10px 10px 0 0;
}

.kb-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.kb-collapse :deep(.el-collapse-item__content) {
  padding: 20px 24px 24px;
  background: var(--c-bg-card, #fff);
  border-radius: 0 0 10px 10px;
}

.kb-collapse :deep(.el-collapse-item) {
  margin-bottom: 16px;
  border: 1px solid var(--c-border, #e4e7ed);
  border-radius: 10px;
  overflow: hidden;
}

.kb-collapse-titlebar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-collapse-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary);
}

.kb-collapse-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--c-bg-sunken, #f5f7fa);
  border: 1px solid var(--c-border, #e4e7ed);
  font-size: 11px;
  color: var(--c-text-muted);
}

/* ── 系统知识库工具栏 ── */
.system-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  flex: 1;
  max-width: 400px;
}

.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--c-bg-sunken, #f5f7fa);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e4e7ed);
}

.filter-label {
  font-size: 12px;
  color: var(--c-text-muted);
  margin-right: 4px;
  white-space: nowrap;
}

.filter-tag {
  cursor: pointer;
  transition: all .2s;
}

.filter-tag:hover {
  transform: scale(1.05);
}

/* ── 卡片网格 ── */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  min-height: 100px;
}

.card-item {
  background: var(--c-bg-elevated, #fff);
  border: 1px solid var(--c-border, #e4e7ed);
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all .2s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-item:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 2px 12px rgba(0, 0, 0, .08);
  transform: translateY(-2px);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text-primary);
  line-height: 1.4;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.card-tags-secondary {
  margin-top: -2px;
}

.card-tag {
  font-size: 11px;
}

.card-module-tag {
  border-style: dashed;
}

.card-source {
  font-size: 12px;
  color: var(--c-text-secondary, #606266);
  line-height: 1.6;
  min-height: 38px;
}

.card-preview {
  font-size: 12px;
  color: var(--c-text-muted, #909399);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--c-text-muted, #909399);
  border-top: 1px solid var(--c-border, #eee);
  padding-top: 8px;
  margin-top: 4px;
}

.card-footnote {
  color: var(--c-text-secondary, #606266);
}

.card-modules {
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cards-count {
  text-align: center;
  padding: 16px 0;
  font-size: 12px;
  color: var(--c-text-muted);
}

/* ── 卡片详情抽屉 ── */
.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-meta-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.detail-label {
  font-size: 12px;
  color: var(--c-text-muted);
  min-width: 60px;
  padding-top: 3px;
  flex-shrink: 0;
}

.detail-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.detail-sources {
  font-size: 12px;
  color: var(--c-text-secondary, #606266);
}

.source-item {
  padding: 2px 0;
}

.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--c-text-primary);
}

.detail-content :deep(h1) { font-size: 18px; margin: 16px 0 8px; }
.detail-content :deep(h2) { font-size: 16px; margin: 14px 0 6px; }
.detail-content :deep(h3) { font-size: 14px; margin: 12px 0 4px; }
.detail-content :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
.detail-content :deep(th),
.detail-content :deep(td) { border: 1px solid var(--c-border, #e4e7ed); padding: 6px 10px; text-align: left; }
.detail-content :deep(th) { background: var(--c-bg-sunken, #f5f7fa); font-weight: 600; }
.detail-content :deep(code) { background: var(--c-bg-sunken, #f5f7fa); padding: 2px 6px; border-radius: 4px; font-size: 12px; }
.detail-content :deep(pre) { background: var(--c-bg-sunken, #f5f7fa); padding: 12px; border-radius: 8px; overflow-x: auto; }
.detail-content :deep(pre code) { padding: 0; background: none; }
.detail-content :deep(ul),
.detail-content :deep(ol) { padding-left: 20px; }
.detail-content :deep(li) { margin: 4px 0; }

.text-muted { font-size: 12px; color: var(--c-text-muted, #909399); }

/* ── 编辑器 ── */
.yaml-preview-collapse {
  margin-top: 8px;
}

.upload-dialog-form {
  padding-top: 4px;
}

.upload-file-picker {
  width: 100%;
}

.upload-file-picker :deep(.el-upload) {
  width: 100%;
}

.upload-file-picker :deep(.el-upload-dragger) {
  width: 100%;
  padding: 24px 16px;
}

.upload-hint {
  margin: 8px 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary);
}

.yaml-preview {
  background: var(--c-bg-sunken, #f5f7fa);
  padding: 12px;
  border-radius: 6px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0;
}

.empty-tip {
  text-align: center;
  color: var(--c-text-muted);
  padding: 40px 16px;
  font-size: 13px;
}

</style>
