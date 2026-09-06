"""槽位填充冒烟测试"""

import pytest


def test_dry_run_client():
    """测试 Dry-run 客户端"""
    from reportgen.llm.deepseek_client import DryRunClient
    
    client = DryRunClient()
    
    assert client.is_available
    assert client.model == "dry-run"
    
    # 测试 chat
    result = client.chat([{"role": "user", "content": "test"}])
    assert "[DRY-RUN]" in result["content"]
    assert result["error"] is None


def test_dry_run_fill_slot():
    """测试 Dry-run 槽位填充"""
    from reportgen.llm.deepseek_client import DryRunClient
    
    client = DryRunClient()
    
    facts = {"variables": [{"name": "F1V1"}]}
    cards = [{"id": "card-001", "title": "Test Card"}]
    
    result = client.fill_slot(
        slot_id="test_slot",
        slot_instruction="测试指令",
        facts=facts,
        retrieved_cards=cards
    )
    
    assert "[待填充]" in result["text"]
    assert "card-001" in result["cards_used"]
    assert result["error"] is None


def test_slot_instructions():
    """测试槽位指令配置"""
    from reportgen.llm.prompts import SLOT_INSTRUCTIONS, get_slot_prompt
    
    # 检查必要的槽位都已定义
    required_slots = [
        "analysis_purpose_1",
        "analysis_purpose_2",
        "engine_model",
        "conclusion"
    ]
    
    for slot_id in required_slots:
        assert slot_id in SLOT_INSTRUCTIONS
        
        # 测试 get_slot_prompt
        prompt = get_slot_prompt(slot_id, {})
        assert "instruction" in prompt
        assert "max_chars" in prompt
        assert "query" in prompt


def test_variable_name_map():
    """测试变量名称映射"""
    from reportgen.llm.prompts import get_variable_chinese_name
    
    assert get_variable_chinese_name("density") == "密度"
    assert get_variable_chinese_name("MomentumX") == "X方向动量"
    assert get_variable_chinese_name("unknown_var") == "unknown_var"


def test_air_properties_markdown():
    """测试空气物性表生成"""
    from reportgen.llm.prompts import get_air_properties_markdown
    
    md = get_air_properties_markdown()
    
    assert "密度" in md
    assert "1.225" in md
    assert "kg/m³" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
