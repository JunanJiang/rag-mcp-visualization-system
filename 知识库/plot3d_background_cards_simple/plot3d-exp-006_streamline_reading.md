---
id: plot3d-exp-006
title: 流线（Streamline）图应该怎么解释才不误导
type: background_card
tags: [streamline, postprocess, interpretation]
report_modules: [后处理, 结果解读]
slot_intents: [postprocess_explain, result_explain]
confidence: high
---

## 它能说明什么
流线用来展示速度场的“流动路径感”，适合观察主流走向、是否存在明显回流/偏转/旋转结构。

## 三个关键影响因素（描述时建议点明）
- **种子点分布**：种子放在哪，流线就主要显示哪的流动。
- **积分设置**：步长、最大步数、终止条件会影响流线长度与是否断裂。
- **局部插值误差**：在网格拼接或近壁复杂区域，流线可能出现不连续或不稳定形态。

## 推荐表述
如果缺少明确的入口/出口定义，建议写“流线显示主流大体沿某方向通过通道，局部存在偏转/回流迹象（需结合更多量确认）”。
