# SimuReport API 使用文档

> 外部平台接入指南 — 从数据上传到报告生成的完整 API 调用流程

---

## 快速开始：一键生成报告

如果你只想尽快得到一份报告，只需调用一个接口：

```bash
curl -X POST http://127.0.0.1:5000/api/v1/report/generate \
  -H "Authorization: ApiKey sr_你的密钥" \
  -H "Content-Type: application/json" \
  -d '{
    "data": { "path": "E:/你的数据包路径" },
    "config": {
      "domain": "aerospace",
      "purpose": "show",
      "template_id": "cfd_standard"
    }
  }'
```

返回值包含生成的报告文件路径（`.md`、`.docx`、`.pdf`）和质量评分。

---

## 认证方式

所有带 🔒 标记的接口需要认证，支持两种方式：

| 方式 | Header 格式 | 适用场景 |
|------|------------|---------|
| JWT Token | `Authorization: Bearer <token>` | 前端用户登录后使用 |
| API Key | `Authorization: ApiKey sr_xxx...` | 外部平台集成 |

### 获取 API Key

1. 使用 `admin` 角色账号登录（默认：`admin` / `admin123456`）
2. 调用 `POST /api/admin/api-keys` 创建密钥
3. 密钥仅在创建时展示一次，请妥善保存

```bash
# 登录获取 Token
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123456"}'

# 用 Token 创建 API Key
curl -X POST http://127.0.0.1:5000/api/admin/api-keys \
  -H "Authorization: Bearer <你的token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "外部平台集成"}'
```

---

## 完整调用流程

如果你想要更精细的控制，可以按以下 5 步分步调用：

```
步骤1: 上传数据包  →  步骤2: 配置报告  →  步骤3: 生成内容  →  步骤4: 确认  →  步骤5: 导出
```

### 步骤 1：上传数据包

**方式 A：指定本地路径**

```bash
curl -X POST http://127.0.0.1:5000/api/upload-folder \
  -H "Content-Type: application/json" \
  -d '{"path": "E:/仿真数据/plot3d_case01"}'
```

**方式 B：上传 ZIP 文件**

```bash
curl -X POST http://127.0.0.1:5000/api/upload \
  -F "file=@datapackage.zip"
```

**方式 C：直接提交标准 Schema JSON**

```bash
curl -X POST http://127.0.0.1:5000/api/ingest \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "manifest": {
      "source_platform": "MySimTool",
      "dataset_name": "wing_case_01",
      "dataset_type": "structured_grid",
      "block_count": 2,
      "total_points": 150000
    },
    "variables": [
      { "name": "Density", "display_name": "密度", "unit": "kg/m^3",
        "components": 1, "range_min": 0.8, "range_max": 1.4 }
    ],
    "datasets": {},
    "images": {},
    "metadata": { "solver": "RANS", "mach_number": 0.8 }
  }'
```

**返回示例：**

```json
{
  "success": true,
  "path": "E:/仿真数据/plot3d_case01",
  "info": {
    "format": "SimuVision/Plot3D",
    "blocks": 11,
    "total_points": 1002672,
    "variables": ["F1V1", "F1V2", "F1V3", "F1V4", "F1V5"]
  }
}
```

### 步骤 2：配置报告参数

```bash
curl -X POST http://127.0.0.1:5000/api/clarification/submit \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "aerospace",
    "purpose": "show",
    "phenomena": ["shock_wave", "turbulence"],
    "inference_level": "may_infer",
    "template_id": "cfd_standard",
    "enable_web_search": false,
    "terminology": { "var_style": "chinese" }
  }'
```

**可选配置字段：**

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `domain` | 仿真领域 | `aerospace`, `automotive`, `building`, `chemical`, `energy`, `marine`, `hvac`, `electronics`, `biomedical`, `general` |
| `purpose` | 报告目的 | `show`（展示结果）, `diagnose`（问题诊断）, `compare`（方案对比）, `acceptance`（验收评估） |
| `phenomena` | 关注物理现象 | `flow_separation`, `turbulence`, `shock_wave`, `heat_transfer`, `mixing`, `combustion`, `multiphase`, `boundary_layer`, `vortex`, `pressure_loss` |
| `inference_level` | 推断强度 | `describe_only`, `may_infer` |
| `template_id` | 报告模板 | `cfd_standard`, `comparison_report`, `acceptance_report` |

### 步骤 3：生成报告内容

**逐个生成（推荐，可监控进度）：**

```bash
# 循环调用直到 all_done=true
curl -X POST http://127.0.0.1:5000/api/slots/generate-next
```

**批量生成：**

```bash
curl -X POST http://127.0.0.1:5000/api/slots/generate-all
```

**查看进度：**

```bash
curl http://127.0.0.1:5000/api/draft
# 返回 progress: { total, pending, draft, accepted, progress }
```

### 步骤 4：确认所有槽位

```bash
curl -X POST http://127.0.0.1:5000/api/slots/accept-all
```

### 步骤 5：导出报告

```bash
# 触发导出
curl -X POST http://127.0.0.1:5000/api/export/report

# 下载文件
curl -O http://127.0.0.1:5000/api/download/md
curl -O http://127.0.0.1:5000/api/download/docx
curl -O http://127.0.0.1:5000/api/download/pdf   # 需安装 weasyprint
curl -O http://127.0.0.1:5000/api/download/draft
```

