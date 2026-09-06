"""构建运行时事实（run_facts.json）"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, List


def build_run_facts(
    pkg_data: Dict[str, Any],
    engine_model_name: str = "",
    project_code: str = "",
    include_blocks: bool = False
) -> Dict[str, Any]:
    """
    从已解析的数据包构建运行时事实
    
    Args:
        pkg_data: 已解析的数据包数据（来自 parse_data_package）
        engine_model_name: 发动机型号名称
        project_code: 项目代码
        include_blocks: 是否包含分块图片
        
    Returns:
        run_facts 字典
    """
    # 直接使用已解析的数据
    facts = pkg_data.copy()
    
    # 添加项目信息
    facts["project"] = {
        "engine_model_name": engine_model_name,
        "project_code": project_code
    }
    
    # 添加选项
    facts["options"] = {
        "include_blocks": include_blocks
    }
    
    # 生成变量摘要
    facts["variables_summary"] = generate_variables_summary(facts.get("variables", []))
    
    # 生成网格摘要
    facts["mesh_summary"] = generate_mesh_summary(facts.get("datasets", {}))
    
    # 生成图片摘要
    facts["images_summary"] = generate_images_summary(facts.get("images", {}))
    
    # 计算派生物理量和深度分析
    facts["derived_quantities"] = compute_derived_quantities(facts.get("variables", []))
    
    # 生成网格质量分析
    facts["mesh_analysis"] = analyze_mesh_quality(facts.get("datasets", {}))
    
    # 生成后处理操作摘要
    facts["ops_summary"] = summarize_automation_ops(facts.get("automation_ops", []))
    
    # 生成流场特征分析
    facts["flow_analysis"] = analyze_flow_characteristics(facts.get("variables", []), facts.get("derived_quantities", {}))
    
    return facts


def generate_variables_summary(variables: list) -> Dict[str, Any]:
    """生成变量摘要"""
    if not variables:
        return {"count": 0, "list": []}
    
    summary = {
        "count": len(variables),
        "list": []
    }
    
    for var in variables:
        var_summary = {
            "name": var.get("name", ""),
            "guess_name": var.get("guess_variableName", "unknown"),
            "range": f"{var.get('range_min', 'N/A')} ~ {var.get('range_max', 'N/A')}"
        }
        summary["list"].append(var_summary)
    
    return summary


def generate_mesh_summary(datasets: Dict[str, Any]) -> Dict[str, Any]:
    """生成网格摘要"""
    if not datasets:
        return {}
    
    blocks = datasets.get("blocks", [])
    
    return {
        "block_count": datasets.get("block_count", len(blocks)),
        "total_points": datasets.get("total_points", 0),
        "total_cells": datasets.get("total_cells", 0),
        "grid_type": "结构网格 (Structured Grid)",
        "blocks_info": [
            {
                "name": b.get("name", ""),
                "dims": b.get("dims", []),
                "points": b.get("points", 0),
                "cells": b.get("cells", 0)
            }
            for b in blocks[:5]  # 只取前5个块的信息
        ],
        "more_blocks": len(blocks) - 5 if len(blocks) > 5 else 0
    }


def generate_images_summary(images: Dict[str, list]) -> Dict[str, Any]:
    """生成图片摘要"""
    summary = {
        "total_count": 0,
        "categories": {}
    }
    
    for category, img_list in images.items():
        count = len(img_list)
        summary["total_count"] += count
        summary["categories"][category] = {
            "count": count,
            "files": [Path(p).name for p in img_list[:5]]
        }
    
    return summary


def compute_derived_quantities(variables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    基于守恒量（密度、动量、能量）计算派生物理量的估算值。
    这些估算值将帮助LLM生成更有深度的分析报告。
    """
    derived = {
        "has_complete_conservation_vars": False,
        "velocity_estimates": {},
        "mach_estimate": {},
        "flow_regime": "unknown",
        "compressibility": "unknown",
        "density_ratio": None,
        "energy_analysis": {},
        "variable_correlations": []
    }
    
    # 查找各守恒量变量
    density_var = None
    momentum_x = None
    momentum_y = None
    momentum_z = None
    energy_var = None
    
    for var in variables:
        guess = var.get("guess_variableName", "")
        if guess == "density":
            density_var = var
        elif guess == "MomentumX":
            momentum_x = var
        elif guess == "MomentumY":
            momentum_y = var
        elif guess == "MomentumZ":
            momentum_z = var
        elif guess == "EnergyStagnationDensity":
            energy_var = var
    
    if density_var and momentum_x and energy_var:
        derived["has_complete_conservation_vars"] = True
        
        rho_min = density_var.get("range_min", 0)
        rho_max = density_var.get("range_max", 1)
        
        if rho_min > 0:
            # 密度比
            derived["density_ratio"] = round(rho_max / rho_min, 2)
            
            # 速度估算
            for label, mom_var in [("u", momentum_x), ("v", momentum_y), ("w", momentum_z)]:
                if mom_var:
                    mom_min = mom_var.get("range_min", 0)
                    mom_max = mom_var.get("range_max", 0)
                    # 速度 = 动量 / 密度
                    v_max_estimate = max(abs(mom_max), abs(mom_min)) / rho_min
                    v_min_estimate = min(abs(mom_max), abs(mom_min)) / rho_max if rho_max > 0 else 0
                    derived["velocity_estimates"][label] = {
                        "max_estimate": round(v_max_estimate, 2),
                        "min_estimate": round(v_min_estimate, 2),
                        "has_reverse_flow": mom_min < 0 and mom_max > 0
                    }
            
            # 总速度估算
            u_max = derived["velocity_estimates"].get("u", {}).get("max_estimate", 0)
            v_max = derived["velocity_estimates"].get("v", {}).get("max_estimate", 0)
            w_max = derived["velocity_estimates"].get("w", {}).get("max_estimate", 0)
            speed_max = math.sqrt(u_max**2 + v_max**2 + w_max**2)
            derived["velocity_estimates"]["speed_max"] = round(speed_max, 2)
            
            # 能量分析和马赫数估算
            if energy_var:
                e_min = energy_var.get("range_min", 0)
                e_max = energy_var.get("range_max", 0)
                derived["energy_analysis"] = {
                    "range_min": e_min,
                    "range_max": e_max,
                    "energy_ratio": round(e_max / e_min, 2) if e_min > 0 else None
                }
                
                # 马赫数粗略估算：假设理想气体 gamma=1.4, R=287
                # p = (gamma-1) * (rhoE - 0.5*rho*V^2)
                # a = sqrt(gamma * p / rho)
                # 使用平均密度和能量做粗略估算
                gamma = 1.4
                rho_avg = (rho_min + rho_max) / 2
                e_avg = (e_min + e_max) / 2
                # 假设动能约占总能量的一部分
                p_estimate = (gamma - 1) * e_avg * 0.5  # 粗略估算
                if p_estimate > 0 and rho_avg > 0:
                    a_estimate = math.sqrt(gamma * p_estimate / rho_avg)
                    if a_estimate > 0:
                        mach_max = speed_max / a_estimate
                        derived["mach_estimate"] = {
                            "max_estimate": round(mach_max, 3),
                            "note": "粗略估算，基于平均状态量，仅供参考"
                        }
                        
                        # 流动状态判断
                        if mach_max < 0.3:
                            derived["flow_regime"] = "不可压缩流（Ma < 0.3）"
                            derived["compressibility"] = "低"
                        elif mach_max < 0.8:
                            derived["flow_regime"] = "亚声速可压缩流（0.3 < Ma < 0.8）"
                            derived["compressibility"] = "中等"
                        elif mach_max < 1.2:
                            derived["flow_regime"] = "跨声速流（0.8 < Ma < 1.2）"
                            derived["compressibility"] = "高"
                        elif mach_max < 5.0:
                            derived["flow_regime"] = "超声速流（1.2 < Ma < 5.0）"
                            derived["compressibility"] = "高"
                        else:
                            derived["flow_regime"] = "高超声速流（Ma > 5.0）"
                            derived["compressibility"] = "极高"
        
        # 变量关联分析
        correlations = []
        if density_var and momentum_x:
            has_reverse = derived["velocity_estimates"].get("u", {}).get("has_reverse_flow", False)
            if has_reverse:
                correlations.append("X方向动量存在正负值，表明存在回流区域")
        if density_var and derived.get("density_ratio", 0) and derived["density_ratio"] > 5:
            correlations.append(f"密度比达到{derived['density_ratio']}:1，表明存在强压缩效应")
        if momentum_y:
            if momentum_y.get("range_min", 0) < 0 and momentum_y.get("range_max", 0) > 0:
                correlations.append("Y方向动量存在正负分布，可能存在横向流动或旋转结构")
        if momentum_z:
            if momentum_z.get("range_min", 0) < 0 and momentum_z.get("range_max", 0) > 0:
                correlations.append("Z方向动量存在正负分布，表明三维流动效应显著")
        derived["variable_correlations"] = correlations
    
    return derived


