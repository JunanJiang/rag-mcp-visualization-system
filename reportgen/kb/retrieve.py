"""知识库检索功能"""

import logging
from typing import List, Dict, Any, Optional
from .index import VectorIndex

logger = logging.getLogger(__name__)

DEFAULT_MIN_SCORE = 0.25


def retrieve_cards(
    index: VectorIndex,
    query: str,
    top_k: int = 5,
    filter_modules: Optional[List[str]] = None,
    min_score: float = DEFAULT_MIN_SCORE
) -> List[Dict[str, Any]]:
    """
    检索相关知识卡片
    
    Args:
        index: 向量索引
        query: 查询文本
        top_k: 返回数量
        filter_modules: 按 report_modules 过滤（通过 metadata 后过滤）
        min_score: 最低分数阈值（默认 0.25，过滤低相关结果）
        
    Returns:
        检索结果列表，每个包含 id, title, content, score, metadata
    """
    results = index.search(query, top_k=top_k, filter_modules=filter_modules)
    
    # 过滤低分结果
    results = [r for r in results if r.get("score", 0) >= min_score]
    
    # 通过 metadata 后过滤 report_modules
    if filter_modules:
        filtered = []
        for r in results:
            meta = r.get("metadata", {})
            doc_modules = meta.get("report_modules", [])
            if isinstance(doc_modules, str):
                try:
                    import json
                    doc_modules = json.loads(doc_modules)
                except Exception:
                    doc_modules = []
            if not doc_modules or any(m in doc_modules for m in filter_modules):
                filtered.append(r)
        results = filtered if filtered else results
    
    if not results:
        logger.info(f"RAG 检索无结果 (query={query[:50]}..., min_score={min_score})")
    
    formatted = []
    for r in results:
        formatted.append({
            "id": r.get("id", ""),
            "title": r.get("metadata", {}).get("title", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
            "metadata": r.get("metadata", {})
        })
    
    return formatted


def retrieve_for_slot(
    index: VectorIndex,
    slot_id: str,
    slot_description: str,
    facts: Dict[str, Any],
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    为特定槽位检索知识卡片
    
    Args:
        index: 向量索引
        slot_id: 槽位 ID
        slot_description: 槽位描述
        facts: 运行时事实
        top_k: 返回数量
        
    Returns:
        检索结果列表
    """
    slot_queries = {
        "analysis_purpose_1": "CFD仿真分析目的 流场分析 技术背景",
        "analysis_purpose_2": "CFD仿真分析 性能评估 工程价值",
        "geometry_description": "几何结构 多块网格 Plot3D 计算域",
        "mesh_description": "结构网格 网格质量 网格独立性 分辨率",
        "evaluation_criteria_1": "CFD计算质量 收敛性 守恒性评估",
        "evaluation_criteria_2": "网格独立性验证 结果可信度 边界层分辨率",
        "conclusion": "CFD分析结论 仿真结果总结 流场特性 改进建议",
        "engine_model": "涡喷发动机型号 航空发动机",
        "geometry_images": "几何结构 多块网格 Plot3D",
        "mesh_image": "结构网格 多块网格 网格质量",
        "simulation_standard": "仿真规范 CFD标准 计算流体力学规范",
        "air_properties": "空气物性 流体材料 密度 粘度 比热",
        "evaluation_criteria": "评定准则 CFD质量 收敛性 网格独立性",
        "result_density": "密度分布 density 流场变量",
        "result_momentum": "动量 momentum 速度分布",
        "result_energy": "能量 总能量密度 温度分布",
    }
    
    # 根据槽位类型确定过滤模块
    slot_modules = {
        "analysis_purpose_1": ["分析目的"],
        "analysis_purpose_2": ["分析目的"],
        "geometry_images": ["几何", "网格"],
        "mesh_image": ["网格"],
        "simulation_standard": ["仿真规范", "标准"],
        "air_properties": ["材料", "物性"],
        "evaluation_criteria": ["评定准则", "结果解读"],
        "result_density": ["变量", "结果"],
        "result_momentum": ["变量", "结果"],
        "result_energy": ["变量", "结果"],
        "conclusion": ["结论", "总结"]
    }
    
    query = slot_queries.get(slot_id, slot_description)
    filter_mods = slot_modules.get(slot_id)
    
    # Handle variable_* slots dynamically
    if slot_id.startswith("variable_"):
        var_name = slot_id.replace("variable_", "")
        for var in facts.get("variables", []):
            if var.get("name") == var_name:
                guess = var.get("guess_variableName", "")
                query = f"{guess} CFD 物理含义 数值范围 分布特征"
                filter_mods = ["变量", "结果"]
                break
    elif slot_id.startswith("result_") and facts.get("variables"):
        var_names = [v.get("guess_variableName", "") for v in facts["variables"]]
        query += " " + " ".join(var_names)
    
    # Prefer hybrid_search when available
    search_fn = getattr(index, 'hybrid_search', None)
    if search_fn:
        results = search_fn(query, top_k=top_k, filter_modules=filter_mods)
        if DEFAULT_MIN_SCORE > 0:
            results = [r for r in results if r.get("score", 0) >= DEFAULT_MIN_SCORE]
        formatted = []
        for r in results:
            formatted.append({
                "id": r.get("id", ""),
                "title": r.get("metadata", {}).get("title", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
                "metadata": r.get("metadata", {})
            })
        return formatted
    
    return retrieve_cards(index, query, top_k=top_k, filter_modules=filter_mods)
