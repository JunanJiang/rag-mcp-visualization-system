---
id: plot3d-bg2-005
title: 为什么会看到 Velocity/Pressure/Mach：它们常是由 Q 变量派生出来的
type: background_card
tags: [vtk, paraview, plot3d-reader, derived-quantities]
report_modules: [变量, 后处理]
confidence: high
sources:
  - https://vtk.org/doc/release/4.0/html/classvtkPLOT3DReader.html
---

## 核心概念
- VTK 的 PLOT3D Reader（vtkPLOT3DReader）除了读取 Q 变量，还能**生成额外的标量/向量（functions）**。
- 这类派生量通常包括：速度（Velocity）、压力（Pressure）、马赫数（Mach）等。

## 你需要记住的事实
- 当你在数据里看到 `VelocityVector` 之类字段时，它很可能不是“原始输出字段名”，而是工具基于 Q 变量计算得到的。
## 补充：VTK/ParaView 里“Functions”的真实含义
- `vtkPLOT3DReader` 读取到的基础量通常是：密度（scalar）、动量（vector）、能量（scalar）。
- 在此基础上，它能生成一系列派生函数（functions），例如：
  - **Velocity**（由动量/密度换算）
  - **Pressure / Temperature / Mach**（依赖 γ 与气体常数 R 等设置）
  - 以及一些与涡量、梯度相关的量（不同版本支持略有差异）

## 实操提示：派生量“算错”的三大来源
1. **γ（比热比）设置不对**：例如空气常用 1.4，但高温/多组分并不恒定。
2. **无量纲化没还原**：你以为是 Pa，其实是 p/p_ref。
3. **旋转参考系/相对速度**：涡轮机械里速度可能是绝对/相对两套，导入链路不同会导致你看到的 VelocityVector 不一致。

## 快速验证法
- 任选一个点：用 Q 手算一次 u、p，与工具派生结果对比；只要能对上，后面的图就更可信。
