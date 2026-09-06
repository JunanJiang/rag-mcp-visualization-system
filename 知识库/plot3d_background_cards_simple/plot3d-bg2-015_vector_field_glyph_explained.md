---
id: plot3d-bg2-015
title: 矢量场（Glyph）怎么读：方向表示流向，长度/颜色表示强度
type: background_card
tags: [postprocess, vector-field, glyph]
report_modules: [后处理]
confidence: medium
sources:
  - https://vtk.org/doc/release/4.0/html/classvtkPLOT3DReader.html
---

## 核心概念
- 矢量可视化常用“箭头/短线”表达：
  - 朝向 = 方向
  - 长度或颜色 = 大小

## 常见经验
- 太密会“糊成一片”，通常需要抽样（sampling）或限制显示区域。
- 和流线搭配时：
  - 流线负责看整体路径
  - 矢量负责看局部方向变化
## 补充：Glyph 最常见的三种“误读”
1. **把箭头长度当成真实大小**：很多时候你开了“Normalize”，箭头都一样长。
2. **采样不均**：Glyph 默认可能按点/单元顺序抽样，导致某些区域看起来“更密更重要”。
3. **坐标缩放影响直觉**：如果几何在某一方向被缩放（例如单位转换或非等比例显示），箭头方向会被视觉误导。

## 实操建议
- 用 `Glyph` 前先 `Mask Points`（抽样），控制密度。
- 明确选择：
  - Orientation Array（用哪个矢量决定方向）
  - Scale Array（用哪个标量决定长度）
- 若要对比不同截面/不同工况，尽量固定同一套显示参数（尤其是 scale factor）。
