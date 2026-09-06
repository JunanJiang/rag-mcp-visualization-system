"""构建 Markdown 报告"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..kb.index import VectorIndex
from ..kb.retrieve import retrieve_for_slot
from ..llm.prompts import get_slot_prompt, get_variable_chinese_name, SLOT_INSTRUCTIONS


def build_markdown_report(
    run_facts: Dict[str, Any],
    vector_index: VectorIndex,
    llm_client: Any,
    data_package_path: Path,
    output_dir: Path,
    dry_run: bool = False
) -> tuple:
    """
    构建 Markdown 报告
    
    Args:
        run_facts: 运行时事实
        vector_index: 向量索引
        llm_client: LLM 客户端
        data_package_path: 数据包路径
        output_dir: 输出目录
        dry_run: 是否为 dry-run 模式
        
    Returns:
        (报告内容, 检索追踪列表)
    """
    facts = run_facts
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 创建 assets 目录并复制图片
    assets_dir = out_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    image_mapping = copy_images_to_assets(facts, assets_dir, data_package_path)
    
    # 检索追踪记录
    traces = []
    
    # 填充各个槽位
    filled_slots = {}
    
    for slot_id in SLOT_INSTRUCTIONS.keys():
        slot_prompt = get_slot_prompt(slot_id, facts)
        
        # 检索知识卡片
        retrieved = retrieve_for_slot(
            vector_index, 
            slot_id, 
            slot_prompt["instruction"],
            facts,
            top_k=3
        )
        
        # 记录检索追踪
        trace = {
            "slot_id": slot_id,
            "query": slot_prompt["query"],
            "modules_filter": slot_prompt["modules"],
            "retrieved_cards": [
                {"id": c.get("id"), "title": c.get("title"), "score": c.get("score", 0)}
                for c in retrieved
            ]
        }
        
        # 获取槽位配置
        slot_config = SLOT_INSTRUCTIONS.get(slot_id, {})
        structured = slot_config.get("structured", False)
        var_key = slot_config.get("var_key", "")
        
        # 调用 LLM 填充
        result = llm_client.fill_slot(
            slot_id, 
            slot_prompt["instruction"],
            facts, 
            retrieved, 
            slot_prompt["max_chars"],
            structured=structured,
            var_key=var_key
        )
        
        filled_slots[slot_id] = result["text"]
        trace["llm_output"] = result["text"][:200]
        trace["cards_used"] = result.get("cards_used", [])
        trace["error"] = result.get("error")
        
        traces.append(trace)
    
    # 生成报告内容
    report_content = generate_report_content(facts, filled_slots, image_mapping)
    
    # 写入文件
    report_file = out_path / "report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    # 写入检索追踪
    traces_file = out_path / "retrieval_traces.jsonl"
    with open(traces_file, 'w', encoding='utf-8') as f:
        for trace in traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    
    return report_content, traces


def copy_images_to_assets(facts: Dict[str, Any], assets_dir: Path, data_package_path: Path) -> Dict[str, str]:
    """
    复制图片到 assets 目录
    
    Returns:
        原路径到新相对路径的映射
    """
    mapping = {}
    images = facts.get("images", {})
    
    for category, img_list in images.items():
        for img_path in img_list:
            # 尝试相对路径和绝对路径
            src = Path(img_path)
            if not src.exists() and data_package_path:
                src = data_package_path / img_path
            
            if src.exists():
                # 生成新文件名
                new_name = f"{category}_{src.name}"
                dst = assets_dir / new_name
                try:
                    shutil.copy2(src, dst)
                    mapping[img_path] = f"assets/{new_name}"
                except Exception:
                    pass
    
    return mapping


def generate_report_content(
    facts: Dict[str, Any],
    filled_slots: Dict[str, str],
    image_mapping: Dict[str, str]
) -> str:
    """生成报告 Markdown 内容"""
    
    # 获取项目信息
    project = facts.get("project", {})
    engine_model = project.get("engine_model_name", "未指定型号")
    project_code = project.get("project_code", "")
    
    manifest = facts.get("manifest", {})
    created_at = manifest.get("created_at", datetime.now().isoformat())
    
    # 获取图片路径
    images = facts.get("images", {})
    geometry_img = get_first_image(images.get("geometry", []), image_mapping)
    mesh_img = get_first_image(images.get("mesh", []), image_mapping)
    
    # 变量图片
    var_images = {}
    for img_path in images.get("variables", []):
        img_name = Path(img_path).stem
        var_images[img_name] = image_mapping.get(img_path, img_path)
    
    # 获取后处理操作信息
    automation_ops = facts.get("automation_ops", [])
    
    # 变量信息
    variables = facts.get("variables", [])
    
    # 构建报告
    report = f"""# 涡喷发动机仿真分析报告

