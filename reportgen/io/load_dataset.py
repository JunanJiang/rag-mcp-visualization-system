"""数据包解析入口

通过适配器模式自动检测并解析不同格式的数据包。
当前支持：SimuVision/Plot3D 格式。
扩展新格式只需在 adapters/ 目录下添加适配器并注册即可。
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .adapters import auto_detect_adapter, list_supported_formats

logger = logging.getLogger(__name__)


def load_dataset_facts(data_dir: str, *, skip_validation: bool = False) -> Dict[str, Any]:
    """
    加载数据包并生成确定性事实（自动检测格式）
    
    Args:
        data_dir: 数据包目录路径（已解压）
        skip_validation: 跳过 DataPackage Spec 合规验证
        
    Returns:
        标准化的 facts 字典
        
    Raises:
        ValueError: 无法识别数据包格式或验证未通过
    """
    data_path = Path(data_dir)
    
    if not data_path.exists() or not data_path.is_dir():
        raise ValueError(f"数据包路径不存在或不是目录: {data_dir}")
    
    # 解析前先做 DataPackage Spec 合规验证
    validation_result: Optional[Dict] = None
    if not skip_validation:
        try:
            from .datapackage_spec import validate_data_package
            validation_result = validate_data_package(str(data_path))
            if validation_result.get("errors"):
                error_msgs = "; ".join(validation_result["errors"][:5])
                logger.warning(f"数据包验证存在阻断性错误: {error_msgs}")
            if validation_result.get("warnings"):
                for w in validation_result["warnings"][:3]:
                    logger.info(f"数据包验证警告: {w}")
        except Exception as e:
            logger.warning(f"DataPackage Spec 验证跳过: {e}")
    
    adapter = auto_detect_adapter(data_path)
    
    try:
        facts = adapter.parse(data_path)
    except Exception as e:
        raise ValueError(f"数据包解析失败 ({adapter.format_name}): {e}") from e
    
    if validation_result:
        facts["_validation"] = validation_result
    
    return facts


def parse_data_package(data_path: Path) -> Dict[str, Any]:
    """
    解析数据包（简化版本，用于 API）
    
    Args:
        data_path: 数据包目录路径
        
    Returns:
        标准化的 facts 字典
    """
    return load_dataset_facts(str(data_path))
