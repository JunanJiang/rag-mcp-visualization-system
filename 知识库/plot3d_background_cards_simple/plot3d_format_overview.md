---
id: plot3d-format-overview
title: Plot3D数据格式概述
tags: [Plot3D, 数据格式, 多块网格, 文件结构]
report_modules: [grid_description, analysis_purpose]
confidence: high
sources: ["NASA Ames Research Center Plot3D Manual", "Walatka P.P. PLOT3D User's Manual"]
---

# Plot3D数据格式概述

Plot3D是NASA Ames研究中心开发的CFD标准数据格式，广泛用于结构化网格的存储和可视化。

## 文件组成

| 文件类型 | 扩展名 | 内容 | 必要性 |
|---------|--------|------|--------|
| 网格文件 | .xyz / .x | 网格节点坐标 (x, y, z) | 必需 |
| 解文件 | .q | 流场守恒量 (ρ, ρu, ρv, ρw, ρE) | 必需 |
| 函数文件 | .f | 用户自定义变量 | 可选 |
| 名称文件 | .nam | 变量名映射 | 可选 |

## 多块结构

Plot3D支持多块（multi-block）结构化网格：

```
文件头: NBLOCKS (块数)
每个块: NI, NJ, NK (三个方向的网格点数)
数据排列: Fortran列优先顺序 (i变化最快)
```

## 数据包目录结构（本系统约定）

```
data_package/
├── manifest.json      # 元信息（来流条件、参考值等）
├── variables.json     # 变量列表和数值范围
├── datasets.json      # 网格块维度和拓扑信息
└── README.md          # 可选说明文件
```

## 关键元信息字段

- **freestream_mach**: 来流马赫数
- **reynolds_number**: 雷诺数
- **angle_of_attack**: 攻角（度）
- **reference_area**: 参考面积
- **reference_length**: 参考长度
- **gamma**: 比热比（默认1.4）

这些参数对于物理量的量纲化和工程解读至关重要。
