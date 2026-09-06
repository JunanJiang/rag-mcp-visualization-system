---
id: plot3d-bg2-010
title: 压比（Pressure Ratio）的直觉理解：它告诉你机器把压力抬高/降低了多少
type: background_card
tags: [turbomachinery, performance, pressure-ratio]
report_modules: [性能指标]
confidence: medium
sources:
  - https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/cfx_mod/CDDBDFHF.html
---

## 核心概念
- **压气机**：把压力“抬高”，压比通常 > 1。
- **涡轮**：把压力“释放”来做功，压比（按入口/出口定义方式不同）通常体现压力下降。

## 为什么压比常用总压
- 在可压缩流里，总压更能反映“可用能量”与损失，因此很多性能评估用“总压比”。
## 补充：压比其实有好几种“口径”
- **总压比（total-to-total）**：PR_tt = Pt_out / Pt_in（压气机/风扇性能最常用）
- **总-静压比（total-to-static）**：PR_ts = Pt_out / Ps_in 或 Ps_out / Pt_in（取决于行业习惯）
- **静压比（static-to-static）**：更接近管路系统，但在可压缩/高损失场景里解释力弱一些。

## 为什么你需要在报告里写清楚口径
- 不同口径得到的数值差别可能很大；如果不写清楚，“压比对不上”往往只是定义不同，不是算错。

## 一个实用提醒
- 压比最好配合 **同一截面的平均方式**（面积平均/质量平均）一起报，否则 PR 的可比性会受截面非均匀性影响。
