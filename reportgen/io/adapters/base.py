"""数据包适配器抽象基类

定义了所有数据包适配器必须实现的标准接口。
适配器负责将特定格式的数据包解析为统一的 facts 字典结构。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List


class DataPackageAdapter(ABC):
    """数据包适配器抽象基类
    
    每种数据包格式（如 SimuVision/Plot3D、OpenFOAM、Fluent 等）
    需要实现此接口，将原始数据解析为标准化的 facts 字典。
    
    标准化 facts 字典结构：
    {
        "data_dir": str,               # 数据包路径
        "manifest": {                   # 元信息
            "app_name": str,
            "app_version": str,
            "dataset_type": str,
            "dataset_name": str,
            "block_count": int,
            "total_points": int,
            "total_cells": int,
            ...
        },
        "variables": [                  # 变量列表
            {
                "name": str,
                "guess_variableName": str,  # 语义推测
                "components": int,
                "location": str,
                "range_min": float | None,
                "range_max": float | None,
            },
            ...
        ],
        "datasets": {                   # 数据集/网格信息
            "block_count": int,
            "blocks": [...],
            "total_points": int,
            "total_cells": int,
            ...
        },
        "images": {                     # 可视化图片（按类别）
            "geometry": [str, ...],
            "mesh": [str, ...],
            "variables": [str, ...],
            ...
        },
        "hierarchy": dict | None,       # 数据层次结构
        "automation_ops": [dict, ...],  # 自动化操作记录
        "view_presets": [dict, ...],    # 视角预设
    }
    """

    @property
    @abstractmethod
    def format_name(self) -> str:
        """适配器支持的格式名称（如 'SimuVision/Plot3D'）"""
        ...

    @property
    @abstractmethod
    def format_description(self) -> str:
        """格式的简短描述"""
        ...

    @abstractmethod
    def detect(self, data_dir: Path) -> bool:
        """检测给定目录是否为本适配器支持的数据包格式
        
        Args:
            data_dir: 数据包目录路径
            
        Returns:
            True 表示该目录匹配本适配器的格式
        """
        ...

    @abstractmethod
    def parse(self, data_dir: Path) -> Dict[str, Any]:
        """解析数据包，返回标准化的 facts 字典
        
        Args:
            data_dir: 数据包目录路径
            
        Returns:
            符合标准化结构的 facts 字典
            
        Raises:
            FileNotFoundError: 必要文件缺失
            ValueError: 数据格式错误
        """
        ...

    def get_required_files(self) -> List[str]:
        """返回该格式必需的文件列表（用于验证和提示）
        
        Returns:
            必需文件名列表
        """
        return []
