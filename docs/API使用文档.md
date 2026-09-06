# SimuReport HTTP API 使用文档

> 面向外部平台和集成方的 RESTful 接口手册 — 从数据上传到报告生成、知识库管理、组织协作的完整 API 调用流程。
>
> 文档版本：v2.0 ｜ 更新日期：2026-04 ｜ 对应后端端口：`5000`

---

## 目录

1. [快速开始：一键生成报告](#1-快速开始一键生成报告)
2. [认证体系](#2-认证体系)
3. [完整调用流程（5 步）](#3-完整调用流程5-步)
4. [核心资源接口](#4-核心资源接口)
5. [知识库接口](#5-知识库接口)
6. [组织管理接口](#6-组织管理接口)
7. [管理员接口](#7-管理员接口)
8. [MCP 与 AI 对话](#8-mcp-与-ai-对话)
9. [异步任务与模板](#9-异步任务与模板)
10. [错误处理与状态码](#10-错误处理与状态码)
11. [SDK 示例](#11-sdk-示例)
12. [环境与依赖](#12-环境与依赖)

---

## 1. 快速开始：一键生成报告

如果只想尽快得到一份报告，只需一个接口：

```bash
curl -X POST http://127.0.0.1:5000/api/v1/report/generate \
  -H "Authorization: ApiKey sr_你的密钥" \
  -H "Content-Type: application/json" \
  -d '{
    "data": { "path": "E:/数据包路径" },
    "config": {
      "domain": "external_aero",
      "purpose": "design_validation",
      "template_id": "cfd_standard"
    }
  }'
```

**返回示例**：

```json
{
  "success": true,
  "mode": "sync",
  "report_id": 128,
  "files": {
    "markdown": "/api/download/md",
    "word": "/api/download/docx",
    "draft": "/api/download/draft"
  },
  "quality": { "total_score": 84, "summary": "..." },
  "output_dir": "server/reports/20260419_115830"
}
```

**异步模式**：body 中加 `"async": true`，返回 `task_id`，再通过 `GET /api/tasks/<task_id>` 轮询。

---

## 2. 认证体系

### 2.1 两套"Key"的区别（重要）

本系统存在**两套独立的密钥概念**，千万不要混淆：

| 名称 | 接口 | 作用 | 谁签发 | 外部是否可见 |
|------|------|------|--------|:----:|
| **接入 Api Key** | `/api/admin/api-keys` | 外部系统**调用 SimuReport 的鉴权凭证** | 管理员 | ✅ 给集成方 |
| **LLM 密钥池** | `/api/admin/ai-keys` | SimuReport **内部调用大模型的凭证** | 管理员 | ❌ 对外不暴露 |

> 作为第三方集成方，你只需要关心第一套（接入 Api Key）。第二套是系统自己用的。

### 2.2 认证方式

所有带 🔒 的接口必须携带身份凭证，支持两种方式：

| 方式 | Header 格式 | 适用场景 |
|------|------------|---------|
| **JWT Token** | `Authorization: Bearer <token>` | 前端用户登录后使用 |
| **接入 Api Key** | `Authorization: ApiKey sr_xxx...` | 第三方后端系统集成 |

### 2.3 登录获取 JWT

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alice_pass"}'
```

**成功响应**：

```json
{
  "success": true,
  "token": "eyJhbGci...",
  "user": { "id": 5, "username": "alice", "display_name": "Alice", "role": "user" }
}
```

### 2.4 获取接入 Api Key（管理员操作）

```bash
# Step 1: 管理员登录
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<admin_password>"}'

# Step 2: 用管理员 JWT 签发一条 Api Key（raw_key 只在此处展示一次）
curl -X POST http://127.0.0.1:5000/api/admin/api-keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"第三方仿真软件 - 生产环境"}'
```

**返回**：

```json
{ "success": true, "id": 3, "raw_key": "sr_7f8a9b...", "created_at": "..." }
```

### 2.5 当前用户 AI 配置（只读）

普通用户可以查看当前系统生效的 LLM 模型和脱敏密钥，但**不能修改**——`PUT /api/user/ai-config` 会返回 403。

```bash
curl http://127.0.0.1:5000/api/user/ai-config \
  -H "Authorization: Bearer <jwt>"
```

**响应**：

```json
{
  "success": true,
  "config": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key_masked": "sk-7f***a2d1",
    "managed_by": "admin"
  }
}
```

---

## 3. 完整调用流程（5 步）

如果需要精细控制，可按以下 5 步串起来：

```
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 1 上传   │ -> │ 2 配置   │ -> │ 3 生成   │ -> │ 4 确认   │ -> │ 5 导出   │
  │ 数据包   │    │ 报告策略 │    │ 槽位内容 │    │ 全部槽位 │    │ md/docx  │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 步骤 1：上传数据包

三种等效方式：

**A) 本地路径**（最常用）

```bash
curl -X POST http://127.0.0.1:5000/api/upload-folder \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"path":"E:/仿真数据/plot3d_case01"}'
```

**B) ZIP 上传**

```bash
curl -X POST http://127.0.0.1:5000/api/upload \
  -H "Authorization: ApiKey sr_xxx" \
  -F "file=@datapackage.zip"
```

**C) 标准 Schema JSON 直传**（无文件系统依赖，最灵活）

```bash
curl -X POST http://127.0.0.1:5000/api/ingest \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "manifest": {
      "spec_version": "1.0",
      "dataset": { "datasetType": "Plot3DMultiBlock", "blockCount": 11 }
    },
    "variables": [
      {"name":"F1V1","guess_variableName":"density","components":1,
       "rangeGlobal":{"min":0.128,"max":3.007}}
    ]
  }'
```

**返回示例**：

```json
{
  "success": true,
  "path": "E:/仿真数据/plot3d_case01",
  "info": {
    "format": "Plot3DMultiBlock",
    "blocks": 11,
    "total_points": 1002672,
    "variables": ["F1V1","F1V2","F1V3","F1V4","F1V5"]
  }
}
```

### 步骤 2：配置报告参数

```bash
curl -X POST http://127.0.0.1:5000/api/clarification/submit \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "external_aero",
    "purpose": "design_validation",
    "phenomena": ["shock_wave","flow_separation"],
    "inference_level": "may_infer",
    "template_id": "cfd_standard",
    "enable_web_search": false,
    "enable_system_kb": true,
    "enable_personal_kb": true,
    "enable_org_kb": true
  }'
```

**配置字段**：

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `domain` | 仿真领域 | `external_aero` / `turbomachinery` / `internal_flow` / `heat_transfer` / `structural` / `general_cfd` |
| `purpose` | 报告目的 | `design_validation` / `performance_evaluation` / `troubleshooting` / `academic_research` |
| `phenomena` | 关注物理现象 | `flow_separation` / `turbulence` / `shock_wave` / `heat_transfer` / `mixing` / `combustion` / `multiphase` / `boundary_layer` / `vortex` / `pressure_loss` |
| `inference_level` | 推断强度 | `describe_only`（仅描述） / `may_infer`（可合理推断） |
| `template_id` | 报告模板 | `cfd_standard` / `comparison_report` / `acceptance_report` |
| `enable_web_search` | 是否启用联网搜索 | `boolean`，默认 `false` |
| `enable_system_kb` | **是否启用系统知识库** | `boolean`，默认 `true` |
| `enable_personal_kb` | **是否启用个人知识库** | `boolean`，默认 `true` |
| `enable_org_kb` | **是否启用组织知识库** | `boolean`，默认 `true` |

> 三层 KB 开关在 RAG 检索时生效：关闭哪一层，检索时对应集合就不会被搜。

### 步骤 3：生成报告内容

**逐个生成**（可监控进度）：

```bash
curl -X POST http://127.0.0.1:5000/api/slots/generate-next \
  -H "Authorization: ApiKey sr_xxx"
# 循环调用直到返回 completed: true
```

**批量生成**：

```bash
curl -X POST http://127.0.0.1:5000/api/slots/generate-all \
  -H "Authorization: ApiKey sr_xxx"
```

**查看进度**：

```bash
curl http://127.0.0.1:5000/api/draft \
  -H "Authorization: ApiKey sr_xxx"
```

返回体含 `progress: { total, pending, draft, accepted, progress }`。

### 步骤 4：确认所有槽位

```bash
curl -X POST http://127.0.0.1:5000/api/slots/accept-all \
  -H "Authorization: ApiKey sr_xxx"
```

### 步骤 5：导出并下载

```bash
curl -X POST http://127.0.0.1:5000/api/export/report \
  -H "Authorization: ApiKey sr_xxx"

# 下载
curl -O -J -H "Authorization: ApiKey sr_xxx" http://127.0.0.1:5000/api/download/md
curl -O -J -H "Authorization: ApiKey sr_xxx" http://127.0.0.1:5000/api/download/docx
curl -O -J -H "Authorization: ApiKey sr_xxx" http://127.0.0.1:5000/api/download/draft
```

---

## 4. 核心资源接口

### 4.1 数据包

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/data-package/spec` | — | 拉取数据包规范（schema + 示例） |
| POST | `/api/data-package/validate` | ✅ | 验证当前已加载的数据包是否合规 |
| GET | `/api/data-package/facts` | ✅ | 拉取当前数据包解析后的 facts 结构 |
| POST | `/api/upload-folder` | ✅ | 指定本地目录作为数据包 |
| POST | `/api/upload` | ✅ | 上传 ZIP 文件作为数据包 |
| POST | `/api/ingest` | ✅ | 通过标准 Schema JSON 直接提交 |
| GET | `/api/schema` | — | 获取标准输入 Schema 定义 |
| POST | `/api/schema/validate` | — | 验证 JSON 是否符合标准 Schema |

**数据包规范验证示例**：

```bash
curl -X POST http://127.0.0.1:5000/api/data-package/validate \
  -H "Authorization: ApiKey sr_xxx"
```

**返回**：

```json
{
  "is_valid": true,
  "spec_version": "1.0",
  "errors": [],
  "warnings": ["manifest.json 未声明 spec_version，建议添加 \"spec_version\":\"1.0\""]
}
```

### 4.2 Clarification（报告配置问答）

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/clarification/questions` | — | 获取问题清单（用于前端展示） |
| POST | `/api/clarification/submit` | ✅ | 提交答案并创建 Draft |

### 4.3 Draft & Policy

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/draft` | — | 获取当前 Draft 全貌（含 slots、progress、policy） |
| PUT | `/api/draft/policy` | — | 更新 Draft 策略（部分字段即可） |

**策略更新示例**（把组织知识库从启用改为停用）：

```bash
curl -X PUT http://127.0.0.1:5000/api/draft/policy \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"enable_org_kb": false}'
```

**返回**：

```json
{
  "success": true,
  "affected_slots": 3,
  "policy": {
    "enable_system_kb": true,
    "enable_personal_kb": true,
    "enable_org_kb": false,
    "enable_web_search": false,
    "inference_level": "may_infer"
    /* ... */
  },
  "draft_exists": true
}
```

`affected_slots` 表示策略变化后有多少已生成的槽位被标回 `pending`（意味着需要重新生成以反映新策略）。

### 4.4 Slots（章节槽位）

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/slots` | — | 列出所有槽位 |
| POST | `/api/slots/generate-next` | — | 生成下一个 pending 槽位 |
| POST | `/api/slots/generate-all` | — | 批量生成所有 pending 槽位 |
| POST | `/api/slots/<slot_id>/accept` | — | 接受指定槽位 |
| POST | `/api/slots/accept-all` | — | 一键接受所有 draft 槽位 |
| POST | `/api/slots/<slot_id>/reject` | — | 拒绝（标回 pending） |
| POST | `/api/slots/<slot_id>/rewrite` | — | 带指示重写（body 里传 `instruction`） |
| PUT | `/api/slots/<slot_id>/edit` | — | 手动编辑槽位内容（body 传 `content`） |

**重写示例**：

```bash
curl -X POST http://127.0.0.1:5000/api/slots/geometry_description/rewrite \
  -H "Content-Type: application/json" \
  -d '{"instruction":"请补充绕流体的横截面面积与参考尺寸"}'
```

**编辑示例**：

```bash
curl -X PUT http://127.0.0.1:5000/api/slots/conclusion/edit \
  -H "Content-Type: application/json" \
  -d '{"content":"# 结论\n本算例在 Ma=0.82 工况下..."}'
```

### 4.5 报告质量评估

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| POST | `/api/report/quality-check` | ✅ | 生成质量评分与建议 |
| POST | `/api/report/quality-improve` | ✅ | 基于建议自动改进 |

**返回示例**：

```json
{
  "total_score": 84,
  "dimensions": {
    "data_coverage": 88,
    "traceability": 82,
    "professionalism": 86,
    "coherence": 80
  },
  "suggestions": [
    "建议补充变量 F1V3 的物理意义分析",
    "结论章节可增加对网格独立性的讨论"
  ],
  "summary": "报告整体质量良好，数据引用充分..."
}
```

### 4.6 导出与下载

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/export/draft` | — | 导出当前 Draft JSON（含 slots、policy） |
| POST | `/api/export/report` | ✅ | 触发生成 md + docx 文件 |
| GET | `/api/download/<type>` | ✅ | 下载指定类型的文件 |

`<type>` 取值：`md`、`docx`、`draft`、`pdf`（pdf 需要安装 `weasyprint`）。

### 4.7 报告版本与 diff

| 方法 | 路径 | 🔒 | 作用 |
|------|------|:--:|------|
| GET | `/api/reports/<int:report_id>/versions` | ✅ | 列出某份报告的所有历史版本 |
| GET | `/api/reports/<int:report_id>/diff?from=<v1>&to=<v2>` | ✅ | 查看两个版本之间的差异 |

---

## 5. 知识库接口

系统支持三级知识库：**系统知识卡片（仅管理员可写）** / **个人知识库** / **组织知识库**。

### 5.1 系统知识卡片（SystemCard）

| 方法 | 路径 | 🔒 | 权限 |
|------|------|:--:|------|
| GET | `/api/kb/cards` | — | 所有人可查 |
| GET | `/api/kb/cards/<card_id>` | — | 所有人可查 |
| POST | `/api/kb/cards` | ✅ | 仅管理员 |
| PUT | `/api/kb/cards/<card_id>` | ✅ | 仅管理员 |
| DELETE | `/api/kb/cards/<card_id>` | ✅ | 仅管理员 |

**卡片字段**：`id` / `title` / `content` / `tags` / `domain` / `module` / `priority` / `created_at` / `updated_at`。

### 5.2 个人知识库

| 方法 | 路径 | 🔒 | 说明 |
|------|------|:--:|------|
| POST | `/api/kb/upload` | ✅ | 上传个人文档（multipart） |
| GET | `/api/kb/documents` | ✅ | 列出我的文档 |
| GET | `/api/kb/documents/<doc_id>` | ✅ | 查看文档详情 + 正文 |
| **PUT** | **`/api/kb/documents/<doc_id>`** | ✅ | **更新属性 + 可选正文（Markdown / 文本自动重建向量）** |
| DELETE | `/api/kb/documents/<doc_id>` | ✅ | 删除文档 |
| GET | `/api/kb/changelog` | ✅ | 拉取变更日志 |

**上传示例**：

```bash
curl -X POST http://127.0.0.1:5000/api/kb/upload \
  -H "Authorization: Bearer <jwt>" \
  -F "file=@CFD流场分析入门要点.md" \
  -F 'tags=["CFD","入门"]' \
  -F 'report_modules=["methodology","results"]' \
  -F 'sources=["个人学习笔记"]'
```

**更新文档属性 + 正文**（**这是最近新增的能力**）：

```bash
curl -X PUT http://127.0.0.1:5000/api/kb/documents/42 \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["CFD","入门","外流"],
    "report_modules": ["methodology"],
    "sources": ["个人学习笔记（2026-04 更新）"],
    "content": "# CFD 外流入门要点\n..（完整 Markdown 正文）.."
  }'
```

**行为**：
- `tags` / `report_modules` / `sources` 必须至少各有一项（否则 400）
- `content` 是可选字段。**如果提供且非空**：
  - 仅支持 `.md` / `.markdown` / `.txt` 三类文档
  - 系统会**删除旧向量块**，按新内容重新分块并嵌入
  - 返回体多一个 `chunk_count` 字段表示新的块数量
- 仅 `scope=personal` 且 `user_id` 匹配的文档可编辑，否则 403

**返回示例**：

```json
{
  "success": true,
  "message": "文档已更新（属性 + 正文）",
  "document": { "id": 42, "title": "...", "tags": [...], "..." },
  "chunk_count": 18
}
```

### 5.3 组织知识库

| 方法 | 路径 | 🔒 | 说明 |
|------|------|:--:|------|
| POST | `/api/kb/orgs/<org_id>/upload` | ✅ | 组织成员上传共享文档 |
| POST | `/api/kb/orgs/<org_id>/import-personal` | ✅ | 把自己的个人文档导入组织 |
| GET | `/api/kb/orgs/<org_id>/documents` | ✅ | 列出组织文档 |
| GET | `/api/kb/orgs/<org_id>/documents/<doc_id>` | ✅ | 文档详情 |
| **PUT** | **`/api/kb/orgs/<org_id>/documents/<doc_id>`** | ✅ | **更新（组织成员同权）** |
| DELETE | `/api/kb/orgs/<org_id>/documents/<doc_id>` | ✅ | 删除 |
| GET | `/api/kb/orgs/<org_id>/changelog` | ✅ | 组织变更日志 |

**组织文档更新**与个人文档完全同构（同样支持 `content` 字段正文编辑），权限边界改为"当前用户必须是该组织的成员"。

---

## 6. 组织管理接口

| 方法 | 路径 | 🔒 | 说明 |
|------|------|:--:|------|
| GET | `/api/orgs` | ✅ | 我所属的组织列表 |
| GET | `/api/orgs/discover` | ✅ | 我可加入的组织（用于发现） |
| POST | `/api/orgs` | ✅ | 创建组织 |
| POST | `/api/orgs/<org_id>/join` | ✅ | 加入组织 |
| POST | `/api/orgs/<org_id>/leave` | ✅ | 退出组织（最后一人退出等价解散） |
| GET | `/api/orgs/<org_id>/export` | ✅ | 下载组织知识库归档 ZIP |
| GET | `/api/orgs/<org_id>/members` | ✅ | 成员列表（成员可查） |
| POST | `/api/orgs/<org_id>/members` | ✅ | 添加成员（按用户名） |
| PUT | `/api/orgs/<org_id>/members/<uid>/role` | ✅ | 兼容保留，组织内成员同权 |
| DELETE | `/api/orgs/<org_id>/members/<uid>` | ✅ | 移除成员 |
| GET | `/api/orgs/<org_id>/reports` | ✅ | 组织可见的报告列表 |

**创建组织示例**：

```bash
curl -X POST http://127.0.0.1:5000/api/orgs \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"仿真报告质量保障组","description":"负责评审各业务线的仿真报告"}'
```

---

## 7. 管理员接口

> 以下接口均需 **管理员角色**（`role=admin`）。

### 7.1 用户管理

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/admin/users?scope=all` | 列出用户（`scope=all` 全部 / 默认 active） |
| PUT | `/api/admin/users/<uid>/role` | 修改用户角色（`user` / `admin`） |
| GET | `/api/admin/audit-logs` | 审计日志 |

### 7.2 接入 Api Key 管理（对外签发）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/admin/api-keys` | 列出已签发的 Api Key（脱敏） |
| POST | `/api/admin/api-keys` | 签发新 Api Key（raw_key 仅此处返回一次） |
| DELETE | `/api/admin/api-keys/<key_id>` | 停用 Api Key |

### 7.3 LLM 密钥池管理（系统内部使用）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/admin/ai-keys` | 列出所有 LLM 密钥配置（脱敏） |
| POST | `/api/admin/ai-keys` | 新增一条 LLM 密钥配置 |
| POST | `/api/admin/ai-keys/<id>/activate` | 启用指定配置为当前生效 |
| POST | `/api/admin/ai-keys/<id>/deactivate` | 停用指定配置（不删除） |
| DELETE | `/api/admin/ai-keys/<id>` | 删除（建议先停用） |

**新增 LLM 密钥示例**：

```bash
curl -X POST http://127.0.0.1:5000/api/admin/ai-keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DeepSeek Production",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "activate": true
  }'
```

**行为**：
- `activate=true` 会**自动把同 provider 的其他配置置为非活跃**（单活跃约束）
- 创建后，系统所有 LLM 调用（报告生成、AI 对话、MCP 工作流）立刻切换到新密钥
- 普通用户通过 `/api/user/ai-config` 只能看到脱敏后的 `api_key_masked`

---

## 8. MCP 与 AI 对话

### 8.1 MCP 标准端点

| 方法 | 路径 | 作用 |
|------|------|------|
| GET/POST | `/mcp/tools/list` | 列出所有已注册 MCP 工具 |
| POST | `/mcp/tools/call` | 调用指定工具（body: `{name, arguments}`） |
| POST | `/api/tools/<tool_name>` | 便捷端点：等价于 tools/call |
| GET/POST | `/mcp/resources/list` | 列出可用资源 |
| GET/POST | `/mcp/resources/read` | 读取资源（query 或 body 的 `uri`） |

详见 [MCP 工具文档](./MCP工具文档.md)。

### 8.2 AI 对话（SSE 流式）

```bash
curl -N -X POST http://127.0.0.1:5000/api/mcp-chat-stream \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [
      {"role":"user","content":"帮我分析一下当前数据包的流场特征"}
    ],
    "webSearchEnabled": false
  }'
```

**SSE 事件类型**：

| 事件 | 含义 |
|------|------|
| `tool_call` | 大模型正在调用某个 MCP 工具（含工具名、参数） |
| `delta` | 流式文本内容（逐字输出） |
| `done` | 对话完成，含完整 `tool_calls` 列表 |
| `error` | 发生错误 |

> 请求里**不需要**传 `apiKey` —— 系统会自动使用管理员 LLM 密钥池里当前启用的那条。

### 8.3 MCP 可观测性

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/mcp/analytics` | 调用统计（总量、成功率、每工具耗时） |
| GET | `/api/mcp/logs?limit=20` | 最近调用日志 |

### 8.4 一键工作流（SSE 流式）

```bash
curl -N -X POST http://127.0.0.1:5000/api/workflow/auto-generate-stream \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "config": { "domain": "external_aero", "phenomena": ["shock_wave"] }
  }'
```

按标准 7 步工具链顺序串联执行，每步通过 SSE `stage` 事件推送实时进度。

---

## 9. 异步任务与模板

### 9.1 异步任务

`POST /api/v1/report/generate` 指定 `"async": true` 后会返回 `task_id`：

```bash
# 轮询单个任务
curl http://127.0.0.1:5000/api/tasks/task_abc123 \
  -H "Authorization: ApiKey sr_xxx"

# 列出最近任务
curl http://127.0.0.1:5000/api/tasks \
  -H "Authorization: ApiKey sr_xxx"
```

**任务状态字段**：`pending` / `running` / `success` / `failed`，完成时 `result` 字段含报告路径。

### 9.2 报告模板

```bash
curl http://127.0.0.1:5000/api/templates
```

返回系统内置模板清单，字段含：`template_id` / `name` / `description` / `applicable_domains` / `default_slots`。

### 9.3 健康检查

```bash
curl http://127.0.0.1:5000/api/health
```

返回 `{"status":"ok","version":"2.0","timestamp":"..."}`。

---

## 10. 错误处理与状态码

### 10.1 错误响应格式

所有错误统一格式：

```json
{ "success": false, "error": "错误描述信息" }
```

部分接口在异常时还会返回 `details` 或 `traceback`（仅 `DEBUG_MODE=1` 时）。

### 10.2 HTTP 状态码

| 状态码 | 含义 | 常见场景 |
|--------|------|---------|
| 200 | 成功 | 正常响应 |
| 400 | 请求参数错误 | 必填字段缺失、格式不合法 |
| 401 | 未认证或认证过期 | Header 缺失、JWT 过期、Api Key 已停用 |
| 403 | 权限不足 | 普通用户访问管理员接口；非成员操作组织文档 |
| 404 | 资源不存在 | 无此 Draft / Slot / 文档 / 组织 |
| 500 | 服务器内部错误 | 代码 Bug；建议查后端日志或联系维护者 |

### 10.3 常见错误举例

| 错误 | 原因 | 处理 |
|------|------|------|
| `"未加载数据包"` | 调用需要数据包的接口前没走上传 | 先走 `/api/upload-folder` 或 `/api/ingest` |
| `"未创建Draft"` | Slots 接口在 Draft 创建前被调用 | 先走 `/api/clarification/submit` 或 MCP 的 `auto_configure` |
| `"无权限编辑此文档"` | 试图编辑非本人/非所在组织的文档 | 检查 `scope` 与 `user_id` / `org_id` |
| `"请至少填写一个标签"` | KB 更新时必填字段空 | `tags` / `report_modules` / `sources` 各需至少 1 项 |

---

## 11. SDK 示例

### 11.1 Python（requests）

```python
import json
import requests

BASE = "http://127.0.0.1:5000"
API_KEY = "sr_你的密钥"
HEAD = {"Authorization": f"ApiKey {API_KEY}", "Content-Type": "application/json"}


def one_shot_generate(data_path: str, domain: str = "external_aero"):
    """一键生成报告（同步）"""
    resp = requests.post(f"{BASE}/api/v1/report/generate", headers=HEAD, json={
        "data": {"path": data_path},
        "config": {"domain": domain, "purpose": "design_validation"}
    })
    resp.raise_for_status()
    result = resp.json()
    print(f"报告 ID: {result['report_id']}，质量分: {result['quality']['total_score']}")
    return result


def step_by_step(data_path: str):
    """分步生成（可观察每一阶段）"""
    # 1. 上传数据包
    requests.post(f"{BASE}/api/upload-folder", headers=HEAD,
                  json={"path": data_path}).raise_for_status()

    # 2. 配置（关闭组织知识库）
    requests.post(f"{BASE}/api/clarification/submit", headers=HEAD, json={
        "domain": "external_aero",
        "phenomena": ["shock_wave"],
        "enable_org_kb": False
    }).raise_for_status()

    # 3. 批量生成
    requests.post(f"{BASE}/api/slots/generate-all", headers=HEAD).raise_for_status()

    # 4. 确认
    requests.post(f"{BASE}/api/slots/accept-all", headers=HEAD).raise_for_status()

    # 5. 导出 + 下载
    out = requests.post(f"{BASE}/api/export/report", headers=HEAD).json()
    for fmt in ("md", "docx"):
        data = requests.get(f"{BASE}/api/download/{fmt}", headers=HEAD).content
        with open(f"report.{fmt}", "wb") as f:
            f.write(data)
    print("完成：report.md、report.docx")


if __name__ == "__main__":
    one_shot_generate("E:/仿真数据/plot3d_case01")
    # step_by_step("E:/仿真数据/plot3d_case01")
```

### 11.2 JavaScript（fetch）

```javascript
const BASE = 'http://127.0.0.1:5000';
const KEY = 'sr_你的密钥';
const HEAD = { Authorization: `ApiKey ${KEY}`, 'Content-Type': 'application/json' };

async function call(path, body) {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: HEAD,
    body: JSON.stringify(body || {})
  });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

(async () => {
  await call('/api/upload-folder', { path: 'E:/data/case01' });
  await call('/api/clarification/submit', {
    domain: 'external_aero',
    phenomena: ['shock_wave'],
    enable_org_kb: false
  });
  await call('/api/slots/generate-all');
  await call('/api/slots/accept-all');
  const out = await call('/api/export/report');
  console.log('导出文件:', out.files);
})();
```

### 11.3 流式 AI 对话（SSE）

```python
import json
import requests

resp = requests.post(
    "http://127.0.0.1:5000/api/mcp-chat-stream",
    headers={"Authorization": "ApiKey sr_xxx", "Accept": "text/event-stream"},
    json={"messages": [{"role": "user", "content": "分析当前数据包流场特征"}]},
    stream=True
)

for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data:"):
        continue
    payload = json.loads(line[5:].strip())
    if payload.get("event") == "tool_call":
        print(f"→ 调用工具: {payload['name']}({payload['arguments']})")
    elif payload.get("event") == "delta":
        print(payload["content"], end="", flush=True)
    elif payload.get("event") == "done":
        print("\n✅ 对话完成")
        break
```

---

## 12. 环境与依赖

### 12.1 运行环境

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| Node.js | 18+（仅前端需要） |
| 向量数据库 | 内置 ChromaDB（pip 自动安装） |
| 大模型 | DeepSeek（默认） / OpenAI 兼容接口 |

### 12.2 启动服务

```bash
# 安装后端依赖
pip install -r requirements.txt

# 启动后端（端口 5000）
python server/app_v2.py

# 可选：启动集成演示（端口 5100 + 3002）
python integration_demo/backend/app.py
cd integration_demo/frontend && npm run dev

# 可选：启动主前端（端口 3001）
cd frontend && npm install
npm run dev
```

**一键启动**：直接双击项目根目录的 `启动项目.bat`，会按正确顺序拉起四个服务，主后端 ready 后再拉其他。

### 12.3 环境变量（可选）

| 变量 | 作用 | 是否必须 |
|------|------|:----:|
| `TAVILY_API_KEY` | 联网搜索凭证 | 否 |
| `DEBUG_MODE` | 开启详细错误栈 | 否 |

> 注意：**LLM API Key 不从环境变量读取**。从 v2.0 起，LLM 密钥由管理员通过 `/api/admin/ai-keys` 统一维护。初始化时若数据库为空，系统会提示管理员登录后添加第一条配置。

### 12.4 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 5000 | 主后端 API | 所有 `/api/*` 和 `/mcp/*` 接口 |
| 5100 | 集成演示后端 | 代理层，模拟第三方仿真软件接入 |
| 3001 | 主前端 | 完整产品 UI |
| 3002 | 集成演示前端 | 模拟外部软件的 UI 壳子 |

---

## 附录 A：接口分类速查表

| 分类 | 主要前缀 | 常用端点 |
|------|----------|----------|
| **认证** | `/api/auth/*` | `login`、`register`、`profile`、`password`、`reports` |
| **一键生成** | `/api/v1/*`、`/api/workflow/*` | `report/generate`、`auto-generate-stream` |
| **数据包** | `/api/upload*`、`/api/ingest`、`/api/data-package/*`、`/api/schema*` | 上传 / 验证 / 规范 |
| **Clarification** | `/api/clarification/*` | `questions`、`submit` |
| **Draft & Slots** | `/api/draft*`、`/api/slots/*` | 配置策略、生成、审核 |
| **质量与导出** | `/api/report/*`、`/api/export/*`、`/api/download/*` | 评估、导出、下载 |
| **知识库** | `/api/kb/*`（含 `/api/kb/orgs/*`） | 卡片、文档 CRUD、变更日志 |
| **组织** | `/api/orgs/*` | 组织、成员、导出 |
| **管理员** | `/api/admin/*` | 用户、API Key、LLM 密钥池、审计日志 |
| **MCP** | `/mcp/*`、`/api/tools/*`、`/api/mcp/*` | 工具发现、调用、统计 |
| **AI 对话** | `/api/mcp-chat-stream` | 流式大模型对话 |
| **异步任务** | `/api/tasks/*` | 查询异步任务状态 |
| **其他** | `/api/health`、`/api/templates`、`/api/session/context` | 健康、模板、会话恢复 |

---

## 附录 B：权限矩阵

| 资源 | 未登录 | 普通用户 | 组织成员 | 管理员 |
|------|:----:|:----:|:----:|:----:|
| 登录 / 注册 | ✅ | — | — | — |
| 查看模板 / 健康 | ✅ | ✅ | ✅ | ✅ |
| 查看 Schema 与规范 | ✅ | ✅ | ✅ | ✅ |
| 上传 / 生成 / 导出 | ❌ | ✅ | ✅ | ✅ |
| 个人知识库 CRUD | ❌ | ✅（仅自己） | ✅（仅自己） | ✅（仅自己） |
| 组织知识库读写 | ❌ | 仅查看非自己组织时 ❌ | ✅（所在组织） | ✅（所在组织） |
| 系统知识卡片写 | ❌ | ❌ | ❌ | ✅ |
| `/api/admin/*` | ❌ | ❌ | ❌ | ✅ |
| `/api/user/ai-config` (GET) | ❌ | ✅（只读） | ✅（只读） | ✅ |
| `/api/user/ai-config` (PUT) | ❌ | ❌（403） | ❌（403） | ❌（403，需用 admin 端点） |

---

*文档结束。相关文档：《MCP 工具文档》《数据包规范文档》《集成部署指南》。*
