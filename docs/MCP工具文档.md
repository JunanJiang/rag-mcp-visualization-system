# SimuReport MCP 工具文档

> MCP（Model Context Protocol，模型上下文协议）是本系统对外开放能力的标准化通道。
> 本文档面向需要通过 MCP 协议接入 SimuReport 的第三方集成方与应用开发者。
>
> 文档版本：v2.0 ｜ 更新日期：2026-04

---

## 目录

1. [概述](#1-概述)
2. [协议规范](#2-协议规范)
3. [工具清单总表](#3-工具清单总表)
4. [数据类工具详解](#4-数据类工具详解)
5. [知识类工具详解](#5-知识类工具详解)
6. [工作流类工具详解](#6-工作流类工具详解)
7. [工具链编排案例](#7-工具链编排案例)
8. [可观测性](#8-可观测性)
9. [扩展指南](#9-扩展指南)

---

## 1. 概述

### 1.1 为什么有这份文档

SimuReport 把系统内部的数据查询、知识检索、报告配置、内容生成、导出等能力，**全部以标准化 MCP 工具的形式对外暴露**。任何一个第三方宿主软件（仿真软件、可视化软件、实验数据管理系统等），只要遵循本文档约定的请求/响应格式，就可以：

- **发现**：动态拉取系统当前开放的工具清单；
- **调用**：按工具协议发起能力请求并拿到结构化结果；
- **编排**：串联多个工具形成端到端工作流（如一键生成报告）。

### 1.2 MCP 在本系统的角色

```
┌──────────────────────────┐       ┌───────────────────────────┐
│   宿主软件 / AI 大模型    │       │  SimuReport 能力后端       │
│                          │       │                           │
│  - 需要调用能力的一方     │──┐    │  - 注册了若干工具的一方    │
│  - 并不预知系统能做什么   │  │    │  - 工具实现放在后端业务层  │
└──────────────────────────┘  │    └───────────────────────────┘
                              │             ▲
                              │  ┌──────────┴──────────┐
                              └──│   MCP 协议端点       │
                                 │  /mcp/tools/list     │
                                 │  /mcp/tools/call     │
                                 │  /mcp/resources/*    │
                                 └─────────────────────┘
```

### 1.3 核心价值

| 能力 | 体现 |
|------|------|
| **能力发现** | 调用方无需预知系统有哪些功能，`tools/list` 一次拉全 |
| **能力调用一致性** | 不论调用方是大模型（自主编排）还是宿主软件（脚本编排），都走同一套协议 |
| **扩展零改动** | 后端新增工具只需注册，不需要改前端或调用方 |
| **可观测可追踪** | 每次调用都进日志与统计，支持成功率、耗时、错误分析 |

---

## 2. 协议规范

### 2.1 基础信息

| 项 | 值 |
|----|----|
| 基础 URL | `http://<host>:5000` |
| 数据格式 | JSON（`Content-Type: application/json`） |
| 字符集 | UTF-8 |
| 鉴权 | JWT Bearer Token 或 Api Key（详见 2.2） |

### 2.2 鉴权

MCP 标准端点要求调用方携带身份凭证。系统支持两种：

| 方式 | Header 格式 | 适用场景 |
|------|------------|---------|
| **JWT Token** | `Authorization: Bearer <token>` | 前端用户登录后通过浏览器调用 |
| **Api Key** | `Authorization: ApiKey sr_<secret>` | 第三方集成（后端服务之间） |

**获取 Api Key**（由管理员签发）：

```bash
# 1) 管理员登录
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<admin_password>"}'
# 返回 { "success": true, "token": "<jwt>" }

# 2) 管理员用 JWT 签发一条 Api Key（只展示一次）
curl -X POST http://localhost:5000/api/admin/api-keys \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"第三方仿真软件 - 生产"}'
# 返回 { "success": true, "id": 3, "raw_key": "sr_xxx..." }  # 保存 raw_key
```

> ⚠️ Api Key 与 **系统 LLM 密钥池** 是两回事。前者用于"**外部调用 SimuReport**"；后者（`/api/admin/ai-keys`）是"**SimuReport 内部调用大模型**"的凭证，不对外暴露，集成方完全不需要关心。

### 2.3 标准端点

| 端点 | 方法 | 作用 |
|------|------|------|
| `/mcp/tools/list` | GET / POST | 列出当前已注册的所有 MCP 工具（OpenAI function calling 格式） |
| `/mcp/tools/call` | POST | 调用指定工具 |
| `/api/tools/<tool_name>` | POST | **便捷端点**：等价于 `/mcp/tools/call`，但通过 URL 指定工具名 |
| `/mcp/resources/list` | GET / POST | 列出可用资源（数据包、Draft 等只读快照） |
| `/mcp/resources/read` | GET / POST | 读取指定资源 |

### 2.4 `tools/list` 请求与响应

**请求**：

```bash
curl -X POST http://localhost:5000/mcp/tools/list \
  -H "Authorization: ApiKey sr_xxx"
```

**响应**（OpenAI function calling 格式，便于大模型直接使用）：

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_run_info",
        "description": "查询当前已加载数据包的元信息...",
        "parameters": { "type": "object", "properties": {}, "required": [] }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "rag_query",
        "description": "从专业知识库中检索...",
        "parameters": {
          "type": "object",
          "properties": {
            "query": { "type": "string", "description": "检索查询词" },
            "top_k": { "type": "integer", "default": 3 }
          },
          "required": ["query"]
        }
      }
    }
    /* ... 其余 10 个工具 ... */
  ]
}
```

### 2.5 `tools/call` 请求与响应

**请求 body**：

```json
{
  "name": "<工具名>",
  "arguments": { "<参数名>": "<参数值>" }
}
```

**示例**：

```bash
curl -X POST http://localhost:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_query",
    "arguments": {"query": "Plot3D 多块结构网格的常见问题", "top_k": 3}
  }'
```

**成功响应**：

```json
{
  "tool": "rag_query",
  "arguments": {"query": "Plot3D 多块结构网格的常见问题", "top_k": 3},
  "result": "{\"query\":\"...\",\"chunks\":[...],\"total\":3}"
}
```

> `result` 字段本身是一个 **JSON 字符串**（便于不同工具自由返回结构）。调用方拿到之后再 `JSON.parse` 一次。

**错误响应**：

```json
{
  "tool": "rag_query",
  "result": "{\"error\":\"未加载数据包\"}"
}
```

> 工具级错误通过 `result` 内嵌的 `error` 字段表达；HTTP 层 200 即视为"**协议层无异常**"。鉴权失败、工具不存在等**协议级错误**才用 HTTP 4xx/5xx。

### 2.6 便捷端点 `/api/tools/<name>`

等价于 `tools/call`，但通过 URL 指定工具名、body 直接是参数对象：

```bash
curl -X POST http://localhost:5000/api/tools/rag_query \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"query":"涡量计算方法","top_k":5}'
```

### 2.7 错误码

| HTTP | 含义 | 典型场景 |
|------|------|----------|
| 200 | 协议成功，工具结果见 body | 正常调用（含工具级错误） |
| 400 | 请求参数错误 | body 不是合法 JSON / 缺少 `name` |
| 401 | 未认证或认证过期 | 缺少 `Authorization` Header |
| 403 | 权限不足 | Api Key 被停用 |
| 404 | 工具不存在 | `name` 指向未注册工具 |
| 500 | 服务器内部错误 | 代码 Bug；建议重试或报 issue |

---

## 3. 工具清单总表

当前系统已注册 **12 个 MCP 工具**，分为三大类：

| # | 工具名 | 类别 | 用途 | 是否需数据包 | 是否需 Draft |
|---|--------|------|------|:----:|:----:|
| 1 | `get_run_info` | data | 数据包元信息概览 | ✅ | — |
| 2 | `list_signals` | data | 列出流场变量 | ✅ | — |
| 3 | `compute_metrics` | data | 计算变量统计（min/max/span） | ✅ | — |
| 4 | `get_mesh_info` | data | 网格块维度与质量分析 | ✅ | — |
| 5 | `get_derived_quantities` | data | 派生物理量（马赫数、流动状态） | ✅ | — |
| 6 | `rag_query` | knowledge | 三级知识库混合检索 | — | 建议 |
| 7 | `web_search` | knowledge | 联网搜索（Tavily） | — | — |
| 8 | `auto_configure` | workflow | 自动提交 Clarification 并创建 Draft | ✅ | — |
| 9 | `generate_next_slot` | workflow | 生成下一个待处理槽位 | ✅ | ✅ |
| 10 | `generate_all_slots` | workflow | 批量生成所有待处理槽位 | ✅ | ✅ |
| 11 | `accept_all_slots` | workflow | 确认所有 draft 槽位 | — | ✅ |
| 12 | `export_report` | workflow | 导出 Markdown / Word | — | ✅ |

> **图例**：
> - ✅ 必需；— 无要求；建议 = 没有也能跑，但效果下降。
> - "需数据包"指调用前必须通过 `POST /api/upload-folder` 或 `POST /api/ingest` 完成数据包装载。
> - "需 Draft"指必须先成功调用过 `auto_configure`。

---

## 4. 数据类工具详解

> 这类工具不触发生成、不修改状态，用于查询当前数据包的客观事实。

### 4.1 `get_run_info` — 数据包元信息

**用途**：一次性拿到当前数据包的顶层概况（数据类型、块数、变量数等）。

**参数**：无。

**返回字段**：

| 字段 | 类型 | 含义 |
|------|------|------|
| `dataset_type` | string | 数据集类型（如 `Plot3DMultiBlock`） |
| `app_name` | string | 导出该数据包的应用名称 |
| `block_count` | int | 网格块数 |
| `total_points` | int | 总网格点数 |
| `total_cells` | int | 总网格单元数 |
| `variable_count` | int | 变量数 |
| `variables` | array<{name, semantic}> | 变量名列表与语义推断 |
| `path` | string | 数据包在后端的物理路径 |

**调用示例**：

```bash
curl -X POST http://localhost:5000/mcp/tools/call \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name":"get_run_info","arguments":{}}'
```

**返回示例**：

```json
{
  "dataset_type": "Plot3DMultiBlock",
  "app_name": "SimuVision-Desktop",
  "block_count": 11,
  "total_points": 1002672,
  "total_cells": 922816,
  "variable_count": 5,
  "variables": [
    {"name": "F1V1", "semantic": "density"},
    {"name": "F1V2", "semantic": "MomentumX"}
  ],
  "path": "E:/data/plot3d_case01"
}
```

**典型错误**：
- `{"error":"未加载数据包"}` — 调用前先走数据包上传。

---

### 4.2 `list_signals` — 列出变量

**用途**：列出所有流场变量，支持按关键词过滤。

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `pattern` | string | 否 | 过滤关键词，匹配变量名或语义名的子串（大小写不敏感），如 `"Momentum"`、`"density"` |

**返回字段**：

```json
{
  "signals": [
    {
      "name": "F1V1",
      "semantic": "density",
      "components": 1,
      "range_min": 0.128,
      "range_max": 3.007
    }
  ],
  "total": 1
}
```

**调用示例**（过滤所有动量分量）：

```bash
curl -X POST http://localhost:5000/api/tools/list_signals \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{"pattern":"Momentum"}'
```

---

### 4.3 `compute_metrics` — 变量统计

**用途**：对指定变量计算 min / max / span 以及反向流标志等。

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `signals` | array\<string\> | ✅ | 要统计的变量名列表，如 `["F1V1","F1V2"]`；**传空数组等价于"全部变量"** |

**返回字段**：

```json
{
  "metrics": {
    "F1V1": {
      "semantic": "density",
      "min": 0.128,
      "max": 3.007,
      "span": 2.879,
      "has_negative": false,
      "has_reverse_flow": false
    },
    "F1V2": {
      "semantic": "MomentumX",
      "min": -314.46,
      "max": 869.04,
      "span": 1183.5,
      "has_negative": true,
      "has_reverse_flow": true
    }
  }
}
```

> `has_reverse_flow` 为 `true` 表示该变量同时跨过 0（既有正值也有负值），对于动量、速度等变量是**回流/分离区**的提示信号。

---

### 4.4 `get_mesh_info` — 网格信息

**用途**：查询网格块的详细维度、分布与质量分析要点。

**参数**：无。

**返回字段（节选）**：

```json
{
  "block_count": 11,
  "blocks": [
    {"name": "Block_1", "dims": [216, 24, 72], "points": 373248, "cells": 351095}
  ],
  "size_distribution": {"min": 8192, "max": 373248, "avg": 91152},
  "largest_block": {"name": "Block_1", "points": 373248},
  "smallest_block": {"name": "Block_7", "points": 8192},
  "resolution_notes": ["Block_1 分辨率较高，可能是主流区"],
  "aspect_ratio_concerns": ["Block_4 的纵横比约 35:1，近壁网格偏拉伸"]
}
```

---

### 4.5 `get_derived_quantities` — 派生物理量

**用途**：从守恒量推算速度估算、马赫数估算、流动状态判断等间接物理量，并给出流场特征的快速评估。

**参数**：无。

**返回字段**：

```json
{
  "derived_quantities": {
    "velocity_magnitude_estimate": {"min": 2.1, "max": 423.8, "unit": "m/s"},
    "mach_number_estimate": 1.28,
    "flow_regime": "transonic",
    "density_ratio": 23.5
  },
  "flow_analysis": {
    "key_findings": ["存在跨音速区域", "密度比跨度较大，存在激波可能性"],
    "attention_points": ["需结合可视化截图确认激波位置"],
    "limitations": ["仅基于全局极值估算，未做局部分析"]
  }
}
```

> 本工具**仅给出估算**，不是精确 CFD 计算结果。真实物理量需要结合求解器导出的附加变量。

---

## 5. 知识类工具详解

### 5.1 `rag_query` — 知识库混合检索

**用途**：从**系统 / 个人 / 组织**三级知识库中混合检索相关文本片段，支撑大模型基于专业资料回答问题或生成章节。

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `query` | string | ✅ | 检索查询词，支持中英文和专业术语混排 |
| `top_k` | integer | 否 | 返回片段数量，默认 3 |

**返回字段**：

```json
{
  "query": "Plot3D 多块结构网格的常见问题",
  "chunks": [
    {
      "content": "Plot3D 格式是 NASA 开发的...（片段文本，至多 500 字符）",
      "source": "CFD后处理最佳实践.md",
      "score": 0.812
    }
  ],
  "total": 3
}
```

**行为细节**：

- 按当前用户所属组织、角色和 Draft 策略自动选择要检索的集合
- 若 Draft 存在，策略字段 `enable_system_kb` / `enable_personal_kb` / `enable_org_kb` 控制三层是否参与
- 分数低于 `0.25` 的片段被过滤
- 未命中时返回 `{"chunks":[], "total":0, "note":"未检索到相关知识"}`

---

### 5.2 `web_search` — 联网搜索

**用途**：调用外部搜索引擎（当前实现基于 Tavily API）补充背景资料。

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `query` | string | ✅ | 搜索关键词 |
| `max_results` | integer | 否 | 返回结果数，默认 5 |

**返回字段**：

```json
{
  "query": "CFD 网格独立性验证",
  "results": [
    {
      "url": "https://example.com/mesh-convergence",
      "title": "Mesh Convergence Study in CFD",
      "snippet": "Mesh convergence refers to ...",
      "domain": "example.com",
      "relevance": 0.87
    }
  ],
  "total": 1
}
```

**前置条件**：
- 后端已配置 Tavily API Key（环境变量 `TAVILY_API_KEY`）
- 当前 Draft 策略未禁用联网搜索（`policy.enable_web_search`）

**失败时返回**：
- `{"error":"联网搜索失败: <原因>","query":"..."}`

---

## 6. 工作流类工具详解

> 这类工具会**修改系统状态**（创建 Draft、生成内容、导出文件等），调用顺序有严格要求。

### 6.1 `auto_configure` — 自动配置报告并创建 Draft

**用途**：跳过前端的 Clarification 交互，直接以参数形式提交答案并创建 Draft。这是**从数据包到报告生成的第一个写操作**。

**参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `domain` | string | `"general_cfd"` | 仿真领域：`external_aero` / `turbomachinery` / `internal_flow` / `heat_transfer` / `structural` / `general_cfd` |
| `phenomena` | array\<string\> | `[]` | 关注的物理现象，如 `["flow_separation","shock_wave","vortex"]` |
| `purpose` | string | `"design_validation"` | 报告目的：`design_validation` / `performance_evaluation` / `troubleshooting` / `academic_research` |
| `inference_level` | string | `"may_infer"` | 推断强度：`describe_only`（只描述）/ `may_infer`（可合理推断） |
| `enable_web_search` | boolean | `false` | 是否启用联网搜索 |
| `enable_system_kb` | boolean | `true` | 是否启用系统知识库 |
| `enable_personal_kb` | boolean | `true` | 是否启用个人知识库 |
| `enable_org_kb` | boolean | `true` | 是否启用组织知识库 |
| `engine_model_name` | string | `""` | 附注字段：模型/算例名称 |
| `project_code` | string | `""` | 附注字段：项目编号 |

**返回示例**：

```json
{
  "success": true,
  "action": "auto_configure",
  "message": "报告配置完成！已创建13个槽位，领域：external_aero，可以开始生成报告。",
  "slot_count": 13,
  "progress": {"total": 13, "pending": 13, "draft": 0, "accepted": 0, "progress": 0.0},
  "domain": "external_aero",
  "phenomena": ["shock_wave","flow_separation"],
  "answers": {
    "Q1_domain": "external_aero",
    "Q2_purpose": "design_validation",
    "Q3_phenomena": ["shock_wave","flow_separation"],
    "Q4_inference": "may_infer",
    "Q5_knowledge_source": "rag_only",
    "Q6_terminology": "chinese"
  }
}
```

**前置条件**：数据包已通过 `/api/upload-folder` 或 `/api/ingest` 装载。

**调用示例**：

```bash
curl -X POST http://localhost:5000/api/tools/auto_configure \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "external_aero",
    "phenomena": ["shock_wave","flow_separation"],
    "purpose": "design_validation",
    "enable_org_kb": false
  }'
```

---

### 6.2 `generate_next_slot` — 生成下一个槽位

**用途**：生成下一个 `pending` 状态的槽位内容。每次只生成一个，便于前端动画或进度展示。

**参数**：无。

**返回示例**：

```json
{
  "success": true,
  "action": "generate_next_slot",
  "message": "已生成「几何结构描述」槽位内容。",
  "slot_id": "geometry_description",
  "slot_name": "几何结构描述",
  "all_done": false,
  "remaining": 11,
  "progress": {"total": 13, "pending": 11, "draft": 2, "accepted": 0, "progress": 0.15}
}
```

**循环调用模式**：

```python
while True:
    resp = call_tool("generate_next_slot", {})
    data = json.loads(resp["result"])
    if data.get("all_done"):
        break
    # 可选：展示 data["slot_name"] 为进度提示
```

**前置条件**：Draft 已创建（先走 `auto_configure`）。

---

### 6.3 `generate_all_slots` — 批量生成全部槽位

**用途**：一次性把所有 `pending` 槽位生成完。适合不需要细粒度进度的集成方。

**参数**：无。

**返回示例**：

```json
{
  "success": true,
  "action": "generate_all_slots",
  "message": "已成功生成13个槽位内容！所有内容为draft状态，等待确认。",
  "generated": 13,
  "progress": {"total": 13, "pending": 0, "draft": 13, "accepted": 0, "progress": 0.0}
}
```

> 所有生成的槽位统一为 `draft` 状态，**尚未被接受**，后续需调用 `accept_all_slots`。

---

### 6.4 `accept_all_slots` — 批量确认

**用途**：把所有 `draft` 状态的槽位标记为 `accepted`。只有全部 accepted 后才能导出。

**参数**：无。

**返回示例**：

```json
{
  "success": true,
  "action": "accept_all_slots",
  "message": "已确认13个槽位。",
  "accepted_count": 13,
  "progress": {"total": 13, "pending": 0, "draft": 0, "accepted": 13, "progress": 1.0}
}
```

> 在需要人工审核的场景下，调用方应跳过本工具，走前端 UI 的"确认/拒绝/编辑/重写"流程。

---

### 6.5 `export_report` — 导出报告

**用途**：把已 accepted 的报告导出为 Markdown + Word 文件。

**参数**：无。

**返回示例**：

```json
{
  "success": true,
  "action": "export_report",
  "message": "报告已导出",
  "files": {
    "markdown": "/api/download/md",
    "word": "/api/download/docx"
  }
}
```

**下载**：返回的 URL 直接通过 `GET` + 鉴权头下载即可：

```bash
curl -O -J \
  -H "Authorization: ApiKey sr_xxx" \
  http://localhost:5000/api/download/docx
```

**前置条件**：所有槽位必须是 `accepted` 状态。

---

## 7. 工具链编排案例

### 7.1 一键生成报告（7 步工具链）

这是 integration_demo 在 `/api/workflow/auto-generate-stream` 里串联的标准链路：

```
┌─────────────────┐
│ ① get_run_info  │  确认数据包已装载
└────────┬────────┘
         ▼
┌─────────────────┐
│ ② list_signals  │  列出所有变量（可选预查）
└────────┬────────┘
         ▼
┌───────────────────────┐
│ ③ get_derived_quantities │  拿到马赫数估算等推断量
└────────┬──────────────┘
         ▼
┌─────────────────┐
│ ④ auto_configure│  一次性配置并创建 Draft
└────────┬────────┘
         ▼
┌─────────────────┐
│ ⑤ generate_all_slots │  批量生成（也可换成循环 generate_next_slot）
└────────┬────────┘
         ▼
┌─────────────────┐
│ ⑥ accept_all_slots   │  自动确认（若跳过 = 由人审核）
└────────┬────────┘
         ▼
┌─────────────────┐
│ ⑦ export_report │  导出 md + docx
└─────────────────┘
```

### 7.2 Python 完整示例

```python
import json
import requests

BASE = "http://localhost:5000"
HEADERS = {"Authorization": "ApiKey sr_xxx", "Content-Type": "application/json"}

def call(name, args=None):
    r = requests.post(f"{BASE}/mcp/tools/call",
                      headers=HEADERS,
                      json={"name": name, "arguments": args or {}})
    r.raise_for_status()
    return json.loads(r.json()["result"])

# 0) 先上传数据包（非 MCP，走 REST）
requests.post(f"{BASE}/api/upload-folder", headers=HEADERS,
              json={"path": "E:/data/plot3d_case01"})

# 1-3) 事实类查询（可选，供日志或 UI 展示）
print("数据包:", call("get_run_info"))
print("变量数:", call("list_signals")["total"])
print("派生量:", call("get_derived_quantities"))

# 4) 配置并创建 Draft
call("auto_configure", {
    "domain": "external_aero",
    "phenomena": ["shock_wave", "flow_separation"],
    "enable_org_kb": False
})

# 5) 批量生成
result = call("generate_all_slots")
print(f"已生成 {result['generated']} 个槽位")

# 6) 自动接受（或跳过让人审核）
call("accept_all_slots")

# 7) 导出
out = call("export_report")
print("Markdown 下载:", BASE + out["files"]["markdown"])
print("Word 下载:", BASE + out["files"]["word"])
```

### 7.3 宿主软件 + AI 大模型的混合编排

`/api/mcp-chat-stream` 是系统对外的 **SSE 流式 AI 对话端点**。调用方传入对话历史，后端会：

1. 把当前注册的 MCP 工具清单以 function calling 形式喂给大模型
2. 大模型自主判断要调用哪些工具、参数是什么
3. 后端执行工具、回写结果、继续让模型综合
4. 最后流式返回自然语言回答

典型用法（宿主软件把它当成"带工具能力的聊天对话"）：

```bash
curl -N -X POST http://localhost:5000/api/mcp-chat-stream \
  -H "Authorization: ApiKey sr_xxx" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [
      {"role": "user", "content": "帮我分析当前数据包的流场特征，重点看激波区域"}
    ],
    "webSearchEnabled": false
  }'
```

SSE 事件类型：

| `event` | 含义 |
|---------|------|
| `tool_call` | 模型正在调用某个 MCP 工具（含 name、arguments） |
| `delta` | 流式文本内容（逐字输出） |
| `done` | 回复完成，含完整 `tool_calls` 列表 |
| `error` | 发生错误 |

---

## 8. 可观测性

每次 MCP 工具调用都会被记录到**工具观察日志**，支持按工具名、时间、成功/失败查询。

### 8.1 调用统计

```bash
curl http://localhost:5000/api/mcp/analytics \
  -H "Authorization: ApiKey sr_xxx"
```

**返回示例**：

```json
{
  "total_calls": 245,
  "success_rate": 0.976,
  "avg_duration_ms": 284.5,
  "tools": {
    "get_run_info": {"count": 38, "avg_duration_ms": 12.3, "errors": 0},
    "rag_query": {"count": 72, "avg_duration_ms": 456.7, "errors": 1},
    "generate_all_slots": {"count": 12, "avg_duration_ms": 3200.1, "errors": 0}
  },
  "by_category": {"data": 115, "knowledge": 85, "workflow": 45}
}
```

### 8.2 最近调用日志

```bash
curl "http://localhost:5000/api/mcp/logs?limit=20" \
  -H "Authorization: ApiKey sr_xxx"
```

**返回示例**（节选）：

```json
{
  "logs": [
    {
      "id": 1249,
      "timestamp": "2026-04-19T12:34:56",
      "tool_name": "rag_query",
      "category": "knowledge",
      "arguments": {"query": "...", "top_k": 5},
      "success": true,
      "duration_ms": 412,
      "user_id": 7
    }
  ]
}
```

---

## 9. 扩展指南

### 9.1 如何新增一个工具

MCP 工具系统采用**装饰器注册**，新增工具不需要改前端、不需要改分发逻辑。

**步骤**：

```python
from reportgen.mcp import mcp_registry

@mcp_registry.tool(
    name="my_custom_tool",
    description="自定义工具：做某件具体的事",
    schema={
        "type": "object",
        "properties": {
            "input_arg": {"type": "string", "description": "输入参数"}
        },
        "required": ["input_arg"]
    },
    category="custom"
)
def my_custom_tool(context, input_arg: str):
    # 实现逻辑
    return {"success": True, "echo": input_arg}
```

注册后，工具会**自动**出现在：

- `/mcp/tools/list` 返回值里
- AI 对话 function calling 可用清单里
- `/api/mcp/analytics` 统计维度里
- 可观测性日志里

### 9.2 资源扩展

如果要暴露**只读快照**而非"可调用的函数"（比如当前 Draft 的 JSON 结构、变更日志等），可以用 MCP Resource 机制：

```
GET /mcp/resources/list
GET /mcp/resources/read?uri=simureport://draft/current
```

资源和工具的区别：

| | 工具（Tool） | 资源（Resource） |
|---|---------|-----------|
| 目的 | 触发动作（可能改状态） | 暴露只读数据 |
| 调用语义 | RPC | URI 取值 |
| 典型用例 | 生成槽位、计算统计 | 查当前 Draft、查数据包清单 |

---

## 附录 A：工具前置条件速查表

| 工具 | 前置条件 | 违反时返回 |
|------|---------|-----------|
| data 类（5 个） | 已上传数据包 | `{"error":"未加载数据包"}` |
| `rag_query` | 三层知识库至少有一条有效索引 | `{"chunks":[],"note":"未检索到相关知识"}` |
| `web_search` | `TAVILY_API_KEY` 已配置 | `{"error":"联网搜索失败: ..."}` |
| `auto_configure` | 已上传数据包 | `{"error":"未加载数据包"}` |
| `generate_next_slot` / `generate_all_slots` | Draft 已创建 | `{"error":"未创建Draft，请先调用auto_configure"}` |
| `accept_all_slots` | Draft 已创建 | `{"error":"未创建Draft"}` |
| `export_report` | 全部槽位 accepted | `{"error":"存在未确认的槽位"}`（或类似） |

---

## 附录 B：命名与 ID 约定

- **工具名**：小写 + 下划线，英文动词开头（`get_*` / `list_*` / `compute_*` / `generate_*` / `accept_*` / `export_*`）
- **槽位 ID**：`analysis_purpose_1/2`、`geometry_description`、`mesh_description`、`variable_<name>`、`evaluation_criteria_1/2`、`conclusion`
- **数据包路径**：Windows / POSIX 绝对路径均可，上传接口会统一规范化
- **Api Key 前缀**：`sr_` 固定

---

*文档结束。如有疑问或建议，请联系项目维护者。*
