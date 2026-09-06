---
id: plot3d-bg2-016
title: 涡结构识别（以 Lambda2 为例）：为什么它只是“识别工具”而不是唯一答案
type: background_card
tags: [vortex, lambda2, vortex-identification]
report_modules: [结果解读]
confidence: high
sources:
  - https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/abs/on-the-identification-of-a-vortex/D26006DDB95FB28DA80E28A581182DF1
---

## 核心概念
- 涡结构识别的目标是把“旋转主导的区域”从一般剪切/拉伸里区分出来。
- Lambda2 是经典方法之一，常用来更稳定地定位“涡核附近区域”。

## 你需要记住的事实
- **不存在唯一正确的涡定义**：不同方法会给出不同的“涡形状”。
- 阈值选择会强烈影响结果，因此解释涡结构时，应更关注“相对位置、变化趋势”，而不是某一张图的绝对形状。
## 补充：Lambda2 到底在“算”什么（只讲概念）
- 速度梯度 ∇u 可以拆成：
  - **对称部分 S**（应变/拉伸）
  - **反对称部分 Ω**（旋转）
- Jeong & Hussain 的思路是：用 **S² + Ω²** 的特征值来判断局部是否存在“旋转主导的压力极小结构”，并提出用第二大特征值 λ₂ 作为判据（常用阈值是 λ₂ < 0）。

## 为什么 Lambda2 会“看起来更干净”
- 相比直接看压力极小或涡量幅值，它对纯剪切层更不敏感，因而更容易把“剪切”与“涡核”区分开。

## 但它依然不是万能
- **近壁区域**：壁面剪切很强，涡识别很容易把边界层结构也当成“涡”。
- **阈值依赖**：建议用“同一工况多阈值、不同工况固定阈值”两种方式都看一遍，分别用于理解形态与做对比。
