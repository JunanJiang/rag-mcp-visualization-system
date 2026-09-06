---
id: plot3d-bg2-011
title: 等熵效率（Isentropic Efficiency）用一句人话怎么解释
type: background_card
tags: [efficiency, isentropic-efficiency, turbomachinery]
report_modules: [性能指标]
confidence: high
sources:
  - https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/cfx_mod/CDDBDFHF.html
  - https://www.sciencedirect.com/topics/engineering/isentropic-efficiency
---

## 核心概念（不讲推导）
- **等熵效率**把真实设备和“理想、没有损失的设备”做对比。

## 直觉理解
- 对 **压气机**：理想情况下需要的功越接近实际需要的功，效率越高。
- 对 **涡轮**：理想情况下本应能输出的功，真实能输出得越接近，效率越高。

## 为什么它有用
- 它把“损失”整体折算成一个易比较的数，用于对比不同方案/工况。
## 补充：等熵效率在报告里最常见的两条公式（选读）
> 仍以理想气体、常 γ 为例，只用于帮助你理解“为什么要用总量”。

- **压气机（常见 total-to-total 定义）**
  - 理想温升：Tt2s/Tt1 = PR^((γ-1)/γ)
  - η_c ≈ (Tt2s - Tt1) / (Tt2 - Tt1)
- **涡轮（常见 total-to-total 定义）**
  - η_t ≈ (Tt1 - Tt2) / (Tt1 - Tt2s)

## 常见坑
- 用了不同的“口径”（tt vs ts），或者入口/出口截面选得不一致，会让效率出现“看似离谱”的数值。
- 当存在显著冷却流/泄漏流/混合时，简单等熵效率会失真，需要更完整的功与焓流核算。
