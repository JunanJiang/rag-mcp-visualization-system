---
id: plot3d-q-variables
title: Plot3D Q变量物理含义
tags: [Plot3D, Q变量, 守恒量, 流场变量]
report_modules: [variable_analysis, grid_description]
confidence: high
sources: ["NASA Plot3D User Manual", "Anderson J.D. Computational Fluid Dynamics"]
---

# Plot3D Q变量物理含义

Plot3D格式的Q文件（solution file）存储流场守恒量变量，标准五变量对应关系如下：

| 变量编号 | 守恒量 | 物理含义 | 典型无量纲化 |
|---------|--------|---------|-------------|
| Q1 (F1V1) | ρ | 密度 | ρ/ρ∞ |
| Q2 (F1V2) | ρu | x方向动量 | ρu/(ρ∞a∞) |
| Q3 (F1V3) | ρv | y方向动量 | ρv/(ρ∞a∞) |
| Q4 (F1V4) | ρw | z方向动量 | ρw/(ρ∞a∞) |
| Q5 (F1V5) | ρE | 总能量 | ρE/(ρ∞a∞²) |

## 派生物理量

从五个基本守恒量可以推导出以下关键物理量：

- **速度分量**：u = Q2/Q1, v = Q3/Q1, w = Q4/Q1
- **速度幅值**：V = √(u² + v² + w²)
- **压力**：p = (γ-1)[Q5 - 0.5·Q1·(u² + v² + w²)]，其中γ=1.4（理想气体）
- **温度**：T = γ·Ma²·p/Q1（无量纲形式）
- **马赫数**：Ma_local = V / √(γ·p/Q1)

## 工程解读要点

- 当密度比（Q1max/Q1min）超过10:1时，表明流场存在**强压缩性效应**，通常与激波相关
- 动量变量的符号变化区域通常对应**流动分离区**或**回流区**
- 总能量的局部极值点往往标识**驻点**或**高温区**
