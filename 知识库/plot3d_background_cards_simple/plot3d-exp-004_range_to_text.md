---
id: plot3d-exp-004
title: 如何把 min/max 这种统计量写成用户能读懂的描述
type: background_card
tags: [statistics, interpretation, reporting]
report_modules: [结果解读]
slot_intents: [result_explain]
confidence: high
---

## 推荐表达结构（不需要公式）
当你只有范围（min/max）与一张分布图时，建议用三句话：
1) **这是什么量**：用一句话解释变量代表的物理意义。
2) **数值跨度**：说明范围，并强调“单位/无量纲未知时只做相对解读”。
3) **分布现象**：结合图中“高值集中区/低值集中区/梯度显著区”的位置关系，给出客观描述。

## 不建议的写法
- 直接堆一串变量的 min/max（用户看不出重点）。
- 没有证据就写“性能提升/效率更高”等结论。
