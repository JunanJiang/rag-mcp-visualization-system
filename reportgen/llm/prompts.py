"""槽位填充提示词和指令"""

from typing import Dict, Any


# 各槽位的填充指令
SLOT_INSTRUCTIONS: Dict[str, Dict[str, Any]] = {
    "analysis_purpose_1": {
        "instruction": "写出本次 CFD 仿真分析的第一个主要目的，聚焦于流场特性分析",
        "max_chars": 150,
        "modules": ["分析目的"]
    },
    "analysis_purpose_2": {
        "instruction": "写出本次 CFD 仿真分析的第二个主要目的，聚焦于性能评估或设计验证",
        "max_chars": 150,
        "modules": ["分析目的"]
    },
    "engine_model": {
        "instruction": "填写涡喷发动机型号名称",
        "max_chars": 50,
        "modules": []
    },
    "geometry_description": {
        "instruction": "描述几何结构模块，包括数据包类型、块数量、总点数/单元数等基本信息",
        "max_chars": 200,
        "modules": ["几何", "网格"]
    },
    "mesh_description": {
        "instruction": "描述网格特征，包括网格类型（结构/非结构）、多块信息、各块维度分布等",
        "max_chars": 200,
        "modules": ["网格"]
    },
    "simulation_standard": {
        "instruction": "说明本次仿真遵循的规范或标准",
        "max_chars": 100,
        "modules": ["仿真规范", "标准"]
    },
    "air_properties": {
        "instruction": "描述空气作为流体材料的物理属性（密度、粘度、比热、导热系数等）",
        "max_chars": 150,
        "modules": ["材料", "物性"]
    },
    "evaluation_criteria_1": {
        "instruction": "写出第一段评定准则，关于 CFD 计算质量（如收敛性、质量守恒）",
        "max_chars": 200,
        "modules": ["评定准则", "结果解读"]
    },
    "evaluation_criteria_2": {
        "instruction": "写出第二段评定准则，关于结果可信度（如网格独立性、边界层分辨）",
        "max_chars": 200,
        "modules": ["评定准则", "结果解读"]
    },
    "result_F1V1": {
        "instruction": "用4句话解释 F1V1（density 密度）：1)变量通俗含义 2)本次数据范围特征 3)看图应关注什么 4)数据限制说明",
        "max_chars": 200,
        "modules": ["变量", "结果解读"],
        "structured": True,
        "var_key": "density"
    },
    "result_F1V2": {
        "instruction": "用4句话解释 F1V2（MomentumX X方向动量）：1)变量通俗含义 2)本次数据范围特征 3)看图应关注什么 4)数据限制说明",
        "max_chars": 200,
        "modules": ["变量", "结果解读"],
        "structured": True,
        "var_key": "momentum"
    },
    "result_F1V3": {
        "instruction": "用4句话解释 F1V3（MomentumY Y方向动量）：1)变量通俗含义 2)本次数据范围特征 3)看图应关注什么 4)数据限制说明",
        "max_chars": 200,
        "modules": ["变量", "结果解读"],
        "structured": True,
        "var_key": "momentum"
    },
    "result_F1V4": {
        "instruction": "用4句话解释 F1V4（MomentumZ Z方向动量）：1)变量通俗含义 2)本次数据范围特征 3)看图应关注什么 4)数据限制说明",
        "max_chars": 200,
        "modules": ["变量", "结果解读"],
        "structured": True,
        "var_key": "momentum"
    },
    "result_F1V5": {
        "instruction": "用4句话解释 F1V5（EnergyStagnationDensity 总能量密度）：1)变量通俗含义 2)本次数据范围特征 3)看图应关注什么 4)数据限制说明",
        "max_chars": 200,
        "modules": ["变量", "结果解读"],
        "structured": True,
        "var_key": "energy"
    },
    "conclusion": {
        "instruction": "基于数据事实和知识背景，总结 3-5 条结论，包括数据包概况、变量语义、可视化产物、以及数据限制说明",
        "max_chars": 500,
        "modules": ["结论", "总结"]
    },
    "placeholder_skip": {
        "instruction": "此处暂不填写",
        "max_chars": 50,
        "modules": []
    }
}


def get_slot_prompt(slot_id: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取槽位的填充提示信息
    
    Args:
        slot_id: 槽位 ID
        facts: 运行时事实
        
    Returns:
        包含 instruction, max_chars, query, modules 的字典
    """
    slot_info = SLOT_INSTRUCTIONS.get(slot_id, {
        "instruction": f"填写 {slot_id} 相关内容",
        "max_chars": 150,
        "modules": []
    })
    
    # 构建检索查询
    query = slot_info["instruction"]
    
    # 根据槽位类型增强查询
    if slot_id.startswith("result_F1V"):
        var_name = slot_id.replace("result_", "")
        for var in facts.get("variables", []):
            if var.get("name") == var_name:
                guess_name = var.get("guess_variableName", "")
                query += f" {guess_name} {var_name}"
                break
    
    return {
        "instruction": slot_info["instruction"],
        "max_chars": slot_info["max_chars"],
        "query": query,
        "modules": slot_info["modules"]
    }


# 变量名称映射（中英文）
VARIABLE_NAME_MAP = {
    "density": "密度",
    "MomentumX": "X方向动量",
    "MomentumY": "Y方向动量",
    "MomentumZ": "Z方向动量",
    "EnergyStagnationDensity": "总能量密度",
    "Pressure": "压力",
    "Temperature": "温度",
    "Velocity": "速度",
    "Mach": "马赫数"
}


def get_variable_chinese_name(english_name: str) -> str:
    """获取变量的中文名称"""
    return VARIABLE_NAME_MAP.get(english_name, english_name)


# 空气标准物性表（常用取值）
AIR_PROPERTIES_TABLE = {
    "temperature": {"value": 288.15, "unit": "K", "name": "温度"},
    "density": {"value": 1.225, "unit": "kg/m³", "name": "密度"},
    "dynamic_viscosity": {"value": 1.789e-5, "unit": "Pa·s", "name": "动力粘度"},
    "kinematic_viscosity": {"value": 1.46e-5, "unit": "m²/s", "name": "运动粘度"},
    "specific_heat_cp": {"value": 1005, "unit": "J/(kg·K)", "name": "定压比热"},
    "thermal_conductivity": {"value": 0.0257, "unit": "W/(m·K)", "name": "导热系数"},
    "gamma": {"value": 1.4, "unit": "-", "name": "比热比"},
    "gas_constant_R": {"value": 287.05, "unit": "J/(kg·K)", "name": "气体常数"}
}


def get_air_properties_markdown() -> str:
    """生成空气物性表的 Markdown 格式"""
    lines = ["| 参数 | 数值 | 单位 |", "|------|------|------|"]
    for key, prop in AIR_PROPERTIES_TABLE.items():
        lines.append(f"| {prop['name']} | {prop['value']} | {prop['unit']} |")
    return "\n".join(lines)
