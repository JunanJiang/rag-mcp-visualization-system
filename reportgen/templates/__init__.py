"""报告模板系统

通过 JSON 模板定义报告的章节结构和槽位布局。
切换模板即可生成不同风格的报告，无需修改代码。

用法：
    from reportgen.templates import load_template, list_templates
    
    templates = list_templates()
    tpl = load_template("cfd_standard")
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

_TEMPLATES_DIR = Path(__file__).parent


def list_templates() -> List[Dict[str, str]]:
    """列出所有可用模板（返回摘要列表）"""
    templates = []
    for f in sorted(_TEMPLATES_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            templates.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return templates


def load_template(template_id: str) -> Dict[str, Any]:
    """加载指定 ID 的模板，返回完整 JSON 结构
    
    Args:
        template_id: 模板 ID（如 'cfd_standard'）
        
    Returns:
        模板字典
        
    Raises:
        FileNotFoundError: 模板不存在
    """
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        available = [t["id"] for t in list_templates()]
        raise FileNotFoundError(
            f"模板 '{template_id}' 不存在。可用模板: {available}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_template_slots(template_id: str, facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据模板和数据事实生成槽位规格列表
    
    处理固定槽位和动态槽位（如按变量列表展开）。
    
    Args:
        template_id: 模板 ID
        facts: 数据包事实字典
        
    Returns:
        槽位规格列表，每项包含 slot_id / placeholder_text / section / slot_type / dependencies
    """
    tpl = load_template(template_id)
    slot_specs: List[Dict[str, Any]] = []

    for section in tpl.get("sections", []):
        section_id = section.get("section_id", "")
        for slot_def in section.get("slots", []):
            slot_specs.append(_build_slot_spec(slot_def, section_id))

    for dyn in tpl.get("dynamic_sections", []):
        section_id = dyn.get("section_id", "")
        repeat_for = dyn.get("repeat_for", "")
        slot_template = dyn.get("slot_template", {})

        if repeat_for == "variables":
            variables = facts.get("variables", [])
            for var in variables:
                var_name = var.get("name", "unknown")
                expanded = _expand_slot_template(slot_template, {"name": var_name})
                slot_specs.append(_build_slot_spec(expanded, section_id))

    for section in tpl.get("static_tail_sections", []):
        section_id = section.get("section_id", "")
        for slot_def in section.get("slots", []):
            slot_specs.append(_build_slot_spec(slot_def, section_id))

    return slot_specs


def _build_slot_spec(slot_def: Dict[str, Any], section_id: str) -> Dict[str, Any]:
    """将模板中的槽位定义转换为 DraftManager 可用的 slot spec"""
    return {
        "slot_id": slot_def.get("slot_id", ""),
        "placeholder_text": slot_def.get("placeholder", slot_def.get("placeholder_text", "")),
        "section": section_id,
        "slot_type": slot_def.get("type", "text"),
        "dependencies": {
            "policy": slot_def.get("deps_policy", []),
            "facts": slot_def.get("deps_facts", []),
        },
    }


def _expand_slot_template(template: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    """展开槽位模板中的 {name} 占位符"""
    result = {}
    for key, value in template.items():
        if isinstance(value, str):
            for var_key, var_val in variables.items():
                value = value.replace(f"{{{var_key}}}", var_val)
            result[key] = value
        elif isinstance(value, list):
            result[key] = value
        else:
            result[key] = value
    return result
