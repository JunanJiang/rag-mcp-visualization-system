---
id: heat-transfer-analysis
title: 气动加热与传热分析
tags: [传热, 气动加热, 热流密度, 温度场]
report_modules: [variable_analysis, conclusions]
confidence: medium
sources: ["Anderson J.D. Hypersonic and High-Temperature Gas Dynamics", "陶文铨. 数值传热学"]
---

# 气动加热与传热分析

高速流动中的气动加热是飞行器热防护设计的关键问题，CFD仿真可提供详细的热流分布。

## 关键物理量

- **壁面热流密度** (q_w)：单位面积单位时间的热量传递，单位 W/m²
- **斯坦顿数** (St)：无量纲热流系数，St = q_w / (ρ∞·V∞·cp·(T_aw - T_w))
- **绝热壁温** (T_aw)：绝热条件下壁面达到的平衡温度
- **恢复系数** (r)：r = (T_aw - T∞) / (T_0 - T∞)，层流约0.85，湍流约0.89

## 温度场解读

| 温度特征 | 物理含义 | 工程关注度 |
|---------|---------|----------|
| 壁面温度 > 500K | 中等加热 | 需考虑材料热性能 |
| 壁面温度 > 1500K | 强加热 | 需热防护系统 |
| 温度梯度极大区域 | 热流密度峰值 | 热防护设计重点区域 |
| 驻点温度 | 最高加热位置 | 头部热防护关键 |

## 从Plot3D数据估算温度

```
T = γ·Ma∞²·p/Q1  （无量纲温度）
T_dimensional = T · T∞_ref  （量纲化）
```

其中 T∞_ref 为参考温度（来流静温），通常在manifest.json中给出。
