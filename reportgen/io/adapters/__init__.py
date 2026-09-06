"""数据包适配器注册表

通过适配器模式支持多种数据包格式。
新增格式只需实现 DataPackageAdapter 接口并在此注册即可。
"""

from pathlib import Path
from typing import Dict, Any, Optional

from .base import DataPackageAdapter
from .simuvision import SimuVisionAdapter

# 适配器注册表（按优先级排列，先匹配先使用）
ADAPTER_REGISTRY: list[DataPackageAdapter] = [
    SimuVisionAdapter(),
]


def auto_detect_adapter(data_dir: Path) -> DataPackageAdapter:
    """自动检测数据包格式并返回对应适配器
    
    Args:
        data_dir: 数据包目录
        
    Returns:
        匹配的适配器实例
        
    Raises:
        ValueError: 无法识别数据包格式
    """
    for adapter in ADAPTER_REGISTRY:
        if adapter.detect(data_dir):
            return adapter
    
    # 列出目录内容帮助诊断
    contents = [f.name for f in data_dir.iterdir()] if data_dir.exists() else []
    raise ValueError(
        f"无法识别数据包格式。目录 '{data_dir}' 中包含: {contents}。"
        f"当前支持的格式: {[a.format_name for a in ADAPTER_REGISTRY]}"
    )


def list_supported_formats() -> list[dict]:
    """列出所有已注册的数据包格式"""
    return [
        {
            "name": a.format_name,
            "description": a.format_description,
        }
        for a in ADAPTER_REGISTRY
    ]


__all__ = [
    "DataPackageAdapter",
    "SimuVisionAdapter",
    "ADAPTER_REGISTRY",
    "auto_detect_adapter",
    "list_supported_formats",
]