**发动机型号**：{engine_model}  
**项目代码**：{project_code}  
**生成时间**：{created_at}

---

## 1. 分析目的

{filled_slots.get("analysis_purpose_1", "对涡喷发动机内部流场进行数值模拟分析，获取流动特性和压力分布规律。")}

{filled_slots.get("analysis_purpose_2", "验证设计方案的合理性，为后续优化提供数据支撑。")}

---

## 2. 几何结构

### 2.1 模型概述

{filled_slots.get("geometry_description", generate_geometry_description(facts))}

### 2.2 几何模型图

"""
    
    if geometry_img:
        report += f"![几何结构概览]({geometry_img})\n\n"
    else:
        report += "*（数据包未包含几何图片）*\n\n"
    
    report += """---

## 3. 网格结构

### 3.1 网格信息

"""
    # 使用槽位内容或默认生成
    mesh_desc = filled_slots.get("mesh_description", "")
    if mesh_desc:
        report += mesh_desc + "\n\n"
    report += generate_mesh_description(facts)
    report += "\n\n### 3.2 网格图\n\n"
    
    if mesh_img:
        report += f"![网格概览]({mesh_img})\n\n"
    else:
        report += "*（数据包未包含网格图片）*\n\n"
    
    # 添加后处理章节
    report += "---\n\n## 4. 后处理\n\n"
    report += generate_postprocessing_section(automation_ops, image_mapping, facts)
    
    report += f"""---

## 5. 评定准则

{filled_slots.get("evaluation_criteria_1", "CFD 计算应满足收敛性要求，残差下降至少 3-4 个数量级，质量守恒误差应控制在可接受范围内。")}

{filled_slots.get("evaluation_criteria_2", "结果应具有网格独立性，边界层区域应有足够的网格分辨率以捕捉壁面附近的流动特征。")}

---

## 6. 分析结果

### 6.1 变量语义说明

本数据包采用 Plot3D 格式，Q 文件中的变量按照标准约定依次为：密度（ρ）、X/Y/Z 方向动量（ρu, ρv, ρw）、总能量密度（ρE）。变量语义基于 Plot3D Q 文件的常见约定进行推断，具体映射关系如下：

| 原始变量名 | 推断语义 | 中文名称 | 数值范围 | 推断依据 |
|-----------|----------|----------|----------|----------|
"""
    
    # 添加变量语义表格
    for var in variables:
        var_name = var.get("name", "")
        guess_name = var.get("guess_variableName", "unknown")
        chinese_name = get_variable_chinese_name(guess_name)
        range_min = var.get("range_min", "N/A")
        range_max = var.get("range_max", "N/A")
        
        # 格式化数值范围
        if isinstance(range_min, float) and isinstance(range_max, float):
            range_str = f"{range_min:.4g} ~ {range_max:.4g}"
        else:
            range_str = f"{range_min} ~ {range_max}"
        
        # 推断依据
        inference_basis = get_variable_inference_basis(var_name, guess_name)
        
        report += f"| {var_name} | {guess_name} | {chinese_name} | {range_str} | {inference_basis} |\n"
    
    report += "\n> **注**：以上变量语义为基于 Plot3D Q 文件标准格式的推断结果。如需确认，请核对求解器输出设置。\n\n"
    
    # 添加派生物理量说明
    report += generate_derived_quantities_section(variables)
    
    # 各变量详细结果
    for i, var in enumerate(variables):
        var_name = var.get("name", f"F1V{i+1}")
        guess_name = var.get("guess_variableName", "unknown")
        chinese_name = get_variable_chinese_name(guess_name)
        range_min = var.get("range_min", "N/A")
        range_max = var.get("range_max", "N/A")
        
        report += f"### 6.{i+3} {chinese_name}（{var_name}）\n\n"
        
        # 从填充槽位获取描述（槽位ID是variable_开头）
        slot_key = f"variable_{var_name}"
        description = filled_slots.get(slot_key, "")
        
        if not description:
            description = f"{var_name} 对应 {guess_name}（{chinese_name}），"
            description += f"数值范围为 {range_min:.4f} ~ {range_max:.4f}。" if isinstance(range_min, (int, float)) else f"数值范围为 {range_min} ~ {range_max}。"
        
        report += f"{description}\n\n"
        
        # 添加变量图片
        var_img = var_images.get(var_name)
        if var_img:
            report += f"![{var_name} 分布图]({var_img})\n\n"
        else:
            report += f"*（数据包未包含 {var_name} 的可视化图片）*\n\n"
    
    report += f"""---