def analyze_mesh_quality(datasets: Dict[str, Any]) -> Dict[str, Any]:
    """分析网格质量特征"""
    blocks = datasets.get("blocks", [])
    if not blocks:
        return {}
    
    analysis = {
        "block_count": len(blocks),
        "size_distribution": "uniform",
        "largest_block": None,
        "smallest_block": None,
        "aspect_ratio_concerns": [],
        "resolution_notes": []
    }
    
    # 找最大最小块
    blocks_sorted = sorted(blocks, key=lambda b: b.get("points", 0), reverse=True)
    if blocks_sorted:
        largest = blocks_sorted[0]
        smallest = blocks_sorted[-1]
        analysis["largest_block"] = {
            "name": largest.get("name"),
            "points": largest.get("points", 0),
            "dims": largest.get("dims", [])
        }
        analysis["smallest_block"] = {
            "name": smallest.get("name"),
            "points": smallest.get("points", 0),
            "dims": smallest.get("dims", [])
        }
        
        # 判断大小分布是否均匀
        if largest.get("points", 0) > 10 * smallest.get("points", 1):
            analysis["size_distribution"] = "highly_nonuniform"
        elif largest.get("points", 0) > 3 * smallest.get("points", 1):
            analysis["size_distribution"] = "moderately_nonuniform"
    
    # 检查纵横比
    for block in blocks:
        dims = block.get("dims", [])
        if len(dims) == 3 and min(dims) > 0:
            max_ratio = max(dims) / min(dims)
            if max_ratio > 30:
                analysis["aspect_ratio_concerns"].append({
                    "block": block.get("name"),
                    "ratio": round(max_ratio, 1),
                    "dims": dims
                })
    
    # 分辨率说明
    total_points = datasets.get("total_points", 0)
    if total_points > 5000000:
        analysis["resolution_notes"].append("高分辨率网格（>500万节点），适合捕捉精细流动结构")
    elif total_points > 1000000:
        analysis["resolution_notes"].append("中等分辨率网格（100-500万节点），适合工程级分析")
    elif total_points > 100000:
        analysis["resolution_notes"].append("较低分辨率网格（10-100万节点），适合初步评估")
    else:
        analysis["resolution_notes"].append("低分辨率网格（<10万节点），仅适合概念验证")
    
    return analysis


