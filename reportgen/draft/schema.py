"""Draft JSON数据结构定义"""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


class SlotStatus(str, Enum):
    """槽位状态"""
    PENDING = "pending"        # 待生成
    DRAFT = "draft"            # 已生成，待确认
    ACCEPTED = "accepted"      # 已接受
    REJECTED = "rejected"      # 已拒绝，待改写
    USER_EDITED = "user_edited"  # 用户编辑后锁定


class SlotType(str, Enum):
    """槽位类型"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class SourceType(str, Enum):
    """来源类型"""
    DATA = "DATA"              # 来自数据包
    EVIDENCE = "EVIDENCE"      # 来自证据（RAG/Browser）
    INFERENCE = "INFERENCE"    # 推断


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MID = "mid"
    HIGH = "high"


@dataclass
class Claim:
    """声明/断言"""
    text: str
    source: SourceType = SourceType.DATA
    risk: RiskLevel = RiskLevel.LOW
    evidence_ref: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source.value,
            "risk": self.risk.value,
            "evidence_ref": self.evidence_ref
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        return cls(
            text=data.get("text", ""),
            source=SourceType(data.get("source", "DATA")),
            risk=RiskLevel(data.get("risk", "low")),
            evidence_ref=data.get("evidence_ref", "")
        )


@dataclass
class SlotDependency:
    """槽位依赖"""
    policy: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy,
            "facts": self.facts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlotDependency":
        return cls(
            policy=data.get("policy", []),
            facts=data.get("facts", [])
        )


@dataclass
class Slot:
    """槽位"""
    slot_id: str
    placeholder_text: str
    section: str
    slot_type: SlotType = SlotType.TEXT
    status: SlotStatus = SlotStatus.PENDING
    content: str = ""
    claims: List[Claim] = field(default_factory=list)
    dependencies: SlotDependency = field(default_factory=SlotDependency)
    evidence_refs: List[str] = field(default_factory=list)
    evidence_pack: Dict[str, Any] = field(default_factory=dict)
    reject_reason: str = ""
    user_feedback: str = ""
    generated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "placeholder_text": self.placeholder_text,
            "section": self.section,
            "slot_type": self.slot_type.value,
            "status": self.status.value,
            "content": self.content,
            "claims": [c.to_dict() for c in self.claims],
            "dependencies": self.dependencies.to_dict(),
            "evidence_refs": self.evidence_refs,
            "evidence_pack": self.evidence_pack,
            "reject_reason": self.reject_reason,
            "user_feedback": self.user_feedback,
            "generated_at": self.generated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Slot":
        return cls(
            slot_id=data.get("slot_id", ""),
            placeholder_text=data.get("placeholder_text", ""),
            section=data.get("section", ""),
            slot_type=SlotType(data.get("slot_type", "text")),
            status=SlotStatus(data.get("status", "pending")),
            content=data.get("content", ""),
            claims=[Claim.from_dict(c) for c in data.get("claims", [])],
            dependencies=SlotDependency.from_dict(data.get("dependencies", {})),
            evidence_refs=data.get("evidence_refs", []),
            evidence_pack=data.get("evidence_pack", {}),
            reject_reason=data.get("reject_reason", ""),
            user_feedback=data.get("user_feedback", ""),
            generated_at=data.get("generated_at", "")
        )


@dataclass
class Policy:
    """写作策略"""
    # 生成模式
    mode: str = "simulation"
    
    # 基本信息
    domain: str = "unknown"                    # 领域：external_aero, turbomachinery, internal_flow, heat_transfer, structural, general_cfd
    context: str = "unknown"                   # 语境
    purpose: str = "show"                      # 目的：show, diagnose, compare, acceptance
    
    # 关注点
    focus: List[str] = field(default_factory=list)
    phenomena: List[str] = field(default_factory=list)  # 关注的物理现象
    
    # 口径策略
    inference_level: str = "describe_only"     # describe_only, may_infer
    missing_info_policy: str = "must_disclose" # must_disclose, optional_disclose
    
    # 术语偏好
    terminology: Dict[str, str] = field(default_factory=lambda: {
        "var_style": "original"  # original, english, symbolic, chinese
    })
    
    # 报告模板
    template_id: str = "cfd_standard"
    
    # Browser设置
    enable_web_search: bool = True
    enable_rag: bool = True
    enable_system_kb: bool = True
    enable_personal_kb: bool = True
    enable_org_kb: bool = True
    trusted_domains: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "domain": self.domain,
            "context": self.context,
            "purpose": self.purpose,
            "focus": self.focus,
            "phenomena": self.phenomena,
            "inference_level": self.inference_level,
            "missing_info_policy": self.missing_info_policy,
            "terminology": self.terminology,
            "template_id": self.template_id,
            "enable_web_search": self.enable_web_search,
            "enable_rag": self.enable_rag,
            "enable_system_kb": self.enable_system_kb,
            "enable_personal_kb": self.enable_personal_kb,
            "enable_org_kb": self.enable_org_kb,
            "trusted_domains": self.trusted_domains
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        return cls(
            mode=data.get("mode", "simulation"),
            domain=data.get("domain", "unknown"),
            context=data.get("context", "unknown"),
            purpose=data.get("purpose", "show"),
            focus=data.get("focus", []),
            phenomena=data.get("phenomena", []),
            inference_level=data.get("inference_level", "describe_only"),
            missing_info_policy=data.get("missing_info_policy", "must_disclose"),
            terminology=data.get("terminology", {"var_style": "original"}),
            template_id=data.get("template_id", "cfd_standard"),
            enable_web_search=data.get("enable_web_search", True),
            enable_rag=data.get("enable_rag", True),
            enable_system_kb=data.get("enable_system_kb", True),
            enable_personal_kb=data.get("enable_personal_kb", True),
            enable_org_kb=data.get("enable_org_kb", True),
            trusted_domains=data.get("trusted_domains", [])
        )
    
    @classmethod
    def default_conservative(cls) -> "Policy":
        """默认保守策略"""
        return cls(
            context="unknown",
            inference_level="describe_only",
            missing_info_policy="must_disclose",
            terminology={"var_style": "original"}
        )


@dataclass
class Draft:
    """Draft JSON - 系统唯一真相源"""
    # 元信息
    draft_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    
    # 策略
    policy: Policy = field(default_factory=Policy)
    
    # 事实（来自数据包）
    facts: Dict[str, Any] = field(default_factory=dict)
    
    # 槽位列表
    slots: List[Slot] = field(default_factory=list)
    
    # 证据包（来自RAG和Browser）
    evidence_pack: Dict[str, Any] = field(default_factory=dict)
    
    # Clarification记录
    clarification_questions: List[Dict[str, Any]] = field(default_factory=list)
    clarification_answers: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "policy": self.policy.to_dict(),
            "facts": self.facts,
            "slots": [s.to_dict() for s in self.slots],
            "evidence_pack": self.evidence_pack,
            "clarification_questions": self.clarification_questions,
            "clarification_answers": self.clarification_answers
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Draft":
        return cls(
            draft_id=data.get("draft_id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
            policy=Policy.from_dict(data.get("policy", {})),
            facts=data.get("facts", {}),
            slots=[Slot.from_dict(s) for s in data.get("slots", [])],
            evidence_pack=data.get("evidence_pack", {}),
            clarification_questions=data.get("clarification_questions", []),
            clarification_answers=data.get("clarification_answers", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "Draft":
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_slot(self, slot_id: str) -> Optional[Slot]:
        """获取槽位"""
        for slot in self.slots:
            if slot.slot_id == slot_id:
                return slot
        return None
    
    def update_slot(self, slot_id: str, **kwargs) -> bool:
        """更新槽位"""
        slot = self.get_slot(slot_id)
        if slot is None:
            return False
        
        for key, value in kwargs.items():
            if hasattr(slot, key):
                setattr(slot, key, value)
        
        self.updated_at = datetime.now().isoformat()
        return True
    
    def get_pending_slots(self) -> List[Slot]:
        """获取待生成的槽位"""
        return [s for s in self.slots if s.status == SlotStatus.PENDING]
    
    def get_draft_slots(self) -> List[Slot]:
        """获取待确认的槽位"""
        return [s for s in self.slots if s.status == SlotStatus.DRAFT]
    
    def get_accepted_slots(self) -> List[Slot]:
        """获取已接受的槽位"""
        return [s for s in self.slots if s.status == SlotStatus.ACCEPTED]
    
    def get_slots_needing_rewrite(self, changed_policy_keys: List[str]) -> List[Slot]:
        """获取需要重写的槽位（当policy变化时）"""
        rewrite_slots = []
        for slot in self.slots:
            # 跳过已接受或用户编辑的槽位
            if slot.status in [SlotStatus.ACCEPTED, SlotStatus.USER_EDITED]:
                continue
            
            # 检查依赖的policy是否变化
            if any(key in slot.dependencies.policy for key in changed_policy_keys):
                rewrite_slots.append(slot)
        
        return rewrite_slots


# 预定义的领域列表（面向 SimuVision Desktop 支持的仿真场景）
DOMAINS = [
    {"id": "external_aero", "name": "外流气动分析", "description": "翼型/飞行器/车辆外流绕流、升阻特性"},
    {"id": "turbomachinery", "name": "叶轮机械", "description": "压气机、涡轮、叶栅流动、级性能"},
    {"id": "internal_flow", "name": "内流分析", "description": "管道、进气道、喷管、阀门内部流动"},
    {"id": "heat_transfer", "name": "传热与热防护", "description": "气动加热、壁面热流、散热分析"},
    {"id": "structural", "name": "结构力学", "description": "应力/应变/位移/变形分析（Abaqus等）"},
    {"id": "general_cfd", "name": "通用CFD", "description": "不属于以上分类的一般流体仿真"},
]

# 预定义的物理现象列表
PHENOMENA = [
    {"id": "flow_separation", "name": "流动分离", "description": "流体从壁面分离"},
    {"id": "turbulence", "name": "湍流", "description": "湍流流动特性"},
    {"id": "shock_wave", "name": "激波", "description": "可压缩流中的激波"},
    {"id": "heat_transfer", "name": "传热", "description": "热量传递过程"},
    {"id": "mixing", "name": "混合", "description": "流体混合过程"},
    {"id": "combustion", "name": "燃烧", "description": "燃烧反应"},
    {"id": "multiphase", "name": "多相流", "description": "气液/气固等多相流动"},
    {"id": "boundary_layer", "name": "边界层", "description": "壁面边界层特性"},
    {"id": "vortex", "name": "涡旋", "description": "涡旋结构"},
    {"id": "pressure_loss", "name": "压力损失", "description": "流动压力损失"},
]

# 报告目的列表
PURPOSES = [
    {"id": "show", "name": "展示结果", "description": "展示仿真结果，说明流场特性"},
    {"id": "diagnose", "name": "问题诊断", "description": "诊断设计问题，找出原因"},
    {"id": "compare", "name": "方案对比", "description": "对比不同设计方案"},
    {"id": "acceptance", "name": "验收评估", "description": "评估是否满足设计要求"},
]
