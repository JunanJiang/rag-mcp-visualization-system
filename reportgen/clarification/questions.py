"""Clarification问题生成器"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ..draft.schema import DOMAINS, PHENOMENA, PURPOSES


@dataclass
class Question:
    """问题"""
    id: str
    question: str
    type: str  # single_choice, multi_choice, confirm
    options: List[Dict[str, str]] = field(default_factory=list)
    why_needed: str = ""
    default_value: Any = None
    required: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "type": self.type,
            "options": self.options,
            "why_needed": self.why_needed,
            "default_value": self.default_value,
            "required": self.required
        }


class ClarificationGenerator:
    """Clarification问题生成器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def generate_questions(
        self,
        facts: Dict[str, Any],
        use_llm: bool = False,
        mode: str = "simulation"
    ) -> List[Question]:
        """生成 Clarification 问题。"""
        if use_llm and self.llm_client:
            return self._generate_with_llm(facts)
        
        return self._generate_default_questions(facts)
    
    def _generate_default_questions(self, facts: Dict[str, Any]) -> List[Question]:
        """生成默认问题（不依赖LLM）"""
        questions = []
        
        # Q1: 领域选择（面向 SimuVision Desktop 支持的仿真场景）
        domain_options = [{"id": d["id"], "label": d["name"], "description": d["description"]} for d in DOMAINS]
        domain_options.append({"id": "other", "label": "其他（请在下方说明）", "description": "其他未列出的领域"})
        
        questions.append(Question(
            id="Q1_domain",
            question="这是什么领域的仿真分析？",
            type="single_choice",
            options=domain_options,
            why_needed="确定领域后，可以搜索更准确的背景知识和术语解释",
            default_value="general_cfd",
            required=True
        ))
        
        # Q1.1: 其他领域说明（条件显示）
        questions.append(Question(
            id="Q1_1_domain_other",
            question="请说明具体领域",
            type="text",
            options=[],
            why_needed="用于自定义领域",
            default_value="",
            required=False
        ))
        
        # Q2: 报告目的
        purpose_options = [{"id": p["id"], "label": p["name"], "description": p["description"]} for p in PURPOSES]
        purpose_options.append({"id": "other", "label": "其他（请在下方说明）", "description": "其他未列出的目的"})
        
        questions.append(Question(
            id="Q2_purpose",
            question="本次报告的主要目的是什么？",
            type="single_choice",
            options=purpose_options,
            why_needed="明确目的可以调整报告的措辞和重点",
            default_value="show",
            required=True
        ))
        
        # Q2.1: 其他目的说明
        questions.append(Question(
            id="Q2_1_purpose_other",
            question="请说明具体目的",
            type="text",
            options=[],
            why_needed="用于自定义目的",
            default_value="",
            required=False
        ))
        
        # Q3: 关注的物理现象
        phenomena_options = [{"id": p["id"], "label": p["name"], "description": p["description"]} for p in PHENOMENA]
        phenomena_options.append({"id": "other", "label": "其他（请在备注中说明）", "description": "其他未列出的现象"})
        
        questions.append(Question(
            id="Q3_phenomena",
            question="本次分析关注哪些物理现象？（可多选）",
            type="multi_choice",
            options=phenomena_options,
            why_needed="帮助聚焦分析内容，搜索相关的评判标准",
            default_value=[],
            required=False
        ))
        
        # Q3.1: 其他现象说明
        questions.append(Question(
            id="Q3_1_phenomena_other",
            question="请说明其他关注的物理现象",
            type="text",
            options=[],
            why_needed="用于自定义物理现象",
            default_value="",
            required=False
        ))
        
        # Q4: 推断强度
        questions.append(Question(
            id="Q4_inference",
            question="对于数据包中没有明确标注的信息，报告应该如何处理？",
            type="single_choice",
            options=[
                {"id": "describe_only", "label": "仅描述数据", "description": "只描述数据包中的原始数据，不做任何推断"},
                {"id": "may_infer", "label": "可适度推断", "description": "可以根据数据特征进行合理推断，但需标注推断依据"}
            ],
            why_needed="控制报告的保守程度",
            default_value="describe_only",
            required=True
        ))
        
        # Q5: 知识来源
        questions.append(Question(
            id="Q5_knowledge_source",
            question="是否启用网络搜索来补充背景知识？",
            type="single_choice",
            options=[
                {"id": "web_and_rag", "label": "网络搜索 + 本地知识库", "description": "同时使用网络搜索和本地知识库"},
                {"id": "web_only", "label": "仅网络搜索", "description": "只使用网络搜索获取背景知识"},
                {"id": "rag_only", "label": "仅本地知识库", "description": "只使用本地知识库"},
                {"id": "none", "label": "不使用外部知识", "description": "仅基于数据包内容生成报告"}
            ],
            why_needed="控制背景知识的来源",
            default_value="web_and_rag",
            required=True
        ))
        
        # Q6: 术语偏好（可选）
        questions.append(Question(
            id="Q6_terminology",
            question="变量名称显示偏好？",
            type="single_choice",
            options=[
                {"id": "original", "label": "保持原始名称", "description": "使用数据包中的原始变量名（如F1V1）"},
                {"id": "chinese", "label": "中文名称", "description": "转换为中文物理量名称（如密度、动量）"},
                {"id": "english", "label": "英文名称", "description": "转换为英文物理量名称（如Density, Momentum）"},
                {"id": "symbolic", "label": "符号表示", "description": "使用物理符号（如ρ, ρu, ρv）"}
            ],
            why_needed="统一报告中的变量命名风格",
            default_value="chinese",
            required=False
        ))
        
        return questions
    
    def _generate_with_llm(self, facts: Dict[str, Any]) -> List[Question]:
        """使用LLM生成问题"""
        # 先获取默认问题作为基础
        default_questions = self._generate_default_questions(facts)
        
        if not self.llm_client:
            return default_questions
        
        # 构建prompt
        facts_summary = self._summarize_facts(facts)
        
        prompt = f"""你是"文档生成提问器"。你的目标是在开始写作之前，提出少量必要的问题，让用户确认写作语境与口径。

输入数据摘要：
{facts_summary}

规则：
1. 最多提出5个问题
2. 问题必须是选择题或确认题
3. 只允许问：语境、报告目的、关注点、口径策略、术语偏好
4. 严禁询问任何数值数据或工况参数

请根据数据特征，判断是否需要额外的澄清问题。如果默认问题已经足够，回复"使用默认问题"。"""

        try:
            response = self.llm_client.chat(prompt)
            
            if "使用默认问题" in response:
                return default_questions
            
            # 解析LLM响应，添加额外问题
            # 这里简化处理，实际需要更复杂的解析
            return default_questions
            
        except Exception as e:
            return default_questions
    
    def _summarize_facts(self, facts: Dict[str, Any]) -> str:
        """生成facts摘要"""
        manifest = facts.get("manifest", {})
        variables = facts.get("variables", [])
        
        summary = []
        
        # 数据类型
        dataset_type = manifest.get("datasetType", "Unknown")
        summary.append(f"数据类型: {dataset_type}")
        
        # 网格信息
        block_count = manifest.get("blockCount", 0)
        total_points = manifest.get("totalPoints", 0)
        summary.append(f"网格: {block_count}个块, {total_points}个节点")
        
        # 变量信息
        if variables:
            var_names = [v.get("name", "") for v in variables]
            summary.append(f"变量: {', '.join(var_names)}")
        
        return "\n".join(summary)
    
    def parse_answers(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        """解析用户回答，转换为policy参数"""
        policy_params = {}
        
        # Q1: 领域
        if "Q1_domain" in answers:
            policy_params["domain"] = answers["Q1_domain"]
        
        # Q2: 目的
        if "Q2_purpose" in answers:
            policy_params["purpose"] = answers["Q2_purpose"]
        
        # Q3: 物理现象
        if "Q3_phenomena" in answers:
            policy_params["phenomena"] = answers["Q3_phenomena"]
        
        # Q4: 推断强度
        if "Q4_inference" in answers:
            policy_params["inference_level"] = answers["Q4_inference"]
        
        # Q5: 知识来源
        if "Q5_knowledge_source" in answers:
            source = answers["Q5_knowledge_source"]
            policy_params["enable_web_search"] = source in ["web_and_rag", "web_only"]
            policy_params["enable_rag"] = source in ["web_and_rag", "rag_only"]
        
        # Q6: 术语偏好
        if "Q6_terminology" in answers:
            policy_params["terminology"] = {"var_style": answers["Q6_terminology"]}
        
        return policy_params