## 7. 结论

{filled_slots.get("conclusion", generate_default_conclusion(facts))}

"""
    
    # 添加 Block 图片附录（如果启用）
    options = facts.get("options", {})
    if options.get("include_blocks", False):
        geometry_blocks = images.get("geometry_blocks", [])
        mesh_blocks = images.get("mesh_blocks", [])
        
        if geometry_blocks or mesh_blocks:
            report += """---

## 附录：分块图片

以下为模型各计算块（Block）的可视化图片，用于展示多块结构网格的空间分布和拓扑关系。

"""
            # 几何分块
            if geometry_blocks:
                report += "### A.1 几何分块\n\n"
                report += "几何分块图展示了各计算块的空间位置和几何形状：\n\n"
                for img_path in sorted(geometry_blocks):
                    mapped = image_mapping.get(img_path, img_path)
                    # 从文件名提取块名称
                    block_name = Path(img_path).stem  # e.g., "Block_1"
                    report += f"![{block_name} 几何]({mapped})\n\n"
            
            # 网格分块
            if mesh_blocks:
                report += "### A.2 网格分块\n\n"
                report += "网格分块图展示了各计算块的网格划分情况：\n\n"
                for img_path in sorted(mesh_blocks):
                    mapped = image_mapping.get(img_path, img_path)
                    block_name = Path(img_path).stem
                    report += f"![{block_name} 网格]({mapped})\n\n"
    
    report += """---

