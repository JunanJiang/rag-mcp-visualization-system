"""SimuVision Desktop 数据包适配器

解析由 SimuVision-Desktop 可视化工具导出的 Plot3D 格式数据包。
数据包包含 manifest.json、datasets.json、variables.json 等 JSON 元信息文件，
以及 images/ 和 automation/ 目录下的可视化截图。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import DataPackageAdapter


import logging as _logging

_logger = _logging.getLogger(__name__)


def _load_json_safe(file_path: Path, *, label: str = "") -> Optional[Dict]:
    """安全加载 JSON 文件。区分文件缺失（正常）和文件损坏（警告）。"""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        _logger.warning(f"JSON 解析失败 ({label or file_path.name}): {e}")
        return None
    except UnicodeDecodeError as e:
        _logger.warning(f"编码错误 ({label or file_path.name}): {e}")
        return None


class SimuVisionAdapter(DataPackageAdapter):
    """SimuVision Desktop 导出的 Plot3D 数据包适配器
    
    识别依据：目录下存在 manifest.json 文件
    """

    @property
    def format_name(self) -> str:
        return "SimuVision/Plot3D"

    @property
    def format_description(self) -> str:
        return "SimuVision-Desktop 导出的 Plot3D 多块结构网格数据包（含 manifest.json）"

    def detect(self, data_dir: Path) -> bool:
        """检测目录下是否存在 manifest.json"""
        return (data_dir / "manifest.json").exists()

    def get_required_files(self) -> List[str]:
        return ["manifest.json"]

    def parse(self, data_dir: Path) -> Dict[str, Any]:
        """解析 SimuVision 数据包"""
        manifest = _load_json_safe(data_dir / "manifest.json")
        variables_data = _load_json_safe(data_dir / "variables.json")
        datasets_data = _load_json_safe(data_dir / "datasets.json")
        hierarchy = _load_json_safe(data_dir / "hierarchy.json")

        images = self._find_images(data_dir)
        automation_ops = self._parse_automation_ops(data_dir)
        view_presets = self._parse_view_presets(data_dir)

        facts: Dict[str, Any] = {
            "data_dir": str(data_dir),
            "manifest": {},
            "variables": [],
            "datasets": {},
            "images": images,
            "hierarchy": hierarchy,
            "automation_ops": automation_ops,
            "view_presets": view_presets,
        }

        # 解析 manifest
        if manifest:
            block_count_raw = manifest.get("dataset", {}).get("blockCount", 0)
            block_count = int(block_count_raw) if block_count_raw else 0

            facts["manifest"] = {
                "app_name": manifest.get("app", {}).get("name", "Simuvision"),
                "app_version": manifest.get("app", {}).get("version", "unknown"),
                "created_at": manifest.get("createdAt", ""),
                "session_id": manifest.get("sessionId", ""),
                "dataset_type": manifest.get("dataset", {}).get("datasetType", ""),
                "dataset_name": manifest.get("dataset", {}).get("datasetName", ""),
                "block_count": block_count,
                "total_points": manifest.get("dataset", {}).get("totalPoints", 0),
                "total_cells": manifest.get("dataset", {}).get("totalCells", 0),
                "source_files": manifest.get("sourceFiles", {}),
                "exports": manifest.get("exports", {}),
            }

        # 解析变量
        facts["variables"] = self._parse_variables(variables_data)

        # 解析数据集
        facts["datasets"] = self._parse_datasets(datasets_data)

        return facts

    # ── 内部解析方法 ──

    @staticmethod
    def _parse_variables(variables_data: Optional[Dict]) -> List[Dict[str, Any]]:
        """解析变量信息（防御性：处理缺失字段和类型异常）"""
        if not variables_data:
            return []
        
        raw_vars = variables_data.get("variables")
        if not isinstance(raw_vars, list):
            return []

        result = []
        for var in raw_vars:
            if not isinstance(var, dict):
                continue
            var_info = {
                "name": var.get("name", ""),
                "guess_variableName": var.get("guess_variableName", "unknown"),
                "components": var.get("components", 1),
                "location": var.get("location", ""),
                "range_min": None,
                "range_max": None,
            }
            range_global = var.get("rangeGlobal")
            if isinstance(range_global, dict):
                var_info["range_min"] = range_global.get("min")
                var_info["range_max"] = range_global.get("max")
            result.append(var_info)
        return result

    @staticmethod
    def _parse_datasets(datasets_data: Optional[Dict]) -> Dict[str, Any]:
        """解析数据集信息，统计网格特征（防御性：处理 null/非法类型）"""
        if not datasets_data:
            return {}

        blocks = datasets_data.get("datasets")
        if not isinstance(blocks, list):
            return {}

        dims_list = []
        points_list = []
        cells_list = []

        parsed_blocks = []
        for i, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            topo = block.get("topology") or {}
            if not isinstance(topo, dict):
                topo = {}

            dims_raw = topo.get("dims")
            dims_vals = []
            if isinstance(dims_raw, dict):
                dims_vals = dims_raw.get("values", [])
            if not isinstance(dims_vals, list):
                dims_vals = []
            
            pts = topo.get("points", 0)
            cls = topo.get("cells", 0)
            pts = pts if isinstance(pts, (int, float)) else 0
            cls = cls if isinstance(cls, (int, float)) else 0

            if dims_vals:
                dims_list.append(dims_vals)
            points_list.append(pts)
            cells_list.append(cls)

            parsed_blocks.append({
                "name": block.get("name", f"Block_{i}"),
                "blockIndex": block.get("blockIndex", i),
                "dims": dims_vals,
                "points": pts,
                "cells": cls,
                "type": block.get("type", "unknown"),
            })

        def _dims_volume(x):
            if isinstance(x, list) and len(x) == 3:
                try:
                    return x[0] * x[1] * x[2]
                except (TypeError, IndexError):
                    return 0
            return 0

        valid_dims = [d for d in dims_list if _dims_volume(d) > 0]

        return {
            "block_count": len(parsed_blocks),
            "blocks": parsed_blocks,
            "total_points": sum(points_list),
            "total_cells": sum(cells_list),
            "dims_summary": {
                "all_dims": dims_list,
                "max_dims": max(valid_dims, key=_dims_volume) if valid_dims else [],
                "min_dims": min(valid_dims, key=_dims_volume) if valid_dims else [],
            },
        }

    @staticmethod
    def _find_images(data_dir: Path) -> Dict[str, List[str]]:
        """查找数据包中的所有图片"""
        images: Dict[str, List[str]] = {
            "geometry": [],
            "mesh": [],
            "variables": [],
            "automation": [],
            "blocks": [],
            "geometry_blocks": [],
            "mesh_blocks": [],
        }

        images_dir = data_dir / "images"
        if images_dir.exists():
            geo_dir = images_dir / "geometry"
            if geo_dir.exists():
                images["geometry"] = [str(p) for p in geo_dir.glob("*.png")]
                geo_blocks_dir = geo_dir / "blocks"
                if geo_blocks_dir.exists():
                    images["geometry_blocks"] = [str(p) for p in sorted(geo_blocks_dir.glob("*.png"))]

            mesh_dir = images_dir / "mesh"
            if mesh_dir.exists():
                images["mesh"] = [str(p) for p in mesh_dir.glob("*.png")]
                mesh_blocks_dir = mesh_dir / "blocks"
                if mesh_blocks_dir.exists():
                    images["mesh_blocks"] = [str(p) for p in sorted(mesh_blocks_dir.glob("*.png"))]

            var_dir = images_dir / "variables"
            if var_dir.exists():
                images["variables"] = [str(p) for p in var_dir.glob("*.png")]

        automation_dir = data_dir / "automation" / "ops"
        if automation_dir.exists():
            for op_dir in automation_dir.iterdir():
                if op_dir.is_dir():
                    op_images_dir = op_dir / "images"
                    if op_images_dir.exists():
                        for img in op_images_dir.glob("*.png"):
                            images["automation"].append(str(img))
                    for img in op_dir.glob("*.png"):
                        images["automation"].append(str(img))

        return images

    @staticmethod
    def _parse_automation_ops(data_dir: Path) -> List[Dict[str, Any]]:
        """解析 automation/ops 目录中的后处理操作"""
        ops: List[Dict[str, Any]] = []
        ops_dir = data_dir / "automation" / "ops"
        if not ops_dir.exists():
            return ops

        for op_dir in sorted(ops_dir.iterdir()):
            if not op_dir.is_dir():
                continue

            op_info: Dict[str, Any] = {
                "folder": op_dir.name,
                "operation_type": None,
                "variable_name": None,
                "images": [],
            }

            ctx = _load_json_safe(op_dir / "context.json")
            if ctx:
                op_info["operation_type"] = ctx.get("operation_type")
                op_info["variable_name"] = ctx.get("parameters", {}).get("variable_name")
                op_info["parameters"] = ctx.get("parameters", {})

            result = _load_json_safe(op_dir / "result.json")
            if result:
                op_info["success"] = result.get("success", False)
                op_info["images"] = result.get("image_files", [])

            ops.append(op_info)
        return ops

    @staticmethod
    def _parse_view_presets(data_dir: Path) -> List[Dict[str, Any]]:
        """解析视角预设"""
        data = _load_json_safe(data_dir / "views" / "view_presets.json")
        if not data:
            return []
        return data.get("presets", [])
