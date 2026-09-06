---
id: plot3d-exp-001
title: 密度（Density）在可压缩流动中通常反映什么
type: background_card
tags: [density, compressible-flow, interpretation]
report_modules: [变量, 结果解读]
slot_intents: [result_explain, variable_semantics]
confidence: medium
---

## 它是什么（通俗版）
密度表示单位体积里“有多少质量的气体”。在可压缩流动里，密度不是常数，会随着压力和温度变化。

## 在仿真结果里常见的解读方式
- **密度变化很小**：通常说明流动近似不可压缩（或马赫数不高）。
- **局部密度突变/梯度很大**：常见于激波、强压缩/强膨胀区，或数值耗散/网格质量问题导致的“假突变”。
- **近壁密度变化**：可能与边界层内温度升高/压力变化有关（需要结合温度/压力等量确认）。

## 需要避免的误解
- 仅凭“颜色深浅”不能断定是哪个部件造成；需要结合几何图、切片位置和流向一起看。
- 如果数据单位/无量纲方式未知，只能做“相对变化”描述，不要强行写绝对工程结论。
