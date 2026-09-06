---
id: plot3d-bg2-004
title: Q 文件里“5 个分量”通常表示什么（密度/动量/能量）
type: background_card
tags: [plot3d, q-file, compressible, conservative-variables]
report_modules: [变量]
confidence: high
sources:
  - https://vtk.org/doc/release/4.0/html/classvtkPLOT3DReader.html
  - https://en.wikipedia.org/wiki/Plot3d_file_format
---

## 最常见的约定（可压缩流）
很多 PLOT3D 的 Solution/Q 文件，5 个分量常按“保守量”顺序存储：
- ρ：密度
- ρu、ρv、ρw：三个方向的动量
- ρE：能量相关量（常见写法是总能量密度）

## 直觉理解
- 这些量适合数值求解（守恒形式），但不如“速度/压力/温度”直观。
- 因此很多后处理工具会基于这 5 个量再计算更直观的工程量。
## 补充：从保守量到“工程量”的最常用换算
> 下面以理想气体/常 γ 为最常见情形举例（很多工具默认就是这个假设）。

- 速度：
  - u = (ρu)/ρ，v = (ρv)/ρ，w = (ρw)/ρ
- 动能项：0.5 * ρ * (u²+v²+w²)
- 压力（常见写法）：p = (γ-1) * (ρE - 动能项)

这些换算解释了：为什么 Q 文件看起来“只有 5 个分量”，但后处理里能得到 Pressure/Mach/Temperature 等。

## 重要但常被忽略：Q 可能是无量纲化的
- 很多 CFD 会用参考量把变量无量纲化（例如以入口总压/声速/密度做参考）。
- VTK 的 PLOT3D Reader 会在输出里放一个 `Properties` 数组（例如 freestream Mach、alpha、Re、time），但它并不能替你补齐“参考量到底是什么”。

## 快速自检
- ρ 是否全为正且数量级合理（无量纲时通常 O(1)）
- 用 Q 反算出的速度大小是否与可视化里的 VelocityVector 一致（能验证字段含义是否对齐）
