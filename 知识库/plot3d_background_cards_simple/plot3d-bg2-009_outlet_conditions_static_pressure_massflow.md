---
id: plot3d-bg2-009
title: 出口工况常见设定：出口静压与质量流量（为什么二者常只选其一）
type: background_card
tags: [boundary-condition, outlet, static-pressure, mass-flow]
report_modules: [工况]
confidence: medium
sources:
  - https://www.simscale.com/docs/simulation-setup/boundary-conditions/pressure-inlet-and-pressure-outlet/
---

## 常见出口设定
- **指定出口静压**：相当于给定“反压”，流量由流场自己决定。
- **指定质量流量**：相当于强制“通过多少流”，压力由流场自己决定。

## 为什么经常只选其一
- 两者都强行固定，容易让问题过约束（尤其在可压缩流里），导致数值不稳定或不物理。

## 直觉理解
- 出口静压像“你在下游接了一个多大阻力的管路”。
- 质量流量像“你强行规定必须过这么多气”。
## 补充：可压缩流里“指定静压”为什么常见
- 在很多工程场景，下游系统（管路/燃烧室/喷管）更像是给你一个**反压**，因此用 pressure outlet 更贴合物理直觉。
- 但要注意：当流动**堵塞（choked）**时，质量流量可能几乎不再受出口静压影响——这时你会看到“调反压但流量不怎么变”。

## 数值层面的两个风险点
- **回流（backflow）**：出口附近若出现回流，很多求解器需要你同时指定回流的温度/湍流量等，否则会不稳定。
- **过约束**：即使你只指定了一个量（静压或质量流量），入口端如果也用了强约束（例如固定速度+固定总压），也可能等价于过约束。

（SimScale 的边界条件说明里也强调了 pressure outlet / mass flow outlet 的不同“控制逻辑”。）
