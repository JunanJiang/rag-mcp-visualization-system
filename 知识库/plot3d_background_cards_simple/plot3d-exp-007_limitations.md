---
id: plot3d-exp-007
title: 当数据包缺少工况/单位/边界条件时，结果解读的边界在哪里
type: background_card
tags: [limitations, uncertainty, best-practice]
report_modules: [结果解读]
slot_intents: [result_explain, conclusion]
confidence: high
---

## 常见缺失项
很多可视化数据包只包含网格与若干场变量，不包含：单位体系、无量纲参考量、边界条件口径（总压/总温或静压等）、转速/参考系等。

## 在这种情况下可以做什么
- 可以描述：变量的范围、相对变化、分布趋势、是否存在明显梯度集中区。
- 可以说明：后处理方法展示了哪些现象（例如流线主流方向、局部偏转）。

## 不建议做什么
- 不要直接给“性能指标（效率/压比/推力等）”的数值结论。
- 不要把坐标轴分量强行解释为“轴向/径向/周向”，除非数据包明确说明坐标含义。