def summarize_automation_ops(automation_ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成后处理操作的结构化摘要"""
    summary = {
        "total_ops": len(automation_ops),
        "by_type": {},
        "variables_analyzed": [],
        "has_contour": False,
        "has_isosurface": False,
        "has_streamline": False,
        "description": ""
    }
    
    for op in automation_ops:
        op_type = op.get("operation_type", "unknown")
        if op_type not in summary["by_type"]:
            summary["by_type"][op_type] = []
        summary["by_type"][op_type].append({
            "variable": op.get("variable_name") or op.get("parameters", {}).get("vector_name", ""),
            "success": op.get("success", False),
            "params": op.get("parameters", {})
        })
        
        var_name = op.get("variable_name")
        if var_name and var_name not in summary["variables_analyzed"]:
            summary["variables_analyzed"].append(var_name)
    
    summary["has_contour"] = "contourLine" in summary["by_type"]
    summary["has_isosurface"] = "isosurface" in summary["by_type"]
    summary["has_streamline"] = "streamline" in summary["by_type"]
    
    # 生成描述
    parts = []
    if summary["has_contour"]:
        n = len(summary["by_type"].get("contourLine", []))
        parts.append(f"{n}组等值线图")
    if summary["has_isosurface"]:
        n = len(summary["by_type"].get("isosurface", []))
        parts.append(f"{n}组等值面图")
    if summary["has_streamline"]:
        parts.append("流线图")
    summary["description"] = "、".join(parts) if parts else "无后处理操作"
    
    return summary


def analyze_flow_characteristics(variables: List[Dict[str, Any]], derived: Dict[str, Any]) -> Dict[str, Any]:
    """基于数据特征分析流场特性，生成分析要点供LLM参考"""
    analysis = {
        "key_findings": [],
        "attention_points": [],
        "limitations": []
    }
    
    # 基于派生量的发现
    if derived.get("has_complete_conservation_vars"):
        flow_regime = derived.get("flow_regime", "unknown")
        if flow_regime != "unknown":
            analysis["key_findings"].append(f"流动状态初步判断为{flow_regime}")
        
        density_ratio = derived.get("density_ratio")
        if density_ratio and density_ratio > 3:
            analysis["key_findings"].append(f"密度变化范围较大（比值约{density_ratio}:1），表明流场存在显著的压缩性效应")
        
        vel_est = derived.get("velocity_estimates", {})
        if vel_est.get("u", {}).get("has_reverse_flow"):
            analysis["attention_points"].append("X方向存在回流（动量正负交替），建议关注流动分离区域")
        if vel_est.get("v", {}).get("has_reverse_flow"):
            analysis["attention_points"].append("Y方向存在双向流动，可能存在横向涡旋或二次流")
        if vel_est.get("w", {}).get("has_reverse_flow"):
            analysis["attention_points"].append("Z方向存在双向流动，三维效应显著")
        
        speed_max = vel_est.get("speed_max", 0)
        if speed_max > 0:
            analysis["key_findings"].append(f"最大速度估算约为{speed_max:.1f}（无量纲或SI单位取决于输入）")
    
    # 通用限制说明
    analysis["limitations"].append("数据包未提供边界条件和求解器设置，无法确定具体工况")
    analysis["limitations"].append("变量单位和无量纲化参考值未知，数值分析基于相对比较")
    analysis["limitations"].append("未提供残差收敛历史，无法评估计算收敛性")
    
    # 检查是否有足够的后处理数据
    has_vars = len(variables) >= 5
    if has_vars:
        analysis["key_findings"].append("数据包包含完整的5个守恒量（密度+3动量+能量），符合Plot3D Q文件标准格式")
    
    return analysis
