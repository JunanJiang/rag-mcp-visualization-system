"""槽位填充器 - 集成Browser和RAG"""

import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..draft.schema import Slot, SlotStatus, Policy, Claim, SourceType, RiskLevel
from ..browser.search import WebSearcher, EvidencePack

logger = logging.getLogger(__name__)

MAX_LLM_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0


class SlotFiller:
    """槽位填充器"""
    
    def __init__(
        self,
        llm_client,
        web_searcher: WebSearcher = None,
        vector_index = None,
        use_mock: bool = False,
        kb_manager = None,
        user_context: Optional[Dict[str, Any]] = None,
    ):
        self.llm_client = llm_client
        self.web_searcher = web_searcher or WebSearcher(use_mock=use_mock)
        self.vector_index = vector_index
        self.use_mock = use_mock
        self.kb_manager = kb_manager
        self.user_context = user_context or {}
    
    def fill_slot(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy,
        evidence_pack: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """填充单个槽位"""
        
        # 1. 收集证据
        if evidence_pack is None:
            evidence_pack = self._gather_evidence(slot, facts, policy)
        
        # 2. 对 variable_* 槽位：直接使用高质量模板，不走 LLM
        if slot.slot_id.startswith("variable_"):
            result = self._fill_variable_slot(slot, facts, policy)
        elif self.use_mock:
            # 3. mock 模式：其他槽位也走模板
            result = self._mock_fill(slot, facts, policy)
        else:
            # 4. 其他槽位：走 LLM（带重试和降级）
            prompt = self._build_fill_prompt(slot, facts, policy, evidence_pack)
            result = self._call_llm(prompt, slot, facts=facts, policy=policy)
        
        # 5. 解析结果
        return {
            "slot_id": slot.slot_id,
            "content": result.get("content", ""),
            "claims": result.get("claims", []),
            "evidence_pack": evidence_pack,
            "missing_info": result.get("missing_info", []),
            "suggested_questions": result.get("suggested_questions", []),
            "generated_at": datetime.now().isoformat()
        }
    
    def _fill_variable_slot(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy
    ) -> Dict[str, Any]:
        """变量槽位专用填充：使用高质量模板，确保内容包含真实数值和深度分析"""
        derived = facts.get("derived_quantities", {})
        flow_analysis = facts.get("flow_analysis", {})
        variables = facts.get("variables", [])
        
        var_name = slot.slot_id.replace("variable_", "")
        var_info = None
        for var in variables:
            if var.get("name") == var_name:
                var_info = var
                break
        
        if var_info:
            content = self._generate_variable_analysis(var_info, derived, flow_analysis, policy)
        else:
            content = f"变量{var_name}的数值分布在数据包中可见。该变量的物理意义需要结合具体应用场景进行解释。"
        
        return {
            "content": content,
            "claims": [],
            "missing_info": [],
            "suggested_questions": []
        }
    
    def _gather_evidence(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy
    ) -> Dict[str, Any]:
        """收集证据（来自Browser、RAG和用户上传的附件）"""
        evidence = {
            "web_sources": [],
            "rag_sources": [],
            "definitions": {},
            "standards": [],
            "attachments": []
        }
        
        # 从 facts 中获取用户上传的附件内容
        attachments = facts.get("attachments", [])
        for att in attachments:
            if att.get("content"):
                evidence["attachments"].append({
                    "name": att.get("name", ""),
                    "type": att.get("type", ""),
                    "content": att.get("content", "")[:5000]  # 限制长度
                })
            elif att.get("type") == "image":
                evidence["attachments"].append({
                    "name": att.get("name", ""),
                    "type": "image",
                    "url": att.get("url", "")
                })
        
        # 确定搜索关键词
        search_terms = self._get_search_terms(slot, facts, policy)
        
        # Web搜索
        if policy.enable_web_search and self.web_searcher:
            for term in search_terms[:3]:  # 限制搜索次数
                query = f"{policy.domain} {term}"
                results = self.web_searcher.search(query, max_results=2)
                
                for r in results:
                    evidence["web_sources"].append({
                        "url": r.url,
                        "title": r.title,
                        "snippet": r.snippet,
                        "term": term
                    })
                    
                    if term.lower() in r.snippet.lower():
                        evidence["definitions"][term] = r.snippet
        
        # RAG搜索：统一使用 Slot-Aware Retrieval（优先 KBManager，回退到 vector_index）
        if policy.enable_rag:
            slot_query = " ".join(search_terms[:3])
            
            if self.kb_manager and self.user_context:
                try:
                    kb_results = self.kb_manager.retrieve(
                        query=slot_query,
                        user_id=self.user_context.get("user_id", 0),
                        org_ids=self.user_context.get("org_ids", []),
                        role=self.user_context.get("role", "user"),
                        top_k=5,
                        enable_system=policy.enable_system_kb,
                        enable_personal=policy.enable_personal_kb,
                        enable_org=getattr(policy, 'enable_org_kb', True),
                    )
                    for r in kb_results:
                        evidence["rag_sources"].append({
                            "content": r.get("content", ""),
                            "source": r.get("metadata", {}).get("filename", r.get("collection", "")),
                            "score": r.get("score", 0),
                            "term": slot_query
                        })
                except Exception as e:
                    logger.warning(f"KBManager RAG 搜索失败: {e}")
            elif self.vector_index:
                try:
                    from ..kb.retrieve import retrieve_for_slot
                    slot_results = retrieve_for_slot(
                        self.vector_index, slot.slot_id,
                        slot.placeholder_text, facts, top_k=3
                    )
                    for r in slot_results:
                        evidence["rag_sources"].append({
                            "content": r.get("content", ""),
                            "source": r.get("metadata", {}).get("title", r.get("id", "")),
                            "score": r.get("score", 0),
                            "term": slot.slot_id
                        })
                except Exception as e:
                    logger.warning(f"Slot-Aware 检索失败，回退到通用搜索: {e}")
                    for term in search_terms[:3]:
                        try:
                            search_fn = getattr(self.vector_index, 'hybrid_search', self.vector_index.search)
                            rag_results = search_fn(term, top_k=2)
                            for r in rag_results:
                                evidence["rag_sources"].append({
                                    "content": r.get("content", ""),
                                    "source": r.get("source", ""),
                                    "score": r.get("score", 0),
                                    "term": term
                                })
                        except Exception as e2:
                            logger.warning(f"RAG搜索失败: {e2}")

        return evidence
    
    def _get_search_terms(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy
    ) -> List[str]:
        """获取搜索关键词。"""
        terms = []
        if slot.slot_id.startswith("variable_"):
            var_name = slot.slot_id.replace("variable_", "")
            for var in facts.get("variables", []):
                if var.get("name") == var_name:
                    guess_name = var.get("guess_variableName", "")
                    if guess_name:
                        terms.append(guess_name)
                        terms.append(f"{guess_name} CFD")
                    break

        elif slot.slot_id.startswith("evaluation_"):
            terms.append("CFD 评定准则")
            terms.append("仿真结果验证")
            for phenom in policy.phenomena:
                terms.append(f"{phenom} 评判标准")

        elif slot.slot_id.startswith("analysis_purpose"):
            terms.append(f"{policy.domain} 仿真分析目的")

        elif slot.slot_id == "conclusion":
            terms.append("CFD 仿真结论")
            terms.append("仿真结果总结")

        # 添加领域关键词
        if policy.domain not in ("unknown", "general_cfd") and terms:
            terms = [f"{policy.domain} {t}" if policy.domain not in t else t for t in terms]

        return terms
    
    def _build_fill_prompt(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy,
        evidence: Dict[str, Any]
    ) -> str:
        """构建填充prompt"""
        
        # 根据槽位类型构建针对性的prompt
        slot_specific_instruction = self._get_slot_specific_instruction(slot, facts, policy)
        
        # 格式化RAG证据（优先显示）
        rag_evidence = self._format_rag_evidence(evidence)
        web_evidence = self._format_web_evidence(evidence)
        attachment_evidence = self._format_attachment_evidence(evidence)
        
        user_prompt = f"""你是一位资深的CFD仿真分析工程师，正在撰写一份专业的仿真分析报告。
请基于以下数据事实和知识库参考资料，为报告的指定章节生成高质量的技术内容。

## 写作要求
1. 内容必须基于提供的数据事实，所有数值必须准确引用
2. 使用专业但清晰的工程语言，避免空洞的套话
3. 对数据特征进行有深度的分析和解读，而非简单罗列
4. 结合流体力学专业知识对数据进行合理推断（需标注为推断）
5. 【重要】只描述数据包中实际存在的内容，不要提及数据包缺少什么信息
6. 应用领域：{policy.domain}，报告目的：{policy.purpose}
7. 推断强度：{policy.inference_level}（describe_only=仅描述数据，may_infer=可做合理推断）
8. 变量命名风格：{policy.terminology.get('var_style', 'original')}（original=保持原始名称，chinese=中文名称，english=英文名称，symbolic=物理符号如ρ、ρu）
9. 【证据溯源】每个关键断言必须用行内标注标明来源：
   - [DATA] 表示来自数据包的事实（数值、网格信息等）
   - [RAG-N] 表示来自知识库第N个片段（如 [RAG-1]）
   - [INFER] 表示基于数据的合理推断

## 当前任务
{slot_specific_instruction}

## 数据事实
{self._format_facts_for_slot(slot, facts)}

{rag_evidence}

{web_evidence}

请直接输出段落内容（300-500字），不要加标题、编号或JSON格式。内容应该是完整的、可直接放入技术报告的段落。
请在关键断言后标注来源（如"密度变化比约为23.5:1[DATA]"），这些标注会在报告渲染时自动转为引用标记。"""

        return user_prompt
    
    def _get_slot_specific_instruction(self, slot: Slot, facts: Dict[str, Any], policy: Policy) -> str:
        """根据槽位类型生成针对性的写作指令"""
        derived = facts.get("derived_quantities", {})
        flow_analysis = facts.get("flow_analysis", {})
        ops_summary = facts.get("ops_summary", {})
        mesh_analysis = facts.get("mesh_analysis", {})
        
        if slot.slot_id == "analysis_purpose_1":
            findings = flow_analysis.get("key_findings", [])
            findings_str = "；".join(findings[:3]) if findings else "待分析"
            return f"""为"分析目的"章节撰写第一段。
要求：说明本次仿真分析的技术背景和主要目标。
- 结合数据包的具体特征（数据类型、网格规模、变量类型）说明分析目标
- 提及将要分析的物理现象：{', '.join(policy.phenomena) if policy.phenomena else '流场特性'}
- 初步发现：{findings_str}
- 不要写空泛的套话，要具体到本次数据的特点
- 不要提及数据包缺少什么，只描述数据包有什么"""
        
        elif slot.slot_id == "analysis_purpose_2":
            return f"""为"分析目的"章节撰写第二段。
要求：说明本次分析的工程价值和预期成果。
- 说明分析结果将如何支撑工程决策
- 提及后处理手段：{ops_summary.get('description', '未知')}
- 说明报告将涵盖的分析维度（几何、网格、流场变量、后处理可视化）
- 不要提及数据包缺少什么，只描述数据包提供了什么"""
        
        elif slot.slot_id == "geometry_description":
            return f"""为"几何结构"章节撰写描述。
要求：详细描述计算域的几何特征。
- 说明多块结构的设计意图和拓扑关系
- 分析各块的空间分布特征（哪些块较大、哪些较小、可能对应什么区域）
- 网格分析：{'; '.join(mesh_analysis.get('resolution_notes', []))}
- 最大块：{mesh_analysis.get('largest_block', {}).get('name', 'N/A')}，最小块：{mesh_analysis.get('smallest_block', {}).get('name', 'N/A')}
- 不要只说"共X个块"，要分析块的分布特征"""
        
        elif slot.slot_id == "mesh_description":
            concerns = mesh_analysis.get("aspect_ratio_concerns", [])
            concern_str = f"存在{len(concerns)}个高纵横比块" if concerns else "纵横比在合理范围内"
            return f"""为"网格结构"章节撰写描述。
要求：分析网格的质量特征和适用性。
- 说明结构网格的优势和适用场景
- 分析块大小分布：{mesh_analysis.get('size_distribution', 'unknown')}
- 纵横比情况：{concern_str}
- 分辨率评估：{'; '.join(mesh_analysis.get('resolution_notes', []))}
- 对网格质量给出专业评价"""
        
        elif slot.slot_id == "evaluation_criteria_1":
            return f"""为"评定准则"章节撰写第一段（计算质量评定）。
要求：
- 说明CFD计算质量的评定标准（收敛性、守恒性、网格独立性）
- 基于当前数据包的实际情况进行评估
- 明确指出数据包缺少残差收敛历史这一关键信息
- 对现有数据的可信度给出初步判断
- 流场特征：{derived.get('flow_regime', 'unknown')}"""
        
        elif slot.slot_id == "evaluation_criteria_2":
            return f"""为"评定准则"章节撰写第二段（结果可信度评估）。
要求：
- 评估网格分辨率是否足够（当前{facts.get('datasets', {}).get('total_points', 0):,}个节点）
- 讨论网格独立性验证的必要性
- 对边界层分辨率提出建议
- 指出缺失的验证信息（边界条件、湍流模型等）
- 给出改进建议"""
        
        elif slot.slot_id.startswith("variable_"):
            var_name = slot.slot_id.replace("variable_", "")
            var_info = None
            for var in facts.get("variables", []):
                if var.get("name") == var_name:
                    var_info = var
                    break
            
            if var_info:
                guess_name = var_info.get("guess_variableName", "unknown")
                range_min = var_info.get("range_min", 0)
                range_max = var_info.get("range_max", 0)
                
                # 获取该变量的派生分析
                vel_est = derived.get("velocity_estimates", {})
                correlations = derived.get("variable_correlations", [])
                
                return f"""为变量"{var_name}"（推断语义：{guess_name}）撰写分析段落。
要求（必须包含以下3个方面）：
1. **物理含义**：结合知识库资料解释该变量的物理意义，说明在CFD中的作用
2. **数据特征分析**：数值范围{range_min:.4e}~{range_max:.4e}，分析这个范围说明了什么物理现象
3. **图像解读指导**：告诉读者在对应的分布图中应该关注什么区域和现象

相关派生分析：
- 流动状态：{derived.get('flow_regime', 'unknown')}
- 密度比：{derived.get('density_ratio', 'N/A')}
- 变量关联：{'; '.join(correlations) if correlations else '无特殊关联'}

禁止：不要编造数值、不要给出性能结论（效率/压比/推力）、不要提及数据包缺少什么信息"""
            else:
                return f"为变量{var_name}撰写分析段落。"
        
        elif slot.slot_id == "conclusion":
            findings = flow_analysis.get("key_findings", [])
            attention = flow_analysis.get("attention_points", [])
            limitations = flow_analysis.get("limitations", [])
            return f"""为"结论"章节撰写总结。
要求：基于全部分析结果，撰写3-5条结论。

关键发现：
{chr(10).join('- ' + f for f in findings)}

需要关注的问题：
{chr(10).join('- ' + a for a in attention)}

数据局限性（仅在结论章节统一说明）：
{chr(10).join('- ' + l for l in limitations)}

结论应包括：数据包概况总结、流场特征判断、后处理结果评价，最后统一列出数据局限性和改进建议"""
        
        else:
            return f"为\"{slot.placeholder_text}\"撰写内容。"
    
    def _format_facts_for_slot(self, slot: Slot, facts: Dict[str, Any]) -> str:
        """格式化facts供槽位使用 - 提供丰富的数据上下文"""
        lines = []
        
        manifest = facts.get("manifest", {})
        datasets = facts.get("datasets", {})
        derived = facts.get("derived_quantities", {})
        flow_analysis = facts.get("flow_analysis", {})
        mesh_analysis = facts.get("mesh_analysis", {})
        ops_summary = facts.get("ops_summary", {})
        
        dataset_type = manifest.get('dataset_type', manifest.get('datasetType', 'Unknown'))
        block_count = manifest.get('block_count', manifest.get('blockCount', datasets.get('block_count', 0)))
        total_points = manifest.get('total_points', manifest.get('totalPoints', datasets.get('total_points', 0)))
        total_cells = manifest.get('total_cells', manifest.get('totalCells', datasets.get('total_cells', 0)))
        
        # 基本信息
        lines.append("=== 数据包基本信息 ===")
        lines.append(f"数据类型: {dataset_type}")
        lines.append(f"来源软件: {manifest.get('app_name', 'Unknown')} v{manifest.get('app_version', '')}")
        lines.append(f"网格块数: {block_count}")
        lines.append(f"总节点数: {total_points:,}")
        lines.append(f"总单元数: {total_cells:,}")
        
        # 网格块信息（全部显示）
        blocks = datasets.get('blocks', [])
        if blocks:
            lines.append(f"\n=== 网格块详情 (共{len(blocks)}个块) ===")
            for block in blocks:
                dims = block.get('dims', [])
                dims_str = '×'.join(map(str, dims)) if dims else 'N/A'
                lines.append(f"  {block.get('name')}: {dims_str}, {block.get('points', 0):,}点, {block.get('cells', 0):,}单元")
        
        # 网格质量分析
        if mesh_analysis:
            lines.append(f"\n=== 网格质量分析 ===")
            lines.append(f"块大小分布: {mesh_analysis.get('size_distribution', 'unknown')}")
            largest = mesh_analysis.get('largest_block', {})
            smallest = mesh_analysis.get('smallest_block', {})
            if largest:
                lines.append(f"最大块: {largest.get('name')} ({largest.get('points', 0):,}点)")
            if smallest:
                lines.append(f"最小块: {smallest.get('name')} ({smallest.get('points', 0):,}点)")
            for note in mesh_analysis.get('resolution_notes', []):
                lines.append(f"分辨率: {note}")
            for concern in mesh_analysis.get('aspect_ratio_concerns', []):
                lines.append(f"纵横比警告: {concern.get('block')} 比值={concern.get('ratio')}")
        
        # 变量信息
        variables = facts.get("variables", [])
        if variables:
            lines.append(f"\n=== 流场变量 (共{len(variables)}个) ===")
            for var in variables:
                range_min = var.get('range_min', 'N/A')
                range_max = var.get('range_max', 'N/A')
                if isinstance(range_min, (int, float)) and isinstance(range_max, (int, float)):
                    range_str = f"{range_min:.4e} ~ {range_max:.4e}"
                else:
                    range_str = f"{range_min} ~ {range_max}"
                lines.append(f"  {var.get('name')} ({var.get('guess_variableName', 'unknown')}): {range_str}")
        
        # 派生物理量
        if derived and derived.get("has_complete_conservation_vars"):
            lines.append(f"\n=== 派生物理量估算 ===")
            lines.append(f"密度比: {derived.get('density_ratio', 'N/A')}:1")
            vel_est = derived.get("velocity_estimates", {})
            if vel_est:
                for comp in ['u', 'v', 'w']:
                    if comp in vel_est:
                        v = vel_est[comp]
                        reverse = "(存在回流)" if v.get('has_reverse_flow') else ""
                        lines.append(f"  速度{comp}最大估算: {v.get('max_estimate', 0):.1f} {reverse}")
                lines.append(f"  最大合速度估算: {vel_est.get('speed_max', 0):.1f}")
            mach = derived.get("mach_estimate", {})
            if mach:
                lines.append(f"马赫数估算: ~{mach.get('max_estimate', 'N/A')} ({mach.get('note', '')})")
            lines.append(f"流动状态: {derived.get('flow_regime', 'unknown')}")
            correlations = derived.get("variable_correlations", [])
            if correlations:
                lines.append("变量关联分析:")
                for c in correlations:
                    lines.append(f"  - {c}")
        
        # 流场分析要点
        if flow_analysis:
            findings = flow_analysis.get("key_findings", [])
            if findings:
                lines.append(f"\n=== 流场分析要点 ===")
                for f in findings:
                    lines.append(f"  - {f}")
            attention = flow_analysis.get("attention_points", [])
            if attention:
                lines.append("需关注:")
                for a in attention:
                    lines.append(f"  - {a}")
        
        # 后处理操作
        if ops_summary and ops_summary.get("total_ops", 0) > 0:
            lines.append(f"\n=== 后处理操作 ===")
            lines.append(f"总操作数: {ops_summary.get('total_ops', 0)}")
            lines.append(f"操作类型: {ops_summary.get('description', '')}")
            lines.append(f"分析变量: {', '.join(ops_summary.get('variables_analyzed', []))}")
        
        # 针对特定变量槽位，提供更详细的变量信息
        if slot.slot_id.startswith("variable_"):
            var_name = slot.slot_id.replace("variable_", "")
            for var in variables:
                if var.get("name") == var_name:
                    lines.append(f"\n=== 当前变量详情: {var_name} ===")
                    lines.append(f"  推断语义: {var.get('guess_variableName', 'unknown')}")
                    range_min = var.get('range_min', 'N/A')
                    range_max = var.get('range_max', 'N/A')
                    if isinstance(range_min, (int, float)) and isinstance(range_max, (int, float)):
                        lines.append(f"  数值范围: {range_min:.6e} ~ {range_max:.6e}")
                        if range_min != 0:
                            lines.append(f"  变化倍数: {abs(range_max/range_min):.2f}x")
                        lines.append(f"  跨度: {range_max - range_min:.4e}")
                        if range_min < 0 and range_max > 0:
                            lines.append(f"  存在正负值交替（零值穿越）")
                    break
        
        return "\n".join(lines)
    
    def _format_rag_evidence(self, evidence: Dict[str, Any]) -> str:
        """格式化RAG知识库证据（优先展示）。空结果时插入保守性提示。"""
        rag_sources = evidence.get("rag_sources", [])
        if not rag_sources:
            return ("## 知识库参考资料\n"
                    "未检索到相关的知识库参考资料。请严格基于数据包中的实际数据进行描述，"
                    "避免推测超出数据范围的内容。如不确定，请标注为『待补充』。")
        
        lines = ["## 知识库参考资料（RAG检索）"]
        lines.append("以下内容来自专业知识库，请在写作时引用相关知识：")
        for i, src in enumerate(rag_sources[:5], 1):
            content = src.get('content', '').strip()
            source = src.get('source', '')
            score = src.get('score', 0)
            if content:
                lines.append(f"\n[知识库片段 {i}] 来源：{source}（相关度：{score:.2f}）")
                lines.append(content[:400])
        
        return "\n".join(lines)
    
    def _format_web_evidence(self, evidence: Dict[str, Any]) -> str:
        """格式化网络搜索证据"""
        web_sources = evidence.get("web_sources", [])
        definitions = evidence.get("definitions", {})
        
        if not web_sources and not definitions:
            return ""
        
        lines = ["## 网络参考资料"]
        for src in web_sources[:2]:
            snippet = src.get('snippet', '').strip()
            if snippet:
                lines.append(f"- {src.get('title', '')}: {snippet[:200]}")
        
        return "\n".join(lines)
    
    def _format_attachment_evidence(self, evidence: Dict[str, Any]) -> str:
        """格式化用户上传的附件内容"""
        attachments = evidence.get("attachments", [])
        if not attachments:
            return ""
        
        lines = ["## 用户上传的参考资料"]
        lines.append("以下是用户上传的文档内容，请在写作时参考并引用：")
        
        for i, att in enumerate(attachments, 1):
            name = att.get("name", f"文件{i}")
            att_type = att.get("type", "")
            content = att.get("content", "")
            
            if att_type == "image":
                lines.append(f"\n[图片 {i}] {name}")
                lines.append("（图片内容，请根据上下文描述）")
            elif content:
                lines.append(f"\n[文档 {i}] {name}")
                # 限制每个文档显示的内容长度
                lines.append(content[:3000])
        
        return "\n".join(lines)
    
    def _format_evidence(self, evidence: Dict[str, Any]) -> str:
        """格式化evidence（兼容旧接口）"""
        return self._format_rag_evidence(evidence) + "\n" + self._format_web_evidence(evidence)
    
    def _call_llm(self, prompt: str, slot: Slot, facts: Dict[str, Any] = None, policy: Policy = None) -> Dict[str, Any]:
        """调用LLM（带指数退避重试）"""
        last_error = None

        for attempt in range(MAX_LLM_RETRIES):
            try:
                messages = [{"role": "user", "content": prompt}]
                response = self.llm_client.chat(messages, temperature=0.5, max_tokens=1500)
                
                raw_content = response.get("content", "").strip() if isinstance(response, dict) else str(response).strip()
                
                # 剥离 LLM 可能返回的 JSON 包装（如 ```json {"\u6539\u5199\u540e\u5185\u5bb9": "..."}```）
                raw_content = self._strip_json_wrapper(raw_content)
                claims = self._extract_claims(raw_content)
                content = self._strip_source_tags(raw_content)
                
                if len(content) < 50:
                    if attempt < MAX_LLM_RETRIES - 1:
                        logger.warning(f"LLM返回过短 (attempt {attempt+1}), 重试...")
                        time.sleep(LLM_RETRY_BASE_DELAY * (2 ** attempt))
                        continue
                    logger.warning(f"LLM多次返回过短，降级到模板填充: {content}")
                    return self._mock_fill_with_marker(slot, facts, policy)
                
                return {
                    "content": content,
                    "claims": claims,
                    "missing_info": [],
                    "suggested_questions": [],
                    "_source": "llm"
                }
                
            except Exception as e:
                last_error = e
                if attempt < MAX_LLM_RETRIES - 1:
                    delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"LLM调用失败 (attempt {attempt+1}/{MAX_LLM_RETRIES}): {e}, {delay}s后重试")
                    time.sleep(delay)
                else:
                    logger.error(f"LLM调用{MAX_LLM_RETRIES}次均失败: {last_error}")

        return self._mock_fill_with_marker(slot, facts, policy)
    
    @staticmethod
    def _extract_claims(content: str) -> List[Dict[str, Any]]:
        """从 LLM 输出中提取带来源标注的声明 (e.g. [DATA], [RAG-1], [INFER])"""
        import re
        pattern = r'([^。！？\n]{10,}?)\s*\[(DATA|RAG-\d+|INFER)\]'
        claims = []
        for match in re.finditer(pattern, content):
            text = match.group(1).strip()
            source_tag = match.group(2)
            source_type = "DATA"
            if source_tag.startswith("RAG"):
                source_type = "EVIDENCE"
            elif source_tag == "INFER":
                source_type = "INFERENCE"
            claims.append({
                "text": text,
                "source": source_type,
                "risk": "low" if source_type == "DATA" else "mid" if source_type == "EVIDENCE" else "high",
                "evidence_ref": source_tag
            })
        return claims

    @staticmethod
    def _strip_json_wrapper(content: str) -> str:
        text = (content or "").strip()
        if not text:
            return text

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

        text = text.lstrip('`').strip()

        if not text.startswith("{"):
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if not match:
                return text
            text = match.group(0)

        try:
            import json
            parsed = json.loads(text)
        except Exception:
            import re
            match = re.search(r'"(?:改写后内容|content|text|正文|result|message|rewritten_content|rewrittenContent|output|answer)"\s*:\s*"([\s\S]*?)"\s*(?:,|\})', text)
            if not match:
                return text
            try:
                import json
                return json.loads('"' + match.group(1) + '"').strip()
            except Exception:
                return match.group(1).strip()

        if isinstance(parsed, dict):
            for key in ("改写后内容", "content", "text", "正文", "result", "message", "rewritten_content", "rewrittenContent", "output", "answer"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in parsed.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()

        return text

    @staticmethod
    def _strip_source_tags(content: str) -> str:
        text = (content or "").strip()
        if not text:
            return text
        import re
        text = re.sub(r'\s*\[(DATA|RAG-\d+|INFER)\]', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' *\n *', '\n', text)
        return text.strip()
    
    def _mock_fill_with_marker(self, slot: Slot, facts: Dict[str, Any] = None, policy: Policy = None) -> Dict[str, Any]:
        """LLM 失败后的降级填充，使用真实 facts/policy 并标记来源"""
        result = self._mock_fill(slot, facts or {}, policy or Policy())
        result["_source"] = "fallback"
        if result.get("content"):
            result["content"] = result["content"] + "\n\n> *[注：此内容由模板自动填充，建议人工审查或重新生成]*"
        return result
    
    def _mock_fill(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy
    ) -> Dict[str, Any]:
        """模拟填充（用于测试）- 基于派生物理量生成深度分析内容"""
        
        # 获取数据信息
        manifest = facts.get("manifest", {})
        datasets = facts.get("datasets", {})
        variables = facts.get("variables", [])
        derived = facts.get("derived_quantities", {})
        flow_analysis = facts.get("flow_analysis", {})
        mesh_analysis = facts.get("mesh_analysis", {})
        ops_summary = facts.get("ops_summary", {})
        
        block_count = manifest.get('block_count', manifest.get('blockCount', datasets.get('block_count', 11)))
        total_points = manifest.get('total_points', manifest.get('totalPoints', datasets.get('total_points', 1000000)))
        total_cells = manifest.get('total_cells', manifest.get('totalCells', datasets.get('total_cells', 900000)))
        dataset_type = manifest.get('dataset_type', manifest.get('datasetType', 'Plot3D'))
        
        # 获取派生量信息
        flow_regime = derived.get('flow_regime', '待确认')
        density_ratio = derived.get('density_ratio', 'N/A')
        vel_est = derived.get('velocity_estimates', {})
        speed_max = vel_est.get('speed_max', 0)
        mach_est = derived.get('mach_estimate', {}).get('max_estimate', 'N/A')
        correlations = derived.get('variable_correlations', [])
        findings = flow_analysis.get('key_findings', [])
        attention_points = flow_analysis.get('attention_points', [])
        limitations = flow_analysis.get('limitations', [])
        
        # 领域相关描述
        domain = policy.domain if policy.domain != 'unknown' else '通用CFD'
        domain_context = {
            'external_aero': '外流气动分析领域',
            'turbomachinery': '叶轮机械领域',
            'internal_flow': '内流分析领域',
            'heat_transfer': '传热与热防护领域',
            'structural': '结构力学领域',
            'general_cfd': '工程仿真',
        }.get(policy.domain, '工程仿真')
        
        phenomena_str = '、'.join(policy.phenomena) if policy.phenomena else '流场特性'
        
        # 网格分析信息
        largest_block = mesh_analysis.get('largest_block', {}).get('name', 'Block_1')
        smallest_block = mesh_analysis.get('smallest_block', {}).get('name', 'Block_N')
        resolution_note = mesh_analysis.get('resolution_notes', [''])[0] if mesh_analysis.get('resolution_notes') else ''
        size_dist = mesh_analysis.get('size_distribution', 'unknown')
        
        # 后处理信息
        ops_desc = ops_summary.get('description', '无') if ops_summary else '无'
        
        # 根据槽位类型生成深度分析内容
        content_templates = {
            "analysis_purpose_1": f"""本次仿真分析旨在对{domain_context}中的{dataset_type}格式多块结构网格数据进行系统性的流场特性评估。计算域由{block_count}个结构化网格块组成，总计包含{total_points:,}个网格节点和{total_cells:,}个网格单元，数据包提供了完整的5个守恒量变量（密度、三方向动量和总能量密度），符合Plot3D Q文件的标准格式。基于守恒量的初步分析，密度变化比值约为{density_ratio}:1，最大合速度估算约为{speed_max:.1f}，流动状态初步判断为{flow_regime}。本次分析将重点关注{phenomena_str}等物理现象，通过对各变量空间分布的系统解读，识别流场中的关键特征区域，包括可能存在的流动分离、激波结构和涡旋系统。""",
            
            "analysis_purpose_2": f"""本分析的工程价值在于为设计评估和优化提供定量的数据支撑。数据包已包含{ops_desc}等后处理可视化结果，将从几何结构、网格质量、流场变量分布和后处理可视化四个维度展开分析。报告将对各变量的物理意义进行解读，基于守恒量推算派生物理量（速度、马赫数等），并结合可视化结果识别流场中的关键特征。需要指出的是，当前数据包未提供边界条件设置、求解器参数和残差收敛历史等关键信息，因此分析结论主要基于数据的相对特征，定量结论需结合原始算例设置进一步验证。""",
            
            "geometry_description": f"""本数据包采用{dataset_type}格式的多块结构网格，计算域由{block_count}个结构化网格块组成，总计{total_points:,}个网格节点和{total_cells:,}个网格单元。多块结构的设计使得不同区域可以采用不同的网格密度和拓扑结构，以适应复杂的几何边界。从块的规模分布来看，最大块{largest_block}包含{mesh_analysis.get('largest_block', {}).get('points', 0):,}个节点，最小块{smallest_block}包含{mesh_analysis.get('smallest_block', {}).get('points', 0):,}个节点，块间规模差异{'较大' if size_dist == 'highly_nonuniform' else '中等' if size_dist == 'moderately_nonuniform' else '相对均匀'}，表明网格在不同区域采用了差异化的分辨率策略。较大的块可能对应主流通道或关键分析区域，而较小的块可能用于过渡区域或几何细节的处理。{resolution_note}。""",
            
            "mesh_description": f"""本模型采用多块结构网格（Multi-Block Structured Grid），共划分为{block_count}个计算块，总计{total_points:,}个网格节点和{total_cells:,}个网格单元。结构网格在计算效率和数值精度方面具有优势，特别适合具有规则几何特征的流动问题。从网格质量角度分析，块间规模分布为{size_dist}类型，{'存在较大的块间差异，需要关注块连接处的网格匹配质量' if size_dist != 'uniform' else '块间规模较为均匀'}。{resolution_note}。{'部分块的维度纵横比较大（' + '、'.join([c.get('block', '') + '比值' + str(c.get('ratio', '')) for c in mesh_analysis.get('aspect_ratio_concerns', [])[:2]]) + '），可能影响这些区域的计算精度。' if mesh_analysis.get('aspect_ratio_concerns') else '各块的维度纵横比在合理范围内。'}建议在后续分析中补充网格独立性验证，特别是对存在强梯度的区域进行网格细化敏感性研究。""",
            
            "evaluation_criteria_1": f"""CFD计算结果的质量评定需要从收敛性、守恒性和网格独立性三个方面进行综合评估。当前数据包包含{len(variables)}个流场守恒量变量的完整数值分布，各变量的数值范围均在物理合理范围内——密度值为正且变化比约{density_ratio}:1，动量分量的正负分布符合三维流动特征，总能量密度为正值。这些基本特征表明计算结果在物理一致性方面是合理的。然而，数据包中未提供残差收敛历史曲线，这是评估计算收敛性的关键信息。在缺少残差数据的情况下，只能通过变量分布的光滑性和物理合理性进行间接判断。基于当前数据的流动状态判断为{flow_regime}，{'在此流动条件下，压缩性效应显著，对计算收敛性的要求更高。' if derived.get('compressibility') in ['高', '极高'] else '在此流动条件下，数值稳定性相对较好。'}建议在后续分析中补充残差监控数据，以完整评估计算质量。""",
            
            "evaluation_criteria_2": f"""结果可信度的评估需要基于网格独立性研究。当前网格包含{total_points:,}个节点，{resolution_note.lower() if resolution_note else '分辨率待评估'}。对于{flow_regime}的流动问题，{'需要在激波附近和边界层区域保证足够的网格分辨率' if '超声速' in flow_regime or '跨声速' in flow_regime else '需要在边界层和流动分离区域保证足够的网格分辨率'}。{'从块的维度分析，部分块在某些方向上的网格点数较少（如最小维度仅为6-8个点），可能不足以充分解析该方向的流动梯度。' if any(min(b.get('dims', [999])) < 10 for b in datasets.get('blocks', [])) else ''}建议进行至少两级网格的细化对比研究，重点关注关键区域（如壁面附近、流动分离点、高梯度区域）的结果变化。此外，数据包未提供边界条件设置和湍流模型信息，这些对结果的可信度评估至关重要，建议在后续工作中补充。""",
            
            "conclusion": self._generate_rich_conclusion(facts, derived, flow_analysis, mesh_analysis, ops_summary, policy)
        }
        
        # 变量槽位 - 基于派生量生成深度分析
        if slot.slot_id.startswith("variable_"):
            var_name = slot.slot_id.replace("variable_", "")
            var_info = None
            for var in variables:
                if var.get("name") == var_name:
                    var_info = var
                    break
            
            if var_info:
                content = self._generate_variable_analysis(var_info, derived, flow_analysis, policy)
            else:
                content = f"变量{var_name}的数值分布在数据包中可见。该变量的物理意义需要结合具体应用场景进行解释。"
        else:
            content = content_templates.get(slot.slot_id, f"[{slot.placeholder_text}的内容待生成]")
        
        return {
            "content": content,
            "claims": [
                {"text": content[:100], "source": "DATA", "risk": "low"}
            ],
            "missing_info": [],
            "suggested_questions": []
        }
    
    def _generate_variable_analysis(
        self,
        var_info: Dict[str, Any],
        derived: Dict[str, Any],
        flow_analysis: Dict[str, Any],
        policy: Policy
    ) -> str:
        """为单个变量生成深度分析内容"""
        var_name = var_info.get('name', '')
        guess_name = var_info.get('guess_variableName', 'unknown')
        range_min = var_info.get('range_min', 0)
        range_max = var_info.get('range_max', 0)
        
        vel_est = derived.get('velocity_estimates', {})
        density_ratio = derived.get('density_ratio', 'N/A')
        flow_regime = derived.get('flow_regime', '待确认')
        correlations = derived.get('variable_correlations', [])
        
        has_reverse = range_min < 0 and range_max > 0
        span = range_max - range_min
        ratio = abs(range_max / range_min) if range_min != 0 else float('inf')
        
        descriptions = {
            'density': f"""密度（ρ）是可压缩流动计算中的基本守恒量，表示单位体积内流体的质量。在本数据包中，密度值范围为{range_min:.4e}至{range_max:.4e}，变化比约为{density_ratio}:1。这一密度变化表明流场中存在{'明显的压缩性效应，可能包含激波或强膨胀波等特征结构' if ratio > 5 else '一定的压缩性效应'}。密度最小值出现在高速膨胀区域，最大值对应压缩或滞止区域。在分布图中，应重点关注密度梯度集中的区域——这些区域通常对应激波面或强压缩区，同时低密度区域往往伴随流动加速现象。""",
            
            'MomentumX': f"""X方向动量（ρu）表示流体在X方向的动量密度，是密度与X方向速度的乘积。数值范围为{range_min:.4e}至{range_max:.4e}，{'存在正负值交替，表明流场中存在X方向的回流区域' if has_reverse else '数值均为正值，表明X方向流动方向一致'}。基于密度范围的估算，X方向速度分量的最大值约为{vel_est.get('u', {}).get('max_estimate', 0):.1f}。{'正负值的交界区域是流动分离点或再附着点的候选位置，在分布图中应重点关注这些零值等值线附近的流动结构。' if has_reverse else '动量的空间分布反映了主流的加速和减速过程，梯度集中区域可能对应几何变化或流动特征转变。'}作为主流方向的动量分量，其分布特征直接反映了流道内的流动加速、减速和可能的分离现象。""",
            
            'MomentumY': f"""Y方向动量（ρv）表示流体在Y方向的动量密度，反映了横向流动特征。数值范围为{range_min:.4e}至{range_max:.4e}，{'正负值共存表明存在显著的横向流动，可能由几何弯曲、旋转效应或二次流引起' if has_reverse else '数值以单一方向为主，横向流动效应相对较弱'}。在分布图中，应关注Y方向动量的高值区域，这些区域可能对应涡旋结构的核心或流动转向区域；Y方向动量为零的区域则可能是对称面或流动的分界面。对于{policy.domain if policy.domain != 'unknown' else '工程'}应用，横向流动的强度和分布对整体流动性能有重要影响。""",
            
            'MomentumZ': f"""Z方向动量（ρw）表示流体在Z方向的动量密度，是评估三维流动效应的关键变量。数值范围为{range_min:.4e}至{range_max:.4e}，{'正负值交替分布表明三维流动效应显著，流场具有明显的三维结构特征' if has_reverse else '数值分布特征表明Z方向流动相对较弱'}。Z方向动量的存在说明流动具有三维特性，需要进行完整的三维分析。在分布图中，Z方向动量的高值区域可能对应涡旋的轴向分量或三维分离结构。对于多块结构网格，Z方向通常对应周向或展向，其动量分布可以揭示流动的三维不稳定性和涡旋系统。""",
            
            'EnergyStagnationDensity': f"""总能量密度（ρE）是可压缩流动Euler/N-S方程中的第五个守恒量，包含内能和动能两部分。数值范围为{range_min:.4e}至{range_max:.4e}，能量比约为{derived.get('energy_analysis', {}).get('energy_ratio', 'N/A')}:1。总能量密度的空间分布反映了流场中能量的转换和传递过程——高能量区域通常对应高温或高速区域，低能量区域则对应低温或低速区域。基于守恒量的粗略估算，最大马赫数约为{derived.get('mach_estimate', {}).get('max_estimate', 'N/A')}（{derived.get('mach_estimate', {}).get('note', '仅供参考')}），流动状态判断为{flow_regime}。在分布图中，应关注能量梯度集中的区域，这些区域可能存在强烈的压缩或膨胀过程。结合密度和动量数据，可进一步推算压力、温度和马赫数等派生物理量。"""
        }
        
        content = descriptions.get(guess_name,
            f"""变量{var_name}对应{guess_name}，在本数据包中的数值范围为{range_min:.4e}至{range_max:.4e}，跨度为{span:.4e}。{'该变量存在正负值交替，表明对应的物理量在空间中存在方向变化。' if has_reverse else ''}该变量的分布特征反映了流场的物理状态，在分布图中应关注梯度集中区域和极值区域，这些位置通常对应重要的流动特征。"""
        )
        
        return content
    
    def _generate_rich_conclusion(
        self,
        facts: Dict[str, Any],
        derived: Dict[str, Any],
        flow_analysis: Dict[str, Any],
        mesh_analysis: Dict[str, Any],
        ops_summary: Dict[str, Any],
        policy: Policy
    ) -> str:
        """生成丰富的结论内容"""
        manifest = facts.get("manifest", {})
        datasets = facts.get("datasets", {})
        variables = facts.get("variables", [])
        
        dataset_type = manifest.get('dataset_type', 'Plot3D')
        block_count = manifest.get('block_count', datasets.get('block_count', 0))
        total_points = datasets.get('total_points', 0)
        
        flow_regime = derived.get('flow_regime', '待确认')
        density_ratio = derived.get('density_ratio', 'N/A')
        speed_max = derived.get('velocity_estimates', {}).get('speed_max', 0)
        mach_est = derived.get('mach_estimate', {}).get('max_estimate', 'N/A')
        correlations = derived.get('variable_correlations', [])
        findings = flow_analysis.get('key_findings', [])
        attention = flow_analysis.get('attention_points', [])
        ops_desc = ops_summary.get('description', '无') if ops_summary else '无'
        resolution = mesh_analysis.get('resolution_notes', [''])[0] if mesh_analysis.get('resolution_notes') else ''
        
        conclusion = f"""本次仿真分析基于{dataset_type}格式的多块结构网格数据，计算域由{block_count}个结构化网格块组成，总计{total_points:,}个网格节点，包含{len(variables)}个完整的流场守恒量变量（密度、三方向动量和总能量密度），数据格式符合Plot3D Q文件标准规范。

基于守恒量的派生分析，密度变化比约为{density_ratio}:1，最大合速度估算约为{speed_max:.1f}，流动状态初步判断为{flow_regime}。{'各方向动量分量均存在正负值交替，表明流场具有复杂的三维流动结构，' if len([c for c in correlations if '正负' in c]) > 1 else ''}{'可能包含流动分离、涡旋系统等特征现象。' if attention else '流场结构相对规则。'}

数据包已包含{ops_desc}等后处理可视化结果，为流场特征的直观分析提供了支持。{resolution}，网格规模适合进行工程级别的流场分析。

需要指出以下局限性：（1）数据包未提供残差收敛历史，无法直接评估计算的收敛性；（2）缺少边界条件和求解器设置信息，无法确定具体工况；（3）变量单位和无量纲化参考值未知，定量分析基于相对比较。建议在后续工作中补充上述信息，并进行网格独立性验证，以进一步提高分析结论的可信度和工程参考价值。"""
        
        return conclusion
    
    def rewrite_slot(
        self,
        slot: Slot,
        facts: Dict[str, Any],
        policy: Policy,
        reject_reason: str
    ) -> Dict[str, Any]:
        """改写被拒绝的槽位"""
        
        # 根据拒绝原因调整prompt
        rewrite_instructions = {
            "too_certain": "请使用更保守的措辞，添加'可能'、'初步显示'等限定词，强化缺失项声明。",
            "wrong_terminology": f"请按照术语偏好（{policy.terminology.get('var_style', 'original')}）重写术语。",
            "insufficient_missing": "请补充缺失信息说明，列出无法得出的结论。",
            "no_external_ref": "请移除所有外部引用，仅使用数据包中的信息。",
            "wrong_focus": f"请重新聚焦到用户关注的物理现象：{', '.join(policy.phenomena)}。"
        }
        
        instruction = rewrite_instructions.get(reject_reason, "请根据反馈改写内容。")
        
        prompt = f"""请改写以下槽位内容：

原内容：
{slot.content}

改写要求：
{instruction}

用户反馈：
{slot.user_feedback}

请直接输出改写后的正文内容，不要包含任何 JSON 格式或代码块标记。"""

        if self.use_mock:
            return {
                "content": f"[改写后] {slot.content[:100]}...",
                "claims": [],
                "missing_info": [],
                "suggested_questions": []
            }
        
        return self._call_llm(prompt, slot, facts=facts, policy=policy)


class BatchSlotFiller:
    """批量槽位填充器"""
    
    def __init__(self, slot_filler: SlotFiller):
        self.slot_filler = slot_filler
    
    def fill_all_slots(
        self,
        slots: List[Slot],
        facts: Dict[str, Any],
        policy: Policy,
        progress_callback = None
    ) -> List[Dict[str, Any]]:
        """填充所有槽位"""
        results = []
        total = len(slots)
        
        for i, slot in enumerate(slots):
            if slot.status != SlotStatus.PENDING:
                continue
            
            result = self.slot_filler.fill_slot(slot, facts, policy)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total, slot.slot_id)
        
        return results
    
    def fill_next_slot(
        self,
        slots: List[Slot],
        facts: Dict[str, Any],
        policy: Policy
    ) -> Optional[Dict[str, Any]]:
        """填充下一个待处理的槽位"""
        for slot in slots:
            if slot.status == SlotStatus.PENDING:
                return self.slot_filler.fill_slot(slot, facts, policy)
        
        return None
