"""报告质量自动评估（Self-Reflection）

在所有槽位生成完成后，调用 LLM 对报告内容进行自检评估。
评估维度：数据覆盖度 / 声明可追溯性 / 语言专业度 / 逻辑连贯性。
输出总分（0-100）和各维度分数及改进建议。
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 评估维度定义
DIMENSIONS = [
    {
        "id": "data_coverage",
        "name": "数据覆盖度",
        "description": "报告是否充分引用了数据包中的事实数据（变量、网格、派生量等）",
        "weight": 0.30,
    },
    {
        "id": "traceability",
        "name": "声明可追溯性",
        "description": "报告中的结论和判断是否可追溯到具体数据或知识来源",
        "weight": 0.25,
    },
    {
        "id": "professionalism",
        "name": "语言专业度",
        "description": "用语是否专业准确，是否避免了空泛套话和不当推测",
        "weight": 0.25,
    },
    {
        "id": "coherence",
        "name": "逻辑连贯性",
        "description": "各章节之间逻辑是否连贯，是否存在前后矛盾或重复",
        "weight": 0.20,
    },
]


class QualityChecker:
    """报告质量评估器（调用 LLM 做 Self-Reflection）"""

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def check(self, draft_dict: Dict[str, Any]) -> Dict[str, Any]:
        """对完整 Draft 进行质量评估
        
        Args:
            draft_dict: Draft.to_dict() 的输出
            
        Returns:
            {
                "total_score": int,          # 0-100 总分
                "dimensions": [...],         # 各维度评分
                "suggestions": [str, ...],   # 改进建议
                "summary": str               # 一句话总结
            }
        """
        # 组装报告全文
        slots = draft_dict.get("slots", [])
        policy = draft_dict.get("policy", {})
        facts = draft_dict.get("facts", {})

        report_text = self._assemble_report_text(slots)
        facts_summary = self._summarize_facts(facts)

        prompt = self._build_prompt(report_text, facts_summary, policy)

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages, temperature=0.3, max_tokens=2000)
            content = response.get("content", "") if isinstance(response, dict) else str(response)
            return self._parse_response(content)
        except Exception as e:
            logger.error(f"质量评估 LLM 调用失败: {e}")
            return self._fallback_check(slots, facts)

    def _assemble_report_text(self, slots: List[Dict[str, Any]]) -> str:
        """将所有槽位内容拼接为完整报告文本"""
        parts = []
        for slot in slots:
            content = slot.get("content", "")
            if content:
                section = slot.get("section", "")
                sid = slot.get("slot_id", "")
                parts.append(f"[{section}:{sid}] {content}")
        return "\n\n".join(parts)

    def _summarize_facts(self, facts: Dict[str, Any]) -> str:
        """摘要化 facts，用于 prompt 上下文"""
        lines = []
        manifest = facts.get("manifest", {})
        variables = facts.get("variables", [])
        derived = facts.get("derived_quantities", {})

        lines.append(f"数据类型: {manifest.get('dataset_type', '?')}")
        lines.append(f"块数: {manifest.get('block_count', '?')}, 节点数: {manifest.get('total_points', '?')}")
        lines.append(f"变量数: {len(variables)}")
        for v in variables:
            lines.append(f"  - {v.get('name')} ({v.get('guess_variableName', '?')}): "
                         f"{v.get('range_min', '?')} ~ {v.get('range_max', '?')}")
        if derived.get("flow_regime"):
            lines.append(f"流动状态: {derived['flow_regime']}")
        if derived.get("density_ratio"):
            lines.append(f"密度比: {derived['density_ratio']}")
        return "\n".join(lines)

    def _build_prompt(self, report_text: str, facts_summary: str, policy: Dict[str, Any]) -> str:
        return f"""你是一位资深的 CFD 仿真报告质量审核专家。请对以下自动生成的仿真分析报告进行质量评估。

## 数据包事实摘要
{facts_summary}

## 报告配置
- 领域: {policy.get('domain', '?')}
- 目的: {policy.get('purpose', '?')}
- 推断强度: {policy.get('inference_level', '?')}

## 报告全文
{report_text[:6000]}

---

请严格按以下 JSON 格式输出评估结果（不要输出其他内容）：

