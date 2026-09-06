"""策略构建器"""

from typing import Dict, List, Any
from ..draft.schema import Policy


class PolicyBuilder:
    """策略构建器"""
    
    @staticmethod
    def build_from_answers(answers: Dict[str, Any]) -> Policy:
        """从问答结果构建仿真报告策略。"""
        return PolicyBuilder._build_simulation(answers)

    @staticmethod
    def _build_simulation(answers: Dict[str, Any]) -> Policy:
        """从仿真模式问答构建策略（原有逻辑）"""
        policy = Policy(mode="simulation")
        
        # 领域
        if "Q1_domain" in answers:
            policy.domain = answers["Q1_domain"]
        
        # 目的
        if "Q2_purpose" in answers:
            policy.purpose = answers["Q2_purpose"]
        
        # 物理现象
        if "Q3_phenomena" in answers:
            policy.phenomena = answers["Q3_phenomena"] if isinstance(answers["Q3_phenomena"], list) else [answers["Q3_phenomena"]]
        
        # 推断强度
        if "Q4_inference" in answers:
            policy.inference_level = answers["Q4_inference"]
        
        # 知识来源
        if "Q5_knowledge_source" in answers:
            source = answers["Q5_knowledge_source"]
            policy.enable_web_search = source in ["web_and_rag", "web_only"]
            policy.enable_rag = source in ["web_and_rag", "rag_only"]
        
        # 术语偏好
        if "Q6_terminology" in answers:
            policy.terminology = {"var_style": answers["Q6_terminology"]}
        
        # 报告模板
        if "template_id" in answers and answers["template_id"]:
            policy.template_id = answers["template_id"]
        
        # 三层知识库开关（允许一键生成等路径直接传开关）
        if "enable_system_kb" in answers:
            policy.enable_system_kb = bool(answers["enable_system_kb"])
        if "enable_personal_kb" in answers:
            policy.enable_personal_kb = bool(answers["enable_personal_kb"])
        if "enable_org_kb" in answers:
            policy.enable_org_kb = bool(answers["enable_org_kb"])
        
        return policy
    
    @staticmethod
    def get_search_keywords(policy: Policy) -> List[str]:
        """根据策略生成搜索关键词"""
        keywords = []
        
        # 领域关键词（面向 SimuVision Desktop 支持的仿真场景）
        domain_keywords = {
            "external_aero": ["外流", "绕流", "翼型", "升力", "阻力", "压力系数", "Cp", "激波", "马赫数"],
            "turbomachinery": ["叶轮", "压气机", "涡轮", "叶栅", "级性能", "效率", "总压比", "质量平均"],
            "internal_flow": ["内流", "管道", "进气道", "喷管", "阀门", "压降", "流量"],
            "heat_transfer": ["传热", "热防护", "壁面热流", "斯坦顿数", "恢复系数", "气动加热"],
            "structural": ["应力", "应变", "位移", "变形", "Von Mises", "Abaqus"],
            "general_cfd": ["流体", "仿真", "CFD", "流场"],
        }
        
        if policy.domain in domain_keywords:
            keywords.extend(domain_keywords[policy.domain])
        
        # 现象关键词
        phenomena_keywords = {
            "flow_separation": ["流动分离", "分离点", "分离区"],
            "turbulence": ["湍流", "湍流模型", "雷诺数"],
            "shock_wave": ["激波", "马赫数", "可压缩"],
            "heat_transfer": ["传热", "导热", "对流换热"],
            "mixing": ["混合", "扩散", "均匀性"],
            "combustion": ["燃烧", "反应", "火焰"],
            "multiphase": ["多相流", "气液", "两相"],
            "boundary_layer": ["边界层", "壁面", "y+"],
            "vortex": ["涡旋", "漩涡", "涡量"],
            "pressure_loss": ["压力损失", "压降", "阻力"]
        }
        
        for phenom in policy.phenomena:
            if phenom in phenomena_keywords:
                keywords.extend(phenomena_keywords[phenom])
        
        return list(set(keywords))
    
    @staticmethod
    def get_reject_strategy(reject_reason: str) -> Dict[str, Any]:
        """根据拒绝原因返回改写策略"""
        strategies = {
            "too_certain": {
                "action": "downgrade_wording",
                "description": "降级措辞，使用更保守的表述",
                "modifications": [
                    "将'是'改为'可能是'",
                    "将'表明'改为'提示'",
                    "添加'初步分析显示'等限定词",
                    "强化缺失项声明"
                ]
            },
            "wrong_terminology": {
                "action": "fix_terminology",
                "description": "按策略修正术语",
                "modifications": [
                    "统一变量命名风格",
                    "使用领域标准术语"
                ]
            },
            "insufficient_missing": {
                "action": "add_missing_info",
                "description": "补充缺失信息说明",
                "modifications": [
                    "列出缺失的关键信息",
                    "说明因缺失信息无法得出的结论"
                ]
            },
            "no_external_ref": {
                "action": "remove_external",
                "description": "移除外部引用",
                "modifications": [
                    "删除网络搜索引用",
                    "仅保留数据包内的信息",
                    "添加'仅基于数据包'声明"
                ]
            },
            "wrong_focus": {
                "action": "change_focus",
                "description": "调整关注点",
                "modifications": [
                    "重新对齐用户关注的物理现象",
                    "突出用户指定的重点"
                ]
            }
        }
        
        return strategies.get(reject_reason, {
            "action": "general_rewrite",
            "description": "一般性改写",
            "modifications": []
        })
