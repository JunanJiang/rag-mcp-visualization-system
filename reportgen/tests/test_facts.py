"""测试数据包解析和事实构建"""

import json
import tempfile
from pathlib import Path

import pytest


def test_load_json_safe():
    """测试安全加载 JSON"""
    from reportgen.io.adapters.simuvision import _load_json_safe as load_json_safe
    
    # 创建临时 JSON 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({"test": "value"}, f)
        temp_path = Path(f.name)
    
    try:
        result = load_json_safe(temp_path)
        assert result == {"test": "value"}
    finally:
        temp_path.unlink()


def test_load_json_safe_missing_file():
    """测试加载不存在的文件"""
    from reportgen.io.adapters.simuvision import _load_json_safe as load_json_safe
    
    result = load_json_safe(Path("/nonexistent/file.json"))
    assert result is None


def test_parse_variables():
    """测试变量解析"""
    from reportgen.io.adapters.simuvision import SimuVisionAdapter
    parse_variables = SimuVisionAdapter._parse_variables
    
    variables_data = {
        "variables": [
            {
                "name": "F1V1",
                "guess_variableName": "density",
                "components": 1,
                "location": "PointData",
                "rangeGlobal": {"min": 0.1, "max": 3.0}
            }
        ]
    }
    
    result = parse_variables(variables_data)
    
    assert len(result) == 1
    assert result[0]["name"] == "F1V1"
    assert result[0]["guess_variableName"] == "density"
    assert result[0]["range_min"] == 0.1
    assert result[0]["range_max"] == 3.0


def test_parse_datasets():
    """测试数据集解析"""
    from reportgen.io.adapters.simuvision import SimuVisionAdapter
    parse_datasets = SimuVisionAdapter._parse_datasets
    
    datasets_data = {
        "datasets": [
            {
                "blockIndex": 0,
                "name": "Block_1",
                "topology": {
                    "dims": {"values": [10, 20, 30]},
                    "points": 6000,
                    "cells": 5000
                },
                "type": "vtkStructuredGrid"
            }
        ]
    }
    
    result = parse_datasets(datasets_data)
    
    assert result["block_count"] == 1
    assert result["total_points"] == 6000
    assert result["total_cells"] == 5000
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["dims"] == [10, 20, 30]


def test_generate_variables_summary():
    """测试变量摘要生成"""
    from reportgen.pipeline.build_facts import generate_variables_summary
    
    variables = [
        {"name": "F1V1", "guess_variableName": "density", "range_min": 0.1, "range_max": 3.0}
    ]
    
    result = generate_variables_summary(variables)
    
    assert result["count"] == 1
    assert len(result["list"]) == 1
    assert result["list"][0]["name"] == "F1V1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
