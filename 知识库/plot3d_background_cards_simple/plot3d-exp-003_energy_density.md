---
id: plot3d-exp-003
title: 总能量密度（EnergyStagnationDensity）在结果里通常意味着什么
type: background_card
tags: [energy, stagnation, interpretation]
report_modules: [变量, 结果解读]
slot_intents: [result_explain, variable_semantics]
confidence: low
---

## 它是什么（通俗版）
“总能量密度”通常与气体的热能和动能都有关，可以粗略理解为“单位体积里包含的总能量”。

## 能从它看出什么
- **高能量区域**：往往对应更高速度或更高温度（具体是哪一个需要其他变量确认）。
- **能量分布变化明显**：可能与压缩/膨胀、混合耗散、近壁加热等过程相关。

## 重要限制
仅凭“总能量密度”很难直接得出工程结论。要判断是“温度导致”还是“速度导致”，通常需要同时看速度模、压力或温度等派生量；如果数据包不包含这些量，就建议只做“分布现象描述 + 不确定性说明”。
