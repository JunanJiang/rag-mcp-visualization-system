---
id: plot3d-bg2-001
title: PLOT3D 是什么：grid(XYZ) 与 solution(Q) 的基本含义
type: background_card
tags: [plot3d, cfd, data-format, structured-grid]
report_modules: [数据格式]
confidence: high
sources:
  - https://www.grc.nasa.gov/www/wind/valid/plot3d.html
  - https://en.wikipedia.org/wiki/Plot3d_file_format
---

## 核心概念
- **PLOT3D** 是 CFD 里常见的文件格式，主要面向 **结构网格（structured grid）**。
- 最常见的两类文件：
  - **Grid/XYZ**：网格点坐标（几何）
  - **Solution/Q**：网格点上的流场变量数组（结果）

## 你需要记住的事实
- PLOT3D 通常**不自描述**：单位、气体模型、边界条件等往往不在文件里，需要靠算例背景补齐。
- 在多块（multi-block）情况下，会按 block 逐个存储坐标/变量。
## 补充：PLOT3D 文件族里常见的“隐含选项”
- **Formatted vs Unformatted**：同一套格式既可能是文本（formatted/ASCII），也可能是 Fortran 二进制（unformatted）。二进制里还可能遇到 **endianness** 与 record marker 差异，跨平台读写要格外小心。
- **2D/3D、单块/多块**：文件头部通常会给出每个 block 的维度 (ni,nj,nk)，随后按 block 顺序写入坐标或变量。
- **iblank/overset（可选）**：有些 PLOT3D 网格文件会带 `iblank`（0/1 标记），用于遮罩（例如 overset/Chimera 网格的“被覆盖区域”）。如果你看到局部突然“消失”或被裁掉，先确认是否有 iblank 之类的掩码参与。

## 快速识别：你手里的文件更像哪一种
- 只包含 XYZ 坐标数组、没有流场变量：通常是 **grid/xyz**。
- 有 5 个（或更多）分量，且能在 ParaView/VTK 里派生出 Pressure/Mach：通常是 **solution/q（保守量）**。

## 常见坑（后处理最容易踩）
- **文件不自描述** 导致单位/无量纲化不明：看到压力/速度“数量级怪”时，先别怀疑物理，优先怀疑 **参考量（pref、rho_ref、a_ref）** 和 **气体参数（gamma、R）**。
- **块顺序/索引方向不一致**：同一个算例不同工具导入时，可能出现某些块翻转、法向反了、矢量方向奇怪。遇到这种情况，先用几何（例如叶片弦向）做方向校验。
