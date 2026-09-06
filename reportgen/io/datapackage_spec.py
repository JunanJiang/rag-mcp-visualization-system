"""SimuVision 数据包格式规范（DataPackage Spec v1.0）

定义数据包内每个文件的 JSON Schema，提供验证函数。
外部平台对接时可参考此规范构建合规数据包。

用法：
    from reportgen.io.datapackage_spec import validate_data_package, SPEC_VERSION
    is_valid, errors, warnings = validate_data_package(Path("./数据包"))
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

SPEC_VERSION = "1.0"

# ── manifest.json Schema ──

MANIFEST_SCHEMA = {
    "type": "object",
    "description": "数据包清单（入口文件），声明数据包元信息和文件引用",
    "required": ["dataset"],
    "properties": {
        "spec_version": {
            "type": "string",
            "description": "数据包规范版本号，当前为 1.0",
            "pattern": r"^\d+\.\d+$"
        },
        "app": {
            "type": "object",
            "description": "导出应用信息",
            "properties": {
                "name": {"type": "string", "description": "应用名称，如 'SimuVision-Desktop'"},
                "version": {"type": "string", "description": "应用版本号"}
            }
        },
        "createdAt": {
            "type": "string",
            "description": "数据包创建时间（ISO 8601 格式）"
        },
        "sessionId": {
            "type": "string",
            "description": "导出会话唯一标识"
        },
        "dataset": {
            "type": "object",
            "description": "数据集核心信息",
            "required": ["datasetType"],
            "properties": {
                "datasetName": {"type": "string", "description": "数据集名称"},
                "datasetType": {
                    "type": "string",
                    "description": "数据集类型",
                    "enum": ["Plot3DMultiBlock", "Plot3DSingleBlock",
                             "VTKUnstructured", "OpenFOAM", "FluentCase", "Custom"]
                },
                "blockCount": {
                    "type": ["string", "integer"],
                    "description": "网格块数量（字符串或整数均可）"
                },
                "totalPoints": {"type": "integer", "description": "总网格点数", "minimum": 0},
                "totalCells": {"type": "integer", "description": "总网格单元数", "minimum": 0}
            }
        },
        "exports": {
            "type": "object",
            "description": "其他 JSON 文件的引用路径",
            "properties": {
                "datasets": {"type": "string"},
                "variables": {"type": "string"},
                "hierarchy": {"type": "string"},
                "images": {"type": "array", "items": {"type": "string"}},
                "viewPresets": {"type": "string"}
            }
        },
        "sourceFiles": {
            "type": "object",
            "description": "原始仿真文件路径引用"
        }
    }
}

# ── variables.json Schema ──

VARIABLES_SCHEMA = {
    "type": "object",
    "description": "流场变量列表",
    "required": ["variables"],
    "properties": {
        "variables": {
            "type": "array",
            "description": "变量数组",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "变量原始名称（如 F1V1）"},
                    "guess_variableName": {
                        "type": "string",
                        "description": "语义推测名称（如 density, MomentumX）"
                    },
                    "components": {
                        "type": "integer",
                        "description": "分量数（标量=1，矢量=3）",
                        "minimum": 1
                    },
                    "location": {
                        "type": "string",
                        "description": "数据位置",
                        "enum": ["PointData", "CellData", "node", "cell"]
                    },
                    "rangeGlobal": {
                        "type": "object",
                        "description": "全局数值范围",
                        "properties": {
                            "min": {"type": "number"},
                            "max": {"type": "number"}
                        }
                    }
                }
            }
        }
    }
}

# ── datasets.json Schema ──

DATASETS_SCHEMA = {
    "type": "object",
    "description": "网格块详情",
    "required": ["datasets"],
    "properties": {
        "datasets": {
            "type": "array",
            "description": "网格块数组",
            "items": {
                "type": "object",
                "required": ["blockIndex"],
                "properties": {
                    "blockIndex": {"type": "integer", "minimum": 0},
                    "name": {"type": "string"},
                    "datasetId": {"type": "string"},
                    "type": {
                        "type": "string",
                        "description": "VTK 数据类型（如 vtkStructuredGrid）"
                    },
                    "topology": {
                        "type": "object",
                        "properties": {
                            "dims": {
                                "type": "object",
                                "properties": {
                                    "values": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 1},
                                        "minItems": 3,
                                        "maxItems": 3
                                    }
                                }
                            },
                            "points": {"type": "integer", "minimum": 0},
                            "cells": {"type": "integer", "minimum": 0}
                        }
                    },
                    "bounds": {
                        "type": "object",
                        "description": "空间边界 [xmin, xmax, ymin, ymax, zmin, zmax]",
                        "properties": {
                            "values": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 6,
                                "maxItems": 6
                            }
                        }
                    }
                }
            }
        }
    }
}


# ── 数据包目录结构定义 ──

REQUIRED_FILES = ["manifest.json", "variables.json"]

OPTIONAL_FILES = ["datasets.json", "hierarchy.json"]

OPTIONAL_DIRS = [
    "images",
    "images/geometry",
    "images/mesh",
    "images/variables",
    "automation",
    "automation/ops",
    "views"
]


# ── 验证工具函数 ──

def _validate_json_against_schema(data: Any, schema: Dict[str, Any], path_prefix: str = "") -> List[str]:
    """轻量级 JSON Schema 验证（不依赖 jsonschema 库）
    
    仅校验：type / required / enum / minimum / minItems / maxItems / pattern
    返回错误消息列表
    """
    errors = []

    expected_type = schema.get("type")
    if expected_type:
        type_map = {
            "object": dict, "array": list, "string": str,
            "integer": int, "number": (int, float), "boolean": bool
        }
        if isinstance(expected_type, list):
            allowed = tuple(t for e in expected_type for t in (type_map.get(e, ()) if isinstance(type_map.get(e), tuple) else (type_map.get(e, type(None)),)))
            if not isinstance(data, allowed):
                errors.append(f"{path_prefix}: 类型应为 {expected_type}，实际为 {type(data).__name__}")
                return errors
        else:
            expected_cls = type_map.get(expected_type)
            if expected_cls and not isinstance(data, expected_cls):
                errors.append(f"{path_prefix}: 类型应为 {expected_type}，实际为 {type(data).__name__}")
                return errors

    # required
    if isinstance(data, dict):
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path_prefix}: 缺少必需字段 '{req}'")

        # 递归验证 properties
        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in data and isinstance(sub_schema, dict) and "type" in sub_schema:
                errors.extend(_validate_json_against_schema(data[key], sub_schema, f"{path_prefix}.{key}"))

    # array items
    if isinstance(data, list):
        items_schema = schema.get("items")
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(data) < min_items:
            errors.append(f"{path_prefix}: 数组至少需要 {min_items} 项，实际 {len(data)} 项")
        if max_items is not None and len(data) > max_items:
            errors.append(f"{path_prefix}: 数组最多 {max_items} 项，实际 {len(data)} 项")
        if items_schema and isinstance(items_schema, dict):
            for i, item in enumerate(data):
                errors.extend(_validate_json_against_schema(item, items_schema, f"{path_prefix}[{i}]"))

    # enum
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path_prefix}: 值 '{data}' 不在允许范围 {schema['enum']} 内")

    # minimum
    if "minimum" in schema and isinstance(data, (int, float)):
        if data < schema["minimum"]:
            errors.append(f"{path_prefix}: 值 {data} 小于最小值 {schema['minimum']}")

    return errors


def _load_json_safe(file_path: Path) -> Tuple[Any, str]:
    """安全加载 JSON 文件，返回 (data, error)"""
    if not file_path.exists():
        return None, f"文件不存在: {file_path.name}"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f), ""
    except json.JSONDecodeError as e:
        return None, f"{file_path.name} JSON 解析失败: {e}"
    except UnicodeDecodeError as e:
        return None, f"{file_path.name} 编码错误: {e}"


def validate_data_package(data_dir: Path) -> Tuple[bool, List[str], List[str]]:
    """验证数据包是否符合 DataPackage Spec v1.0
    
    Args:
        data_dir: 数据包根目录路径
        
    Returns:
        (is_valid, errors, warnings)
        - is_valid: True 表示核心文件合规（errors 为空）
        - errors:   阻断性错误列表（必需文件缺失或格式严重不合规）
        - warnings: 非阻断性警告列表（可选文件缺失、字段缺失等）
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data_dir.exists():
        return False, [f"目录不存在: {data_dir}"], []
    if not data_dir.is_dir():
        return False, [f"路径不是目录: {data_dir}"], []

    # ── 1. 检查必需文件 ──
    for fname in REQUIRED_FILES:
        if not (data_dir / fname).exists():
            errors.append(f"缺少必需文件: {fname}")

    if errors:
        return False, errors, warnings

    # ── 2. 验证 manifest.json ──
    manifest, err = _load_json_safe(data_dir / "manifest.json")
    if err:
        errors.append(err)
    else:
        manifest_errors = _validate_json_against_schema(manifest, MANIFEST_SCHEMA, "manifest.json")
        errors.extend(manifest_errors)

        # 检查 spec_version
        spec_ver = manifest.get("spec_version")
        if not spec_ver:
            warnings.append("manifest.json 未声明 spec_version，建议添加 \"spec_version\": \"1.0\"")
        elif spec_ver != SPEC_VERSION:
            warnings.append(f"manifest.json spec_version={spec_ver}，当前规范版本为 {SPEC_VERSION}")

        # 检查 exports 引用的文件是否存在
        exports = manifest.get("exports", {})
        for key, rel_path in exports.items():
            if isinstance(rel_path, str) and not (data_dir / rel_path).exists():
                warnings.append(f"manifest.exports.{key} 引用的文件不存在: {rel_path}")
            elif isinstance(rel_path, list):
                for p in rel_path:
                    if isinstance(p, str) and not (data_dir / p).exists():
                        warnings.append(f"manifest.exports.{key} 引用的文件不存在: {p}")

    # ── 3. 验证 variables.json ──
    variables, err = _load_json_safe(data_dir / "variables.json")
    if err:
        errors.append(err)
    else:
        var_errors = _validate_json_against_schema(variables, VARIABLES_SCHEMA, "variables.json")
        errors.extend(var_errors)

        # 额外检查：是否有变量缺少 rangeGlobal
        for i, var in enumerate(variables.get("variables", [])):
            if "rangeGlobal" not in var:
                warnings.append(f"variables.json.variables[{i}] ({var.get('name', '?')}): 缺少 rangeGlobal 字段")

    # ── 4. 验证 datasets.json（可选） ──
    datasets_path = data_dir / "datasets.json"
    if datasets_path.exists():
        datasets, err = _load_json_safe(datasets_path)
        if err:
            warnings.append(err)
        else:
            ds_errors = _validate_json_against_schema(datasets, DATASETS_SCHEMA, "datasets.json")
            # datasets.json 的问题降级为 warning（可选文件）
            warnings.extend(ds_errors)
    else:
        warnings.append("缺少可选文件: datasets.json（建议提供以获得更精确的网格分析）")

    # ── 5. 检查可选目录 ──
    for dir_name in OPTIONAL_DIRS:
        dir_path = data_dir / dir_name
        if not dir_path.exists():
            # 只对顶级可选目录发 warning
            if "/" not in dir_name:
                warnings.append(f"缺少可选目录: {dir_name}/")

    # ── 6. 检查图片文件 ──
    images_dir = data_dir / "images"
    if images_dir.exists():
        png_count = len(list(images_dir.rglob("*.png")))
        jpg_count = len(list(images_dir.rglob("*.jpg")))
        if png_count + jpg_count == 0:
            warnings.append("images/ 目录存在但未包含任何图片文件")

    # ── 7. automation/ops 检查 ──
    ops_dir = data_dir / "automation" / "ops"
    if ops_dir.exists():
        for op_dir in ops_dir.iterdir():
            if op_dir.is_dir():
                if not (op_dir / "context.json").exists():
                    warnings.append(f"automation/ops/{op_dir.name}/ 缺少 context.json")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def get_spec_summary() -> Dict[str, Any]:
    """返回规范摘要（供 API 接口使用）"""
    return {
        "spec_version": SPEC_VERSION,
        "description": "SimuVision DataPackage Spec — 仿真数据包标准格式规范",
        "required_files": REQUIRED_FILES,
        "optional_files": OPTIONAL_FILES,
        "optional_dirs": OPTIONAL_DIRS,
        "schemas": {
            "manifest.json": MANIFEST_SCHEMA,
            "variables.json": VARIABLES_SCHEMA,
            "datasets.json": DATASETS_SCHEMA
        },
        "directory_structure": {
            "<root>/": "数据包根目录",
            "manifest.json": "★ 必须 — 数据包清单，声明 spec_version 和元信息",
            "variables.json": "★ 必须 — 流场变量列表（含语义推测和数值范围）",
            "datasets.json": "可选 — 网格块详情（维度、拓扑、边界）",
            "hierarchy.json": "可选 — 数据层次结构",
            "images/": "可选 — 可视化截图",
            "images/geometry/": "几何结构概览图",
            "images/mesh/": "网格结构概览图",
            "images/variables/": "变量云图",
            "automation/ops/": "可选 — 后处理操作记录",
            "automation/ops/<op>/context.json": "操作上下文",
            "automation/ops/<op>/result.json": "操作结果",
            "automation/ops/<op>/images/": "操作截图",
            "views/view_presets.json": "可选 — 视角预设"
        }
    }
