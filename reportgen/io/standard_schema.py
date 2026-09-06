"""标准数据输入 Schema（Standard Data Schema）

定义了报告生成引擎接受的标准化 JSON 数据结构。
任何外部平台只需按此 Schema 提交数据，即可调用报告生成 API。

架构说明：
    外部平台数据 ──→ [可选: 内置适配器自动转换] ──→ 标准数据Schema ──→ 报告生成引擎
                                                       ↑
                                        外部平台也可以直接提交标准格式

已知格式（如 SimuVision）→ 用内置适配器自动转换
未知格式 → 外部平台按此 Schema 提交 JSON 即可

Schema 版本: 1.0
"""

# ── Schema 版本 ──
SCHEMA_VERSION = "1.0"

# ── 标准数据 Schema 定义（JSON Schema 风格文档） ──
STANDARD_SCHEMA = {
    "version": SCHEMA_VERSION,
    "description": "SimuReport 标准数据输入格式 v1.0",
    "required_fields": ["manifest", "variables"],
    "optional_fields": ["datasets", "images", "metadata", "hierarchy", "automation_ops", "view_presets"],
    "fields": {
        "manifest": {
            "type": "object",
            "description": "数据包元信息",
            "required": ["source_platform"],
            "properties": {
                "source_platform": "数据来源平台标识（如 'SimuVision', 'OpenFOAM', 'Fluent', 'custom'）",
                "app_name": "应用程序名称",
                "app_version": "应用程序版本",
                "dataset_type": "数据集类型（如 'structured_grid', 'unstructured_mesh', 'tabular'）",
                "dataset_name": "数据集名称",
                "block_count": "网格块数量（结构化网格）",
                "total_points": "总网格点数",
                "total_cells": "总网格单元数",
                "description": "数据集描述（自由文本）",
            }
        },
        "variables": {
            "type": "array",
            "description": "变量/物理量列表",
            "items": {
                "name": "变量名（原始标识符）",
                "display_name": "变量显示名（可选，如 '密度', 'Density'）",
                "unit": "物理单位（可选，如 'kg/m^3', 'Pa'）",
                "components": "分量数（标量=1，矢量=3）",
                "location": "数据位置（'node' / 'cell'）",
                "range_min": "最小值（可选）",
                "range_max": "最大值（可选）",
                "statistics": "统计信息对象（可选，含 mean/std/median 等）",
            }
        },
        "datasets": {
            "type": "object",
            "description": "数据集/网格结构信息",
            "properties": {
                "block_count": "块数量",
                "blocks": "块信息数组（每块含 dimensions, points, cells 等）",
                "total_points": "总点数",
                "total_cells": "总单元数",
            }
        },
        "images": {
            "type": "object",
            "description": "可视化图片（按类别分组，值为 URL 或 Base64 数组）",
            "example": {
                "geometry": ["url_or_base64_1", "..."],
                "mesh": ["url_or_base64_1", "..."],
                "variables": ["url_or_base64_1", "..."],
                "results": ["url_or_base64_1", "..."],
            }
        },
        "metadata": {
            "type": "object",
            "description": "自由扩展的键值对元数据（任何额外信息）",
        },
        "hierarchy": {
            "type": "object",
            "description": "数据层次结构（树形结构）",
        },
        "automation_ops": {
            "type": "array",
            "description": "自动化操作记录列表",
        },
        "view_presets": {
            "type": "array",
            "description": "视角预设列表",
        },
    }
}


