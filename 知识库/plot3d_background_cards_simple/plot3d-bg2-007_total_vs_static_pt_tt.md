---
id: plot3d-bg2-007
title: 总压/总温（Pt/Tt）与静压/静温的区别（可读版）
type: background_card
tags: [compressible-flow, total-pressure, total-temperature]
report_modules: [工况]
confidence: high
sources:
  - https://www.grc.nasa.gov/www/k-12/airplane/isentrop.html
---

## 静压/静温（Static）
- 可以理解为：你“跟着气流一起移动”时，在那个局部位置测到的压力/温度。

## 总压/总温（Total / Stagnation）
- 可以理解为：把气流**尽量不额外损失**地慢慢减速到静止时，它对应的压力/温度水平。

## 为什么工程里爱用总量
- 总压/总温更能代表“流动携带的能量水平”，因此入口工况、损失评估、效率定义里经常出现。
## 补充：理想气体/等熵关系下的“快速公式”（方便做 sanity check）
> 只用来做数量级核对，不建议在卡片里背推导。

- Tt = T * (1 + (γ-1)/2 * M²)
- Pt = P * (Tt/T)^(γ/(γ-1))

它解释了两个直觉：
- **马赫数越大，总温越高**（因为把更多动能“刹车”成内能）。
- **总压对损失更敏感**：同样的静压变化，若伴随不可逆损失，总压会掉得更明显。

NASA 的科普页面对“等熵/停滞量”也采用了这种解释路径。

## 常见误区
- 把“总压”当成“静压加一个动压”在可压缩流里直接相加（这只在低马赫、近似不可压时才勉强成立）。