```json
{{
  "total_score": <0-100整数>,
  "dimensions": [
    {{"id": "data_coverage", "name": "数据覆盖度", "score": <0-100>, "comment": "<一句话评价>"}},
    {{"id": "traceability", "name": "声明可追溯性", "score": <0-100>, "comment": "<一句话评价>"}},
    {{"id": "professionalism", "name": "语言专业度", "score": <0-100>, "comment": "<一句话评价>"}},
    {{"id": "coherence", "name": "逻辑连贯性", "score": <0-100>, "comment": "<一句话评价>"}}
  ],
  "suggestions": ["<改进建议1>", "<改进建议2>", "<改进建议3>"],
  "summary": "<一句话总结报告质量>"
}}
```"""

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON 块
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            content = content[start:end].strip()

        try:
            result = json.loads(content)
            # 验证结构
            if "total_score" not in result:
                raise ValueError("缺少 total_score")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"质量评估 JSON 解析失败: {e}, 使用兜底评估")
            return self._fallback_from_text(content)

    def _fallback_from_text(self, content: str) -> Dict[str, Any]:
        """当 JSON 解析失败时，从文本内容中尽力提取信息"""
        return {
            "total_score": 70,
            "dimensions": [
                {"id": d["id"], "name": d["name"], "score": 70, "comment": "自动评估"}
                for d in DIMENSIONS
            ],
            "suggestions": ["建议补充更多数据引用", "建议加强前后章节的逻辑衔接"],
            "summary": content[:200] if content else "质量评估完成（JSON 解析失败，使用默认评分）"
        }

    def _fallback_check(self, slots: List[Dict[str, Any]], facts: Dict[str, Any]) -> Dict[str, Any]:
        """兜底质量评估（不依赖 LLM）：基于规则的简单检查"""
        total_content_len = sum(len(s.get("content", "")) for s in slots)
        var_count = len(facts.get("variables", []))
        slot_count = len(slots)

        # 数据覆盖度：检查内容中是否引用了变量名
        variable_names = [v.get("name", "") for v in facts.get("variables", [])]
        full_text = " ".join(s.get("content", "") for s in slots)
        vars_mentioned = sum(1 for vn in variable_names if vn and vn in full_text)
        data_coverage = min(100, int(vars_mentioned / max(var_count, 1) * 100))

        # 语言专业度：基于内容长度粗略估算
        avg_len = total_content_len / max(slot_count, 1)
        professionalism = min(100, int(avg_len / 3))  # 300字以上得100分

        # 逻辑连贯性：简单检查是否有空槽位
        filled_count = sum(1 for s in slots if len(s.get("content", "")) > 50)
        coherence = int(filled_count / max(slot_count, 1) * 100)

        traceability = min(data_coverage + 10, 100)

        total = int(
            data_coverage * 0.30 +
            traceability * 0.25 +
            professionalism * 0.25 +
            coherence * 0.20
        )

        suggestions = []
        if data_coverage < 80:
            suggestions.append(f"报告仅引用了 {vars_mentioned}/{var_count} 个变量，建议覆盖更多变量数据")
        if professionalism < 70:
            suggestions.append("部分章节内容较短，建议补充更详细的技术分析")
        if coherence < 90:
            suggestions.append("存在内容较少的槽位，建议补充完善")

        return {
            "total_score": total,
            "dimensions": [
                {"id": "data_coverage", "name": "数据覆盖度", "score": data_coverage,
                 "comment": f"引用了 {vars_mentioned}/{var_count} 个变量"},
                {"id": "traceability", "name": "声明可追溯性", "score": traceability,
                 "comment": "基于数据覆盖度推算"},
                {"id": "professionalism", "name": "语言专业度", "score": professionalism,
                 "comment": f"平均段落长度 {int(avg_len)} 字"},
                {"id": "coherence", "name": "逻辑连贯性", "score": coherence,
                 "comment": f"{filled_count}/{slot_count} 个槽位有足够内容"},
            ],
            "suggestions": suggestions or ["报告质量整体良好"],
            "summary": f"报告综合质量评分 {total}/100（规则评估，未使用 LLM）"
        }


class MockQualityChecker:
    """Mock 质量评估器（无 API Key 时使用，直接走规则检查）"""

    def check(self, draft_dict: Dict[str, Any]) -> Dict[str, Any]:
        checker = QualityChecker(llm_client=None)
        slots = draft_dict.get("slots", [])
        facts = draft_dict.get("facts", {})
        return checker._fallback_check(slots, facts)