# ── 示例数据（用于文档和测试） ──
EXAMPLE_INPUT = {
    "manifest": {
        "source_platform": "custom",
        "app_name": "MySimulationTool",
        "app_version": "2.0",
        "dataset_type": "structured_grid",
        "dataset_name": "wing_simulation_case01",
        "block_count": 2,
        "total_points": 150000,
        "total_cells": 140000,
        "description": "NACA0012 翼型绕流仿真数据"
    },
    "variables": [
        {
            "name": "Density",
            "display_name": "密度",
            "unit": "kg/m^3",
            "components": 1,
            "location": "node",
            "range_min": 0.8,
            "range_max": 1.4,
        },
        {
            "name": "Pressure",
            "display_name": "压力",
            "unit": "Pa",
            "components": 1,
            "location": "node",
            "range_min": 50000,
            "range_max": 120000,
        },
        {
            "name": "Velocity",
            "display_name": "速度",
            "unit": "m/s",
            "components": 3,
            "location": "node",
            "range_min": 0,
            "range_max": 340,
        }
    ],
    "datasets": {
        "block_count": 2,
        "blocks": [
            {"id": 0, "dimensions": [100, 50, 30], "points": 150000, "cells": 140000},
            {"id": 1, "dimensions": [80, 40, 20], "points": 64000, "cells": 59000},
        ],
        "total_points": 214000,
        "total_cells": 199000,
    },
    "images": {
        "geometry": [],
        "mesh": [],
        "variables": [],
    },
    "metadata": {
        "solver": "RANS",
        "turbulence_model": "k-omega SST",
        "mach_number": 0.8,
        "reynolds_number": 6e6,
    }
}


def validate_standard_input(data: dict) -> tuple[bool, str]:
    """验证输入数据是否符合标准 Schema
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "输入必须是 JSON 对象"

    # 检查必需字段
    if "manifest" not in data:
        return False, "缺少必需字段: manifest"
    if "variables" not in data:
        return False, "缺少必需字段: variables"

    manifest = data["manifest"]
    if not isinstance(manifest, dict):
        return False, "manifest 必须是对象"
    if "source_platform" not in manifest:
        return False, "manifest 中缺少必需字段: source_platform"

    variables = data["variables"]
    if not isinstance(variables, list):
        return False, "variables 必须是数组"
    if len(variables) == 0:
        return False, "variables 不能为空（至少需要一个变量）"

    # 验证每个变量
    for i, var in enumerate(variables):
        if not isinstance(var, dict):
            return False, f"variables[{i}] 必须是对象"
        if "name" not in var:
            return False, f"variables[{i}] 缺少必需字段: name"

    return True, ""


def normalize_to_facts(data: dict) -> dict:
    """将标准 Schema 输入转换为内部 facts 字典格式
    
    这是标准 Schema → 内部引擎的桥梁。
    无论数据来自文件适配器还是 API 直接提交，最终都转换为统一的 facts 格式。
    """
    manifest = data.get("manifest", {})
    variables = data.get("variables", [])
    datasets = data.get("datasets", {})
    images = data.get("images", {})

    # 标准化变量格式（确保兼容内部格式）
    normalized_vars = []
    for var in variables:
        normalized_vars.append({
            "name": var.get("name", ""),
            "guess_variableName": var.get("display_name", var.get("name", "")),
            "components": var.get("components", 1),
            "location": var.get("location", "node"),
            "range_min": var.get("range_min"),
            "range_max": var.get("range_max"),
            "unit": var.get("unit", ""),
            "statistics": var.get("statistics", {}),
        })

    # 构建 facts 字典（与适配器 parse() 输出格式一致）
    facts = {
        "data_dir": "",  # API 直接提交时无本地目录
        "manifest": {
            "source_platform": manifest.get("source_platform", "unknown"),
            "app_name": manifest.get("app_name", ""),
            "app_version": manifest.get("app_version", ""),
            "dataset_type": manifest.get("dataset_type", ""),
            "dataset_name": manifest.get("dataset_name", ""),
            "block_count": manifest.get("block_count", 0),
            "total_points": manifest.get("total_points", 0),
            "total_cells": manifest.get("total_cells", 0),
            "description": manifest.get("description", ""),
        },
        "variables": normalized_vars,
        "datasets": datasets or {"block_count": 0, "blocks": [], "total_points": 0, "total_cells": 0},
        "images": images or {},
        "hierarchy": data.get("hierarchy"),
        "automation_ops": data.get("automation_ops", []),
        "view_presets": data.get("view_presets", []),
        "metadata": data.get("metadata", {}),
    }

    return facts
