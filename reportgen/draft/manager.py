"""Draft管理器"""

import json
import uuid
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from .schema import Draft, Slot, Policy, SlotStatus, SlotType, SlotDependency
from ..templates import get_template_slots, list_templates


class DraftManager:
    """Draft JSON管理器（线程安全）"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else None
        self.current_draft: Optional[Draft] = None
        self._lock = threading.RLock()
        self._draft_history: List[Dict[str, Any]] = []
        self._max_history = 5
    
    def create_draft(
        self,
        facts: Dict[str, Any],
        slot_specs: List[Dict[str, Any]] = None,
        policy: Policy = None
    ) -> Draft:
        """创建新的Draft
        
        槽位来源优先级：
        1. 显式传入的 slot_specs
        2. Policy 中指定的 template_id 对应的模板
        3. 内置默认槽位结构（兜底）
        """
        with self._lock:
            # 备份当前 Draft 到历史
            if self.current_draft is not None:
                self._backup_current_draft()

            policy = policy or Policy.default_conservative()
            
            draft = Draft(
                draft_id=str(uuid.uuid4())[:8],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                policy=policy,
                facts=facts,
                slots=[]
            )
            
            if slot_specs:
                resolved_specs = slot_specs
            else:
                try:
                    resolved_specs = get_template_slots(policy.template_id, facts)
                except FileNotFoundError:
                    resolved_specs = None

            if resolved_specs:
                for spec in resolved_specs:
                    slot = Slot(
                        slot_id=spec.get("slot_id", str(uuid.uuid4())[:8]),
                        placeholder_text=spec.get("placeholder_text", ""),
                        section=spec.get("section", ""),
                        slot_type=SlotType(spec.get("slot_type", "text")),
                        status=SlotStatus.PENDING,
                        dependencies=SlotDependency(
                            policy=spec.get("dependencies", {}).get("policy", []),
                            facts=spec.get("dependencies", {}).get("facts", [])
                        )
                    )
                    draft.slots.append(slot)
            else:
                draft.slots = self._create_default_slots(facts)
            
            self.current_draft = draft
            return draft
    
    def _backup_current_draft(self):
        """备份当前 Draft 到历史（保留最近 N 份）"""
        try:
            snapshot = self.current_draft.to_dict()
            self._draft_history.append(snapshot)
            if len(self._draft_history) > self._max_history:
                self._draft_history = self._draft_history[-self._max_history:]
        except Exception:
            pass
    
    def get_draft_history(self) -> List[Dict[str, Any]]:
        """获取 Draft 历史备份列表"""
        with self._lock:
            return [
                {"draft_id": h.get("draft_id", ""), "created_at": h.get("created_at", ""), "slots": len(h.get("slots", []))}
                for h in self._draft_history
            ]
    
    def restore_draft(self, index: int = -1) -> Optional[Draft]:
        """从历史备份恢复 Draft"""
        with self._lock:
            if not self._draft_history:
                return None
            try:
                snapshot = self._draft_history[index]
                self.current_draft = Draft.from_dict(snapshot)
                return self.current_draft
            except (IndexError, Exception):
                return None
    
    def _create_default_slots(self, facts: Dict[str, Any]) -> List[Slot]:
        """创建默认槽位结构（基于现有报告模板）"""
        slots = []
        
        # 1. 分析目的
        slots.append(Slot(
            slot_id="analysis_purpose_1",
            placeholder_text="[---分析目的1---]",
            section="1",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["purpose", "domain", "phenomena"],
                facts=["manifest", "variables"]
            )
        ))
        
        slots.append(Slot(
            slot_id="analysis_purpose_2",
            placeholder_text="[---分析目的2---]",
            section="1",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["purpose", "focus"],
                facts=["manifest"]
            )
        ))
        
        # 2. 几何结构描述
        slots.append(Slot(
            slot_id="geometry_description",
            placeholder_text="[---几何结构描述---]",
            section="2",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["domain"],
                facts=["manifest", "blocks"]
            )
        ))
        
        # 3. 网格描述
        slots.append(Slot(
            slot_id="mesh_description",
            placeholder_text="[---网格描述---]",
            section="3",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["domain"],
                facts=["manifest", "blocks"]
            )
        ))
        
        # 4. 评定准则
        slots.append(Slot(
            slot_id="evaluation_criteria_1",
            placeholder_text="[---评定准则1---]",
            section="5",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["domain", "purpose", "inference_level"],
                facts=["variables"]
            )
        ))
        
        slots.append(Slot(
            slot_id="evaluation_criteria_2",
            placeholder_text="[---评定准则2---]",
            section="5",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["domain", "missing_info_policy"],
                facts=["manifest"]
            )
        ))
        
        # 5. 变量语义说明（为每个变量创建槽位）
        variables = facts.get("variables", [])
        for i, var in enumerate(variables):
            var_name = var.get("name", f"V{i+1}")
            slots.append(Slot(
                slot_id=f"variable_{var_name}",
                placeholder_text=f"[---变量{var_name}说明---]",
                section="6",
                slot_type=SlotType.TEXT,
                dependencies=SlotDependency(
                    policy=["domain", "terminology", "inference_level"],
                    facts=["variables"]
                )
            ))
        
        # 6. 结论
        slots.append(Slot(
            slot_id="conclusion",
            placeholder_text="[---结论---]",
            section="7",
            slot_type=SlotType.TEXT,
            dependencies=SlotDependency(
                policy=["purpose", "inference_level", "missing_info_policy"],
                facts=["manifest", "variables", "automation_ops"]
            )
        ))
        
        return slots
    
    def load_draft(self, path: str) -> Draft:
        """从文件加载Draft"""
        with self._lock:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.current_draft = Draft.from_dict(data)
            return self.current_draft
    
    def save_draft(self, path: str = None) -> str:
        """保存Draft到文件"""
        with self._lock:
            if self.current_draft is None:
                raise ValueError("No draft to save")
            
            if path is None:
                if self.output_dir is None:
                    raise ValueError("No output path specified")
                path = self.output_dir / f"draft_{self.current_draft.draft_id}.json"
            
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.current_draft.to_json())
            
            return str(path)
    
    def update_policy(self, policy_updates: Dict[str, Any]) -> List[str]:
        """更新策略，返回受影响的槽位ID列表"""
        with self._lock:
            if self.current_draft is None:
                return []
            
            changed_keys = []
            policy = self.current_draft.policy
            
            for key, value in policy_updates.items():
                if hasattr(policy, key):
                    old_value = getattr(policy, key)
                    if old_value != value:
                        setattr(policy, key, value)
                        changed_keys.append(key)
            
            affected_slots = self.current_draft.get_slots_needing_rewrite(changed_keys)
            self.current_draft.updated_at = datetime.now().isoformat()
            
            return [s.slot_id for s in affected_slots]
    
    # Valid state transitions for the slot state machine
    _VALID_TRANSITIONS = {
        SlotStatus.PENDING: {SlotStatus.DRAFT, SlotStatus.USER_EDITED},
        SlotStatus.DRAFT: {SlotStatus.ACCEPTED, SlotStatus.REJECTED, SlotStatus.USER_EDITED},
        SlotStatus.REJECTED: {SlotStatus.DRAFT, SlotStatus.PENDING, SlotStatus.USER_EDITED},
        SlotStatus.ACCEPTED: {SlotStatus.USER_EDITED},
        SlotStatus.USER_EDITED: set(),
    }

    def update_slot_status(
        self,
        slot_id: str,
        status: SlotStatus,
        reject_reason: str = "",
        user_feedback: str = "",
        force: bool = False,
    ) -> bool:
        """更新槽位状态（带状态机校验）"""
        with self._lock:
            if self.current_draft is None:
                return False
            
            slot = self.current_draft.get_slot(slot_id)
            if slot is None:
                return False
            
            if not force:
                allowed = self._VALID_TRANSITIONS.get(slot.status, set())
                if status not in allowed:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Invalid slot transition: {slot.slot_id} {slot.status.value} -> {status.value}"
                    )
                    return False
            
            slot.status = status
            slot.reject_reason = reject_reason
            slot.user_feedback = user_feedback
            
            self.current_draft.updated_at = datetime.now().isoformat()
            return True
    
    def update_slot_content(
        self,
        slot_id: str,
        content: str,
        claims: List[Dict[str, Any]] = None,
        evidence_pack: Dict[str, Any] = None,
        status: SlotStatus = SlotStatus.DRAFT,
        source: str = "llm",
    ) -> bool:
        """更新槽位内容"""
        with self._lock:
            if self.current_draft is None:
                return False
            
            slot = self.current_draft.get_slot(slot_id)
            if slot is None:
                return False
            
            slot.content = content
            slot.status = status
            slot.generated_at = datetime.now().isoformat()
            
            if claims:
                from .schema import Claim
                slot.claims = [Claim.from_dict(c) for c in claims]
            
            if evidence_pack:
                slot.evidence_pack = evidence_pack

            if not isinstance(slot.evidence_pack, dict):
                slot.evidence_pack = {}
            slot.evidence_pack["_generation_source"] = source
            
            self.current_draft.updated_at = datetime.now().isoformat()
            return True
    
    def accept_slot(self, slot_id: str, force: bool = False) -> bool:
        """接受槽位"""
        return self.update_slot_status(slot_id, SlotStatus.ACCEPTED, force=force)
    
    def reject_slot(self, slot_id: str, reason: str) -> bool:
        """拒绝槽位"""
        return self.update_slot_status(slot_id, SlotStatus.REJECTED, reject_reason=reason)
    
    def edit_slot(self, slot_id: str, content: str) -> bool:
        """用户编辑槽位"""
        with self._lock:
            if self.current_draft is None:
                return False
            
            slot = self.current_draft.get_slot(slot_id)
            if slot is None:
                return False
            
            slot.content = content
            slot.status = SlotStatus.USER_EDITED
            
            self.current_draft.updated_at = datetime.now().isoformat()
            return True
    
    def set_clarification_answers(self, answers: Dict[str, Any]):
        """设置Clarification答案"""
        with self._lock:
            if self.current_draft is None:
                return
            
            self.current_draft.clarification_answers = answers
            
            policy_fields = {
                "domain", "purpose", "focus", "phenomena",
                "inference_level", "enable_web_search", "enable_rag"
            }
            for key in policy_fields:
                if key in answers:
                    setattr(self.current_draft.policy, key, answers[key])
            
            self.current_draft.updated_at = datetime.now().isoformat()
    
    def get_progress(self) -> Dict[str, Any]:
        """获取生成进度"""
        with self._lock:
            if self.current_draft is None:
                return {"total": 0, "pending": 0, "draft": 0, "accepted": 0, "user_edited": 0, "progress": 0}
            
            total = len(self.current_draft.slots)
            pending = len(self.current_draft.get_pending_slots())
            draft = len(self.current_draft.get_draft_slots())
            accepted = len(self.current_draft.get_accepted_slots())
            user_edited = len([s for s in self.current_draft.slots if s.status == SlotStatus.USER_EDITED])
            
            completed = accepted + user_edited
            progress = (completed / total * 100) if total > 0 else 0
            
            return {
                "total": total,
                "pending": pending,
                "draft": draft,
                "accepted": completed,
                "user_edited": user_edited,
                "progress": round(progress, 1)
            }
