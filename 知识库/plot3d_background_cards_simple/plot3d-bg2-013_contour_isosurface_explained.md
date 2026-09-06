---
id: plot3d-bg2-013
title: 等值线/等值面（Contour/Isosurface）到底在表达什么
type: background_card
tags: [postprocess, contour, isosurface]
report_modules: [后处理]
confidence: high
sources:
  - https://www.paraview.org/paraview-docs/latest/python/paraview.simple.Contour.html
---

## 核心概念
- **等值线（2D）/等值面（3D）**：把一个标量场里“数值相同”的位置连成线/面。

## 直觉用途
- 用于快速定位：高/低压区、强梯度区、某阈值以上的“强区域”。
- 适合做“现象定位”，但不直接告诉你“因果”。

## 常见误区
- 等值面的形状很依赖阈值选择：阈值变一点，形状可能差很多。
## 补充：等值面“看起来不连续”通常不是物理不连续
- 常见原因是数据在不同块/不同分区之间没有合并，或块边界处插值方式不同。
- 在 ParaView 里可以尝试：
  - 先 `Append Attributes/Merge Blocks` 再做 Contour
  - 或者先 `Cell Data to Point Data`（或反过来）统一数据位置

## 选择阈值的小技巧
- 不要只试一个值：用“低/中/高”三档阈值快速扫一遍，判断结构是否稳定。
- 如果结构随阈值剧烈改变，说明它更像“强度分布的可视化”，而不是一个明确边界的物理实体。

ParaView 官方的 Contour 文档也强调：Contour/Isosurface 的核心就是“给定等值”。