*本报告由 Simuvision 智能仿真报告生成工具自动生成*
"""
    
    return report


def get_variable_inference_basis(var_name: str, guess_name: str) -> str:
    """获取变量语义推断的依据说明"""
    # 基于 Plot3D Q 文件标准格式的推断依据
    basis_map = {
        "density": "Q文件第1分量，标准约定",
        "MomentumX": "Q文件第2分量，标准约定",
        "MomentumY": "Q文件第3分量，标准约定",
        "MomentumZ": "Q文件第4分量，标准约定",
        "EnergyStagnationDensity": "Q文件第5分量，标准约定",
    }
    
    # 根据变量名后缀推断
    if var_name.endswith("V1"):
        return basis_map.get("density", "Q文件第1分量")
    elif var_name.endswith("V2"):
        return basis_map.get("MomentumX", "Q文件第2分量")
    elif var_name.endswith("V3"):
        return basis_map.get("MomentumY", "Q文件第3分量")
    elif var_name.endswith("V4"):
        return basis_map.get("MomentumZ", "Q文件第4分量")
    elif var_name.endswith("V5"):
        return basis_map.get("EnergyStagnationDensity", "Q文件第5分量")
    
    return basis_map.get(guess_name, "数据包标注")


def generate_derived_quantities_section(variables: List[Dict[str, Any]]) -> str:
    """生成派生物理量说明章节"""
    section = "### 6.2 派生物理量\n\n"
    section += "基于守恒量（密度、动量、能量）可计算以下派生物理量：\n\n"
    
    # 检查是否有必要的变量
    has_density = any(v.get("guess_variableName") == "density" for v in variables)
    has_momentum = any("Momentum" in v.get("guess_variableName", "") for v in variables)
    
    if has_density and has_momentum:
        # 获取密度和动量的范围
        density_var = next((v for v in variables if v.get("guess_variableName") == "density"), None)
        momentum_x = next((v for v in variables if v.get("guess_variableName") == "MomentumX"), None)
        momentum_y = next((v for v in variables if v.get("guess_variableName") == "MomentumY"), None)
        momentum_z = next((v for v in variables if v.get("guess_variableName") == "MomentumZ"), None)
        
        section += "| 派生物理量 | 计算公式 | 物理意义 |\n"
        section += "|------------|----------|----------|\n"
        section += "| 速度分量 u | ρu / ρ | X方向流速 |\n"
        section += "| 速度分量 v | ρv / ρ | Y方向流速 |\n"
        section += "| 速度分量 w | ρw / ρ | Z方向流速 |\n"
        section += "| 速度模 \\|V\\| | √(u² + v² + w²) | 流速大小 |\n"
        section += "| 马赫数 Ma | \\|V\\| / a | 流动可压缩性指标 |\n"
        section += "\n"
        
        # 估算速度范围（如果有数据）
        if density_var and momentum_x:
            rho_min = density_var.get("range_min", 0)
            rho_max = density_var.get("range_max", 1)
            rhou_max = abs(momentum_x.get("range_max", 0))
            rhou_min = abs(momentum_x.get("range_min", 0))
            
            if rho_min > 0:
                u_max_estimate = max(rhou_max, rhou_min) / rho_min
                section += f"> **速度估算**：基于密度范围 ({rho_min:.4g} ~ {rho_max:.4g}) 和动量范围，"
                section += f"X方向速度分量的最大值约为 {u_max_estimate:.1f}（量纲取决于输入数据单位）。\n\n"
    else:
        section += "*（数据包中缺少完整的守恒量变量，无法计算派生物理量）*\n\n"
    
    return section


def get_first_image(img_list: List[str], mapping: Dict[str, str]) -> Optional[str]:
    """获取列表中第一张图片的映射路径"""
    if img_list:
        return mapping.get(img_list[0], img_list[0])
    return None


def generate_geometry_description(facts: Dict[str, Any]) -> str:
    """生成几何描述"""
    manifest = facts.get("manifest", {})
    datasets = facts.get("datasets", {})
    
    dataset_type = manifest.get("dataset_type", "Plot3D")
    block_count = manifest.get("block_count", datasets.get("block_count", "未知"))
    total_points = manifest.get("total_points", datasets.get("total_points", 0))
    total_cells = manifest.get("total_cells", datasets.get("total_cells", 0))
    
    desc = f"本数据包为 {dataset_type} 格式的多块结构网格数据，"
    desc += f"共包含 **{block_count}** 个计算块，"
    desc += f"总计 **{total_points:,}** 个网格点，**{total_cells:,}** 个网格单元。"
    
    return desc


def generate_mesh_description(facts: Dict[str, Any]) -> str:
    """生成网格描述"""
    datasets = facts.get("datasets", {})
    blocks = datasets.get("blocks", [])
    
    if not blocks:
        return "数据包未包含详细的网格信息。"
    
    desc = "本模型采用多块结构网格（Multi-Block Structured Grid），各块网格信息如下：\n\n"
    desc += "| 块名称 | 维度 (nx×ny×nz) | 网格点数 | 网格单元数 |\n"
    desc += "|--------|-----------------|----------|------------|\n"
    
    # 显示所有块的信息
    for block in blocks:
        name = block.get("name", "")
        dims = block.get("dims", [])
        dims_str = "×".join(map(str, dims)) if dims else "N/A"
        points = block.get("points", 0)
        cells = block.get("cells", 0)
        desc += f"| {name} | {dims_str} | {points:,} | {cells:,} |\n"
    
    # 添加汇总行
    total_points = sum(b.get("points", 0) for b in blocks)
    total_cells = sum(b.get("cells", 0) for b in blocks)
    desc += f"| **合计** | **{len(blocks)} 个块** | **{total_points:,}** | **{total_cells:,}** |\n"
    
    return desc


def generate_postprocessing_params_table(op_type: str, ops: List[Dict[str, Any]], var_name_map: Dict[str, str]) -> str:
    """
    生成后处理操作参数表格（用于可复现性说明）
    
    Args:
        op_type: 操作类型 (contourLine, isosurface, streamline)
        ops: 该类型的所有操作
        var_name_map: 变量名到语义名的映射
    """
    from ..llm.prompts import get_variable_chinese_name
    
    if not ops:
        return ""
    
    if op_type == "contourLine":
        # 等值线参数表
        table = "**后处理参数设置：**\n\n"
        table += "| 变量 | 数值范围 | 等值线数 |\n"
        table += "|------|----------|----------|\n"
        for op in ops:
            params = op.get("parameters", {})
            var_name = params.get("variable_name", "")
            guess_name = var_name_map.get(var_name, var_name)
            chinese_name = get_variable_chinese_name(guess_name)
            min_val = params.get("min_value", "N/A")
            max_val = params.get("max_value", "N/A")
            num_lines = params.get("num_contourLines", "N/A")
            if isinstance(min_val, float):
                min_val = f"{min_val:.4g}"
            if isinstance(max_val, float):
                max_val = f"{max_val:.4g}"
            table += f"| {chinese_name}（{var_name}） | {min_val} ~ {max_val} | {num_lines} |\n"
        table += "\n"
        return table
    
    elif op_type == "isosurface":
        # 等值面参数表
        table = "**后处理参数设置：**\n\n"
        table += "| 变量 | 数值范围 | 等值面数 | 使用数据范围 |\n"
        table += "|------|----------|----------|-------------|\n"
        for op in ops:
            params = op.get("parameters", {})
            var_name = params.get("variable_name", "")
            guess_name = var_name_map.get(var_name, var_name)
            chinese_name = get_variable_chinese_name(guess_name)
            min_val = params.get("min_value", "N/A")
            max_val = params.get("max_value", "N/A")
            num_contours = params.get("num_contours", "N/A")
            use_data_range = "是" if params.get("use_data_range", False) else "否"
            if isinstance(min_val, float):
                min_val = f"{min_val:.4g}"
            if isinstance(max_val, float):
                max_val = f"{max_val:.4g}"
            table += f"| {chinese_name}（{var_name}） | {min_val} ~ {max_val} | {num_contours} | {use_data_range} |\n"
        table += "\n"
        return table
    
    elif op_type == "streamline":
        # 流线参数表
        table = "**后处理参数设置：**\n\n"
        table += "| 参数 | 值 |\n"
        table += "|------|----|\n"
        # 取第一个流线操作的参数（通常只有一个）
        if ops:
            params = ops[0].get("parameters", {})
            vector_name = params.get("vector_name", "VelocityVector")
            num_seeds = params.get("num_seeds", "N/A")
            init_step = params.get("init_step", "N/A")
            max_length = params.get("max_length", "N/A")
            auto_detect = "是" if params.get("auto_detect_inlet", False) else "否"
            
            table += f"| 矢量场 | {vector_name} |\n"
            table += f"| 种子点数量 | {num_seeds:,} |\n" if isinstance(num_seeds, int) else f"| 种子点数量 | {num_seeds} |\n"
            table += f"| 初始步长 | {init_step} |\n"
            table += f"| 最大长度 | {max_length:,} |\n" if isinstance(max_length, int) else f"| 最大长度 | {max_length} |\n"
            table += f"| 自动检测入口 | {auto_detect} |\n"
        table += "\n"
        return table
    
    return ""


def generate_postprocessing_section(automation_ops: List[Dict[str, Any]], image_mapping: Dict[str, str], facts: Dict[str, Any]) -> str:
    """
    生成后处理章节内容，按操作类型分组
    
    Args:
        automation_ops: 后处理操作列表
        image_mapping: 图片路径映射
        facts: 运行时事实（包含变量信息）
    """
    # 构建变量名到中文名称的映射
    var_name_map = {}
    for var in facts.get("variables", []):
        var_name_map[var.get("name", "")] = var.get("guess_variableName", "")
    if not automation_ops:
        return "*（数据包未包含后处理图片）*\n\n"
    
    # 按操作类型分组
    ops_by_type = {
        "contourLine": [],
        "isosurface": [],
        "streamline": []
    }
    
    for op in automation_ops:
        op_type = op.get("operation_type", "")
        if op_type in ops_by_type:
            ops_by_type[op_type].append(op)
    
    # 操作类型的中文名称和说明
    type_info = {
        "contourLine": {
            "name": "等值线图",
            "desc": "等值线图（Contour Line）展示了场变量在切面上的分布情况，通过不同颜色的线条表示变量的等值区域，便于观察变量的梯度变化和分布规律。"
        },
        "isosurface": {
            "name": "等值面图",
            "desc": "等值面图（Isosurface）展示了三维空间中场变量取特定值的曲面，可以直观地观察变量在三维空间中的分布形态和结构特征。"
        },
        "streamline": {
            "name": "流线图",
            "desc": "流线图（Streamline）展示了流场中流体质点的运动轨迹，通过流线可以观察流动的主方向、回流区域和涡旋结构。"
        }
    }
    
    section = ""
    subsection_num = 1
    
    for op_type, ops in ops_by_type.items():
        if not ops:
            continue
        
        info = type_info.get(op_type, {"name": op_type, "desc": ""})
        section += f"### 4.{subsection_num} {info['name']}\n\n"
        section += f"{info['desc']}\n\n"
        
        # 添加后处理参数表格（可复现性）
        section += generate_postprocessing_params_table(op_type, ops, var_name_map)
        
        # 添加该类型的所有图片
        for op in ops:
            # 获取变量名（streamline 用 vector_name，其他用 variable_name）
            params = op.get("parameters", {})
            var_name = params.get("variable_name") or params.get("vector_name", "")
            
            # 根据操作类型确定图片名称前缀
            img_prefix_map = {
                "contourLine": "contour",
                "isosurface": "isosurface", 
                "streamline": "streamline"
            }
            img_prefix = img_prefix_map.get(op_type, op_type)
            
            # 构建预期的 assets 路径
            expected_asset = f"assets/automation_{img_prefix}_{var_name}.png"
            
            # 在 image_mapping 中查找匹配
            mapped_path = None
            for orig_path, new_path in image_mapping.items():
                if new_path == expected_asset:
                    mapped_path = new_path
                    break
                # 备用匹配：检查文件名
                if var_name and var_name in new_path and img_prefix in new_path:
                    mapped_path = new_path
                    break
            
            if mapped_path:
                # 生成图片标题
                from ..llm.prompts import get_variable_chinese_name
                if var_name and var_name != "VelocityVector":
                    # 先查找 guess_variableName，再获取中文名
                    guess_name = var_name_map.get(var_name, var_name)
                    chinese_name = get_variable_chinese_name(guess_name)
                    caption = f"{info['name']} - {chinese_name}（{var_name}）"
                elif var_name == "VelocityVector":
                    caption = f"{info['name']} - 速度矢量"
                else:
                    caption = f"{info['name']}"
                
                section += f"![{caption}]({mapped_path})\n\n"
        
        subsection_num += 1
    
    if not section:
        return "*（数据包未包含后处理图片）*\n\n"
    
    return section


def generate_default_conclusion(facts: Dict[str, Any]) -> str:
    """生成默认结论"""
    manifest = facts.get("manifest", {})
    variables = facts.get("variables", [])
    images = facts.get("images", {})
    
    conclusions = []
    
    # 数据包概况
    dataset_type = manifest.get("dataset_type", "Plot3D")
    block_count = manifest.get("block_count", "未知")
    conclusions.append(f"1. 本数据包为 {dataset_type} 格式，包含 {block_count} 个计算块的结构网格数据。")
    
    # 变量信息
    if variables:
        var_names = [v.get("guess_variableName", v.get("name", "")) for v in variables]
        conclusions.append(f"2. 数据包包含 {len(variables)} 个场变量：{', '.join(var_names)}，符合可压缩流 Q 文件的典型格式。")
    
    # 可视化产物
    total_images = sum(len(v) for v in images.values())
    if total_images > 0:
        conclusions.append(f"3. 数据包包含 {total_images} 张可视化图片，涵盖几何、网格和后处理结果。")
    
    # 限制说明
    conclusions.append("4. 注意：本数据包未包含边界条件和求解器设置信息，无法给出具体的性能评估结论。")
    conclusions.append("5. 建议结合原始算例说明文件，进一步验证变量单位和无量纲化参考值。")
    
    return "\n\n".join(conclusions)