---

## MCP 工具调用

外部平台可以直接调用 MCP 工具来查询数据、检索知识，而不一定需要完成完整的报告生成流程。

### 列出所有工具

```bash
curl http://127.0.0.1:5000/mcp/tools/list \
  -H "Authorization: ApiKey sr_xxx"
```

### 调用指定工具

```bash
# 查询数据包信息
curl -X POST http://127.0.0.1:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "get_run_info", "arguments": {}}'

# 知识库检索
curl -X POST http://127.0.0.1:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "rag_query", "arguments": {"query": "Plot3D格式Q变量物理含义", "top_k": 5}}'

# 计算变量统计
curl -X POST http://127.0.0.1:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "compute_metrics", "arguments": {"signals": ["F1V1", "F1V2"]}}'

# 获取派生物理量
curl -X POST http://127.0.0.1:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "get_derived_quantities", "arguments": {}}'
```

### 工具使用统计

```bash
# 查看工具调用统计
curl http://127.0.0.1:5000/api/mcp/analytics

# 查看最近的调用日志
curl http://127.0.0.1:5000/api/mcp/logs?limit=20
```

**统计返回示例：**

```json
{
  "total_calls": 45,
  "success_rate": 0.978,
  "avg_duration_ms": 234.5,
  "tools": {
    "get_run_info": { "count": 8, "avg_duration_ms": 12.3, "errors": 0 },
    "rag_query": { "count": 15, "avg_duration_ms": 456.7, "errors": 1 },
    "generate_next_slot": { "count": 12, "avg_duration_ms": 3200.1, "errors": 0 }
  },
  "by_category": { "data": 20, "knowledge": 15, "workflow": 10 }
}
```

---

## AI 对话接口（SSE 流式）

通过 AI 对话接口，可以用自然语言驱动整个报告生成流程：

```bash
curl -X POST http://127.0.0.1:5000/api/mcp-chat-stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [
      {"role": "user", "content": "帮我分析一下当前数据包的流场特征"}
    ],
    "webSearchEnabled": false
  }'
```

**SSE 事件类型：**

| 事件类型 | 说明 |
|---------|------|
| `tool_call` | AI 正在调用 MCP 工具（含工具名和参数） |
| `delta` | 流式文本内容（逐字输出） |
| `done` | 回复完成（含完整 tool_calls 列表） |
| `error` | 发生错误 |

---

## 数据包格式规范

### 查看规范

```bash
curl http://127.0.0.1:5000/api/data-package/spec
```

### 验证数据包

```bash
curl -X POST http://127.0.0.1:5000/api/data-package/validate
```

### 标准 Schema 定义

```bash
curl http://127.0.0.1:5000/api/schema
```

### 数据包目录结构

```
数据包/
├── manifest.json        ★ 必须 — 数据包清单
├── variables.json       ★ 必须 — 流场变量列表
├── datasets.json          推荐 — 网格块详细信息
├── images/                可选 — 可视化截图
│   ├── geometry/
│   ├── mesh/
│   └── variables/
└── automation/            可选 — 后处理操作
```

---

## 报告质量评估

```bash
curl -X POST http://127.0.0.1:5000/api/report/quality-check \
  -H "Authorization: ApiKey sr_xxx"
```

**返回示例：**

```json
{
  "total_score": 82,
  "dimensions": {
    "data_coverage": 85,
    "traceability": 78,
    "professionalism": 88,
    "coherence": 76
  },
  "suggestions": [
    "建议补充变量F1V3的物理意义分析",
    "结论章节可增加对网格独立性的讨论"
  ],
  "summary": "报告整体质量良好，数据引用充分..."
}
```

---

## 错误处理

所有接口在错误时返回统一格式：

```json
{
  "success": false,
  "error": "错误描述信息"
}
```

常见 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或认证过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## Python SDK 示例

```python
import requests

BASE_URL = "http://127.0.0.1:5000"
API_KEY = "sr_你的密钥"
HEADERS = {"Authorization": f"ApiKey {API_KEY}", "Content-Type": "application/json"}

# 一键生成
resp = requests.post(f"{BASE_URL}/api/v1/report/generate", headers=HEADERS, json={
    "data": {"path": "E:/数据包"},
    "config": {"domain": "aerospace", "purpose": "show"}
})
result = resp.json()
print(f"报告已生成: {result.get('output_dir')}")

# 分步生成
requests.post(f"{BASE_URL}/api/upload-folder", json={"path": "E:/数据包"})
requests.post(f"{BASE_URL}/api/clarification/submit", json={"domain": "aerospace", "purpose": "show"})
requests.post(f"{BASE_URL}/api/slots/generate-all")
requests.post(f"{BASE_URL}/api/slots/accept-all")
resp = requests.post(f"{BASE_URL}/api/export/report")
print(f"导出完成: {resp.json()}")
```

---

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| Node.js | 18+ |
| DeepSeek API Key | 必须（用于 LLM 生成） |
| Tavily API Key | 可选（用于联网搜索） |

### 安装和启动

```bash
# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install

# 设置环境变量
$env:DEEPSEEK_API_KEY = "your-key"

# 启动后端（端口 5000）
python server/app_v2.py

# 启动前端（端口 3001，另一个终端）
cd frontend && npm run dev
```
