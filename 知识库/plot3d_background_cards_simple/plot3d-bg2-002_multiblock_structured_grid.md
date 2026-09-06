---
id: plot3d-bg2-002
title: 多块结构网格（Multi-block Structured Grid）是什么
type: background_card
tags: [mesh, structured-grid, multiblock]
report_modules: [网格]
confidence: high
sources:
  - https://www.grc.nasa.gov/www/wind/valid/plot3d.html
---

## 核心概念
- **结构网格**：每个网格点可以用 (i, j, k) 规则索引排列。
- **多块结构网格**：把复杂几何拆成多个“规整的块（block）”，每块内部是规则结构网格，块与块拼起来覆盖整体几何。

## 为什么工程里常用
- 结构网格在近壁边界层、叶片表面等区域更容易做“可控加密”。
- 多块能兼顾：贴合复杂几何 + 保持结构网格质量。

## 常见注意点
- **块缝（block interface）**附近的插值/拼接处理可能影响梯度类量（如涡量、Q-criterion 等）。
## 补充：多块“拼起来”到底拼的是什么
- 每个 block 都是一个规则的 (i,j,k) 网格立方体；块与块之间通过**界面（interface）**连接。
- 工程里常见两类界面：
  - **1-to-1（点对点匹配）**：两侧网格在界面处点数与分布一致，后处理/插值更干净。
  - **patched / non-matching**：两侧不完全匹配，需要插值，界面附近的梯度、涡量、涡识别更容易出现“假结构”。

## 为什么“块缝”对涡结构尤其敏感
- 涡识别、涡量、Q/Lambda2 都依赖速度梯度（二阶信息）；而块缝附近常出现：
  - 变量插值造成的局部平滑/噪声
  - 网格正交性变差导致的梯度误差
- 实操建议：
  - 先用 **Pressure/Velocity** 这类一阶量看趋势，再看涡识别。
  - 对块缝附近的涡结构，用“多阈值对比 + 多方法交叉验证”（例如 Lambda2 与 Q-criterion）更稳。

## 快速检查清单
- 每个 block 的 (ni,nj,nk) 是否合理（有没有异常小/异常大的块）
- block interface 处等值线是否出现不连续“折痕”（可能是拼接/插值伪影）
- 是否存在周期边界（涡轮机械叶道里很常见）：周期面附近的可视化要注意镜像与相位
