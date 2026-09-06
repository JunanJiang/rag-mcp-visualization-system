---
id: plot3d-bg2-012
title: 为什么要用“质量平均”（mass-averaged）而不是简单面积平均
type: background_card
tags: [postprocess, averaging, mass-averaged]
report_modules: [后处理, 性能指标]
confidence: high
sources:
  - https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/cfx_ref/i1308570.html
  - https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/cfx_mod/CDDBDFHF.html
---

## 面积平均（Area-averaged）
- 每个位置“同等权重”。
- 当截面上速度/密度分布很不均匀时，面积平均可能会被“低流量但面积大”的区域拉偏。

## 质量平均（Mass-averaged）
- 用“局部通过的质量流量”做权重。
- 更符合“谁真正贡献了流量/能量，谁就更该影响平均值”。

## 直觉理解
- 你可以把质量平均理解为：在截面上“流得多的地方说话更有分量”。
## 补充：两种平均的“数学形状”（用来避免概念混淆）
- 面积平均：⟨φ⟩_A = (∫_A φ dA) / A
- 质量平均：⟨φ⟩_m = (∫_A φ · ρ V_n dA) / (∫_A ρ V_n dA)
  - 其中 V_n 是穿过截面的法向速度分量。

Ansys 的文档里也用类似的定义强调：质量平均会让“真正通过截面的流”更有权重。

## 什么时候面积平均也很有用
- 你关心的是“几何表面上的平均压力/热流”而不是通过量（例如叶片表面压力系数平均）。

## 质量平均的一个隐藏细节
- 如果截面存在回流，V_n 可能为负；此时你要明确：
  - 是把回流也算进去（会抵消）
  - 还是只对正向流量做平均（更贴合某些工程定义）
