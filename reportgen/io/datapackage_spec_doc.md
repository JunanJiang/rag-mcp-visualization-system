# SimuVision DataPackage Spec v1.0

> 仿真数据包标准格式规范 — 定义报告生成引擎接受的文件级数据包结构。

---

## 概述

DataPackage 是一个**文件夹**（或 ZIP 压缩包），包含仿真数据的 JSON 元信息和可视化截图。报告生成引擎通过解析数据包自动提取事实、构建分析报告。

任何仿真平台只需按本规范组织数据包，即可被系统自动识别和解析。

---

## 版本

- **当前版本**：`1.0`
- **兼容性**：缺少 `spec_version` 字段的数据包视为 `0.9-legacy`，系统会尝试兼容解析并发出警告。

---

## 目录结构

```
<package_root>/
├── manifest.json            ★ 必须 — 入口清单
├── variables.json           ★ 必须 — 变量列表
├── datasets.json            推荐 — 网格块详情
├── hierarchy.json           可选 — 数据层次结构
├── images/                  可选 — 可视化截图
│   ├── geometry/            几何结构概览图（PNG）
│   ├── mesh/                网格结构概览图（PNG）
│   └── variables/           变量云图（PNG）
├── automation/              可选 — 后处理操作记录
│   └── ops/
│       └── <operation_name>/
│           ├── context.json     操作上下文（变量、参数）
│           ├── result.json      操作结果（成功/失败、图片列表）
│           └── images/          操作截图（PNG）
└── views/                   可选 — 视角预设
    └── view_presets.json
```

---

## 文件详细说明

### `manifest.json`（必须）

数据包的入口文件，声明规范版本、数据集元信息和文件引用。

```json
{
  "spec_version": "1.0",
  "app": {
    "name": "SimuVision-Desktop",
    "version": "1.0.0"
  },
  "createdAt": "2026-01-19T11:22:14",
  "sessionId": "session_20260119_112214_plot3d",
  "dataset": {
    "datasetName": "plot3d",
    "datasetType": "Plot3DMultiBlock",
    "blockCount": 11,
    "totalPoints": 1002672,
    "totalCells": 922816
  },
  "exports": {
    "datasets": "datasets.json",
    "variables": "variables.json",
    "hierarchy": "hierarchy.json",
    "images": ["images/geometry/overview.png", "images/mesh/overview.png"],
    "viewPresets": "views/view_presets.json"
  },
  "sourceFiles": {
    "gridFile": "path/to/plot3d.g"
  }
}
```

**字段说明：**

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `spec_version` | string | 推荐 | 规范版本号，当前为 `"1.0"` |
| `app.name` | string | 否 | 导出应用名称 |
| `app.version` | string | 否 | 导出应用版本 |
| `createdAt` | string | 否 | ISO 8601 时间戳 |
| `dataset.datasetType` | string | **是** | 数据集类型，见下表 |
| `dataset.datasetName` | string | 否 | 数据集名称 |
| `dataset.blockCount` | int/string | 否 | 网格块数量 |
| `dataset.totalPoints` | int | 否 | 总网格点数 |
| `dataset.totalCells` | int | 否 | 总网格单元数 |
| `exports` | object | 否 | 引用其他 JSON 文件的相对路径 |

**支持的 `datasetType` 值：**

| 值 | 说明 |
|----|------|
| `Plot3DMultiBlock` | Plot3D 多块结构网格 |
| `Plot3DSingleBlock` | Plot3D 单块结构网格 |
| `VTKUnstructured` | VTK 非结构网格 |
| `OpenFOAM` | OpenFOAM 格式 |
| `FluentCase` | ANSYS Fluent 格式 |
| `Custom` | 自定义格式 |

---

### `variables.json`（必须）

流场变量列表，至少包含一个变量。

```json
{
  "variables": [
    {
      "name": "F1V1",
      "guess_variableName": "density",
      "components": 1,
      "location": "PointData",
      "rangeGlobal": { "min": 0.128, "max": 3.007 }
    },
    {
      "name": "F1V2",
      "guess_variableName": "MomentumX",
      "components": 1,
      "location": "PointData",
      "rangeGlobal": { "min": -314.46, "max": 869.04 }
    }
  ]
}
```

**字段说明：**

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `name` | string | **是** | 变量原始名称 |
| `guess_variableName` | string | 推荐 | 语义推测名称（如 density, MomentumX） |
| `components` | int | 否 | 分量数（标量=1，矢量=3），默认 1 |
| `location` | string | 否 | 数据位置：`PointData` 或 `CellData` |
| `rangeGlobal.min` | number | 推荐 | 全局最小值 |
| `rangeGlobal.max` | number | 推荐 | 全局最大值 |

---

### `datasets.json`（推荐）

网格块详情，包含每个块的空间范围、维度和拓扑信息。

```json
{
  "datasets": [
    {
      "blockIndex": 0,
      "name": "Block_1",
      "datasetId": "block_0000",
      "type": "vtkStructuredGrid",
      "topology": {
        "dims": { "values": [216, 24, 72] },
        "points": 373248,
        "cells": 351095
      },
      "bounds": {
        "values": [-0.5, 1.5, -0.2, 0.2, -0.3, 0.3]
      }
    }
  ]
}
```

---

### `automation/ops/<op>/context.json`

后处理操作的上下文信息。

```json
{
  "operation_type": "contourLine",
  "parameters": {
    "variable_name": "F1V1",
    "num_contours": 20,
    "color_map": "jet"
  }
}
```

### `automation/ops/<op>/result.json`

操作执行结果。

```json
{
  "success": true,
  "image_files": ["screenshot_001.png"],
  "timestamp": "2026-01-19T11:30:00"
}
```

---

## 验证

系统提供两种验证方式：

### 1. API 验证

```
POST /api/data-package/validate
```

上传数据包后调用，返回合规性检查结果：

```json
{
  "is_valid": true,
  "spec_version": "1.0",
  "errors": [],
  "warnings": [
    "manifest.json 未声明 spec_version，建议添加 \"spec_version\": \"1.0\""
  ]
}
```

### 2. Python 验证

```python
from reportgen.io.datapackage_spec import validate_data_package
from pathlib import Path

is_valid, errors, warnings = validate_data_package(Path("./数据包"))
print(f"合规: {is_valid}")
for e in errors:
    print(f"  ❌ {e}")
for w in warnings:
    print(f"  ⚠️ {w}")
```

---

## 扩展指南

### 添加新的数据集类型

1. 在 `manifest.json` 的 `dataset.datasetType` 中使用 `Custom` 或新增枚举值
2. 在 `reportgen/io/adapters/` 下实现新适配器（继承 `DataPackageAdapter`）
3. 在 `reportgen/io/adapters/__init__.py` 的 `ADAPTER_REGISTRY` 中注册

### 添加自定义元数据

在 `manifest.json` 中可自由添加任何额外字段，系统会忽略未识别的字段（向前兼容）。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-02 | 初始正式版本：定义核心文件结构、JSON Schema、验证机制 |
| 0.9-legacy | - | 隐式版本，无 spec_version 字段的旧数据包 |
