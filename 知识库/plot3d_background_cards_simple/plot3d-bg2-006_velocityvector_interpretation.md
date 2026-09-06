---
id: plot3d-bg2-006
title: VelocityVector 一般代表什么（以及为什么要关注它的来源）
type: background_card
tags: [velocity, vector-field, derived-quantities]
report_modules: [变量, 后处理]
confidence: medium
sources:
  - https://vtk.org/doc/release/4.0/html/classvtkPLOT3DReader.html
---

## 核心概念
- 速度向量是流动“方向与快慢”的最直观表达。
- 在 PLOT3D 的典型链路里，速度经常是**由密度与动量换算**得到的。

## 为什么要关注“它是不是派生量”
- 如果速度是派生量：你需要确认它使用了哪些假设（比如气体常数、比热比、是否无量纲化）。
- 如果速度是原始量：通常变量名/单位会更明确，且不会需要额外换算。
## 补充：在叶轮/叶道问题里，“速度”可能有两套
- **绝对速度（Absolute velocity）**：在惯性系里观察到的速度。
- **相对速度（Relative velocity）**：在随转系里观察到的速度（与绝对速度相差一个“刚体旋转速度”项）。

为什么这重要：
- 你用速度做流线、入射角、马赫数时，绝对/相对会给出不同结论。
- 如果后处理中同时出现“旋涡看起来很强但压比/效率趋势不匹配”，要怀疑自己是不是用错了速度定义。

## 快速排查：你手里的 VelocityVector 更像哪一种
- 在转子区域，如果 VelocityVector 在半径方向上呈现明显的“固体旋转”趋势（切向速度随半径线性变化），它更可能是绝对速度。
- 如果你知道转速 ω，可以用 **V_rel ≈ V_abs − ω×r** 做一个数量级检查：差值是否合理。
