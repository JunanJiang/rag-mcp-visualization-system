---
id: plot3d-bg2-014
title: 流线（Streamline/StreamTracer）怎么理解：它显示的是“速度场的路径”
type: background_card
tags: [postprocess, streamline, streamtracer]
report_modules: [后处理]
confidence: high
sources:
  - https://www.paraview.org/paraview-docs/v5.12.0/python/paraview.simple.StreamTracerForGenericDatasets.html
---

## 核心概念
- 流线是把“如果放一个无质量示踪点，它会沿速度方向怎么走”画出来。
- ParaView 的 StreamTracer 会做数值积分（常见用 Runge–Kutta 积分器）。

## 你需要记住的两个关键
- **种子点（seed）**决定你看见什么：种子点不覆盖关键区域，就看不到关键现象。
- **积分步长/误差设置**会影响流线是否平滑、是否提前终止。
## 补充：Streamline vs Pathline（别把“稳态”假设忘了）
- **Streamline（流线）**：针对稳态速度场；同一时刻的速度方向连成的曲线。
- **Pathline（迹线）**：针对非稳态；粒子随时间走过的轨迹。

在 ParaView 里：
- `StreamTracer`/`StreamTracerForGenericDatasets` 用于稳态积分，并提供多种 Runge–Kutta 积分器与步长/误差控制。
- 如果你有时间序列想看“随时间走”，通常应使用 `ParticleTracer`（不同版本名称略有差异）。

## 更实用的调参顺序
1. 先把 seed 放对（覆盖你关心的入射/尾迹/端壁区域）
2. 再调最大积分长度/时间，确保流线能走到你想看的区域
3. 最后再调步长与误差，让曲线更平滑、更少“提前终止”
