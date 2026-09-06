"""多租户知识库管理器

三层集合策略：
  system        → 现有 .md 知识卡片，所有登录用户可查
  user_{id}     → 用户个人上传，仅本人可查
  org_{id}      → 组织共享，该组织全体成员可查

用法：
    from reportgen.kb.manager import KBManager
    mgr = KBManager(chroma_persist_dir="server/chroma_db", kb_files_dir="知识库")
    doc_id = mgr.upload_personal(user_id=1, file_path="report.pdf")
    chunks  = mgr.retrieve(user_id=1, org_ids=[3, 5], query="仿真分析方法")
"""

import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 将 server 目录加入 path，以便在 reportgen 包内也能 import database
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))


class KBManager:
    """多租户知识库管理器"""

    def __init__(self, chroma_persist_dir: str, kb_files_dir: str = ""):
        """
        Args:
            chroma_persist_dir: ChromaDB 持久化目录（所有集合共享该目录）
            kb_files_dir:       系统级 .md 知识卡片目录（用于 system 集合）
        """
        self.persist_dir = chroma_persist_dir
        self.kb_files_dir = kb_files_dir
        self._client = None
        self._embedder = None
        self._system_loaded = False
        self._init()

    # ─────────────────────────────────────────
    # 初始化
    # ─────────────────────────────────────────

    def _init(self):
        try:
            import chromadb
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._embedder = self._load_embedder()
            logger.info(f"KBManager 初始化成功，持久化目录: {self.persist_dir}")
        except Exception as e:
            logger.error(f"KBManager 初始化失败: {e}")

    def _load_embedder(self):
        try:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
        except Exception:
            from .index import SimpleEmbedding
            return SimpleEmbedding()

    def _collection(self, name: str):
        """获取或创建 ChromaDB 集合"""
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return self._embedder.encode(texts)

    def _normalize_meta_list(self, values: Any) -> List[str]:
        if values is None:
            return []
        if isinstance(values, str):
            values = values.replace("，", ",").replace("\r", "").replace("\n", ",").split(",")
        if not isinstance(values, (list, tuple, set)):
            return []
        return [str(v).strip() for v in values if str(v).strip()]

    def _extract_markdown_title(self, body: str, fallback_name: str) -> str:
        match = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
        return Path(fallback_name).stem.strip()

    def _infer_report_modules(self, text: str) -> List[str]:
        text = text.lower()
        modules: List[str] = []
        rules = [
            ("analysis_purpose", ["需求", "目标", "场景", "定位", "用途", "背景", "scope", "purpose"]),
            ("grid_description", ["网格", "grid"]),
            ("variable_analysis", ["变量", "速度", "压力", "流线", "云图", "回流", "再附着", "分析", "variable"]),
            ("assessment_criteria", ["评估", "质量", "规范", "标准", "准则", "复核", "审核", "criteria", "quality"]),
            ("conclusions", ["结论", "建议", "总结", "影响", "要求", "conclusion", "recommendation"]),
            ("geometry", ["几何", "结构", "台阶", "通道", "geometry"]),
        ]
        for module, keywords in rules:
            if any(keyword in text for keyword in keywords):
                modules.append(module)
        return modules or ["analysis_purpose"]

    def _infer_tags(self, title: str, body: str, scope: str) -> List[str]:
        tags: List[str] = []

        def push(value: str):
            value = value.strip(" -_—、，,。；;:：")
            if len(value) >= 2 and value not in tags:
                tags.append(value)

        cleaned_title = re.sub(r"\s+", " ", title).strip()
        for part in re.split(r"[\-—]\s*|\s{2,}|\s(?=[\u4e00-\u9fffA-Za-z])", cleaned_title):
            if len(part.strip()) >= 2:
                push(part)
        for keyword, tag in [
            ("组织", "组织协作"),
            ("团队", "团队规范"),
            ("规范", "文档规范"),
            ("需求", "需求清单"),
            ("场景", "场景分析"),
            ("质量", "质量评估"),
            ("评估", "质量评估"),
            ("报告", "报告编制"),
            ("变量", "变量分析"),
            ("回流", "回流分析"),
            ("压力", "压力分析"),
            ("可视化", "可视化"),
        ]:
            if keyword in cleaned_title or keyword in body:
                push(tag)
        if scope == "org":
            push("组织知识库")
        elif scope == "personal":
            push("个人知识库")
        return tags[:4]

    def _infer_sources(self, doc: Dict[str, Any], title: str) -> List[str]:
        filename = str(doc.get("filename") or title or "未命名文档")
        uploader = str(doc.get("uploader_display") or doc.get("uploader_name") or "").strip()
        if doc.get("scope") == "org":
            source_label = f"组织共享文档{f'（上传者：{uploader}）' if uploader else ''}"
        else:
            source_label = "个人知识文档"
        return [source_label, f"原始文件：{filename}"]

    def _hydrate_doc_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        tags = self._normalize_meta_list(doc.get("tags"))
        report_modules = self._normalize_meta_list(doc.get("report_modules"))
        sources = self._normalize_meta_list(doc.get("sources"))
        if tags and report_modules and sources:
            return doc

        file_path = Path(doc.get("file_path") or "")
        file_type = str(doc.get("file_type") or file_path.suffix.lstrip(".")).lower()
        if file_type != "md" or not file_path.exists():
            return doc

        try:
            from .parser import _extract_markdown_metadata
            import database as db

            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            inferred_meta, body = _extract_markdown_metadata(raw_text)
            title = self._extract_markdown_title(body, doc.get("filename") or file_path.name)
            next_tags = tags or self._normalize_meta_list(inferred_meta.get("tags")) or self._infer_tags(title, body, str(doc.get("scope") or ""))
            next_modules = report_modules or self._normalize_meta_list(inferred_meta.get("report_modules")) or self._infer_report_modules(f"{title}\n{body}")
            next_sources = sources or self._normalize_meta_list(inferred_meta.get("sources")) or self._infer_sources(doc, title)
            if next_tags == tags and next_modules == report_modules and next_sources == sources:
                return doc

            db.kb_update_document(doc["id"], tags=next_tags, report_modules=next_modules, sources=next_sources)
            updated = dict(doc)
            updated["tags"] = next_tags
            updated["report_modules"] = next_modules
            updated["sources"] = next_sources
            return updated
        except Exception as e:
            logger.debug(f"回填知识库文档元数据失败: {e}")
            return doc

    def hydrate_document_metadata(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return doc
        return self._hydrate_doc_metadata(doc)

    def _read_clean_markdown_body(self, doc: Dict[str, Any]) -> str:
        file_path = Path(doc.get("file_path") or "")
        file_type = str(doc.get("file_type") or file_path.suffix.lstrip(".")).lower()
        if file_type != "md" or not file_path.exists():
            return ""
        try:
            from .parser import _extract_markdown_metadata

            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            _, body = _extract_markdown_metadata(raw_text)
            return body.strip()
        except Exception as e:
            logger.debug(f"读取 Markdown 正文失败: {e}")
            return ""

    def _build_doc_preview(self, doc: Dict[str, Any], fallback_text: str = "") -> str:
        body = self._read_clean_markdown_body(doc)
        if body:
            return body[:150]
        return fallback_text[:150] if fallback_text else ""

    # ─────────────────────────────────────────
    # System KB 加载（.md 知识卡片）
    # ─────────────────────────────────────────

    def ensure_system_kb(self):
        """确保 system 集合已从 .md 文件加载。幂等操作。"""
        if self._system_loaded or not self.kb_files_dir:
            return
        try:
            from .md_loader import load_knowledge_cards, cards_to_documents
            cards = load_knowledge_cards(self.kb_files_dir)
            if not cards:
                self._system_loaded = True
                return
            col = self._collection("system")
            # 幂等：已存在则跳过
            existing_ids = set(col.get(include=[])["ids"])
            docs = cards_to_documents(cards)
            new_docs = [d for d in docs if d["metadata"]["id"] not in existing_ids]
            if new_docs:
                ids = [d["metadata"]["id"] for d in new_docs]
                contents = [d["page_content"] for d in new_docs]
                metas = [d["metadata"] for d in new_docs]
                embeddings = self._embed(contents)
                col.add(ids=ids, embeddings=embeddings, documents=contents, metadatas=metas)
                logger.info(f"system KB 加载了 {len(new_docs)} 张新卡片")
            self._system_loaded = True
        except Exception as e:
            logger.error(f"system KB 加载失败: {e}")

    # ─────────────────────────────────────────
    # 上传
    # ─────────────────────────────────────────

    def upload_personal(self, user_id: int, file_path: str,
                        tags: Optional[List[str]] = None,
                        report_modules: Optional[List[str]] = None,
                        sources: Optional[List[str]] = None) -> int:
        """解析文件并存入 user_{user_id} 集合，返回 db doc_id"""
        return self._upload(
            file_path=file_path,
            collection_name=f"user_{user_id}",
            user_id=user_id,
            org_id=None,
            scope="personal",
            tags=tags,
            report_modules=report_modules,
            sources=sources,
        )

    def upload_to_org(self, org_id: int, uploader_id: int, file_path: str,
                      tags: Optional[List[str]] = None,
                      report_modules: Optional[List[str]] = None,
                      sources: Optional[List[str]] = None) -> int:
        """解析文件并存入 org_{org_id} 集合，返回 db doc_id"""
        return self._upload(
            file_path=file_path,
            collection_name=f"org_{org_id}",
            user_id=uploader_id,
            org_id=org_id,
            scope="org",
            tags=tags,
            report_modules=report_modules,
            sources=sources,
        )

    def _upload(self, file_path: str, collection_name: str,
                user_id: Optional[int], org_id: Optional[int], scope: str,
                tags: Optional[List[str]] = None,
                report_modules: Optional[List[str]] = None,
                sources: Optional[List[str]] = None) -> int:
        from .parser import parse_file
        import database as db

        path = Path(file_path)
        chunks = parse_file(
            file_path,
            user_id=user_id,
            org_id=org_id,
            scope=scope,
            tags=tags,
            report_modules=report_modules,
            sources=sources,
        )
        if not chunks:
            raise ValueError(f"文件解析结果为空: {path.name}")

        # 写入 ChromaDB
        col = self._collection(collection_name)
        ids, contents, metas = [], [], []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{scope}_{user_id or 0}_{org_id or 0}_{path.stem}_{i}"
            ids.append(chunk_id)
            contents.append(chunk["page_content"])
            meta = {k: (str(v) if v is not None else "") for k, v in chunk["metadata"].items()}
            metas.append(meta)
        embeddings = self._embed(contents)
        col.add(ids=ids, embeddings=embeddings, documents=contents, metadatas=metas)

        # 写入 DB 元信息
        suffix = path.suffix.lstrip(".")
        doc_id = db.kb_add_document(
            user_id=user_id, org_id=org_id,
            filename=path.name, file_path=file_path,
            file_type=suffix, chunk_count=len(chunks), scope=scope,
            tags=tags, report_modules=report_modules, sources=sources,
        )

        # 写变更日志
        action_label = "upload"
        details = f"上传 {path.name}，共 {len(chunks)} 块"
        db.kb_log_change(doc_id, user_id or 0, org_id, action_label, path.name, details)

        logger.info(f"已上传到 {collection_name}: {path.name}，{len(chunks)} 块，doc_id={doc_id}")
        return doc_id

    # ─────────────────────────────────────────
    # 删除
    # ─────────────────────────────────────────

    def delete_document(self, doc_id: int, requester_id: int) -> bool:
        """删除文档（个人文档需所有者，组织文档需 org owner/admin）"""
        import database as db

        doc = db.kb_get_document(doc_id)
        if not doc:
            return False

        scope = doc["scope"]
        collection_name = (f"user_{doc['user_id']}" if scope == "personal"
                           else f"org_{doc['org_id']}")

        # 权限验证（允许文档所有者或组织 owner/admin 删除）
        if scope == "personal" and doc["user_id"] != requester_id:
            raise PermissionError("只有文档所有者才能删除个人知识库文档")

        # 删除 ChromaDB 中该文档的所有 chunks（通过 where 过滤 filename）
        try:
            col = self._collection(collection_name)
            result = col.get(where={"filename": doc["filename"]}, include=[])
            if result["ids"]:
                col.delete(ids=result["ids"])
        except Exception as e:
            logger.warning(f"ChromaDB 删除块失败: {e}")

        # 删除文件
        try:
            Path(doc["file_path"]).unlink(missing_ok=True)
        except Exception:
            pass

        # 更新 DB
        db.kb_log_change(
            doc_id, requester_id, doc.get("org_id"),
            "delete", doc["filename"], f"删除文档 {doc['filename']}"
        )
        db.kb_delete_document(doc_id)
        return True

    # ─────────────────────────────────────────
    # 编辑正文内容（仅文本类型）
    # ─────────────────────────────────────────

    # 允许在线编辑正文的文件类型（二进制类如 pdf/docx 不允许）
    _EDITABLE_CONTENT_SUFFIXES = {".md", ".markdown", ".txt"}

    def replace_document_content(self, doc_id: int, requester_id: int, new_content: str) -> int:
        """替换文档的正文内容：重写原文件 → 清理旧 chunks → 重新分块向量化 → 更新 DB。

        返回新的 chunk_count。
        权限：
            - personal 文档：requester_id 必须是文档所有者
            - org 文档：requester_id 必须是该组织成员（由上层路由校验后传入）
        仅允许 md / markdown / txt 文件；其它类型抛 ValueError。
        """
        from .parser import parse_file
        import database as db

        doc = db.kb_get_document(doc_id)
        if not doc:
            raise ValueError("文档不存在")

        scope = doc["scope"]
        path = Path(doc["file_path"])
        if path.suffix.lower() not in self._EDITABLE_CONTENT_SUFFIXES:
            raise ValueError(f"文件类型 {path.suffix} 不支持在线编辑正文（仅支持 .md / .markdown / .txt）")

        if scope == "personal":
            if doc["user_id"] != requester_id:
                raise PermissionError("只有文档所有者才能编辑个人知识库文档正文")
            collection_name = f"user_{doc['user_id']}"
        elif scope == "org":
            collection_name = f"org_{doc['org_id']}"
        else:
            raise ValueError(f"不支持编辑该文档类型：scope={scope}")

        # 1. 写回文件（UTF-8 LF，保证解析器稳定）
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_content, encoding="utf-8", newline="\n")
        except Exception as e:
            raise RuntimeError(f"写入文件失败：{e}") from e

        # 2. 删除 ChromaDB 中旧 chunks
        try:
            col = self._collection(collection_name)
            old_hits = col.get(where={"filename": doc["filename"]}, include=[])
            if old_hits.get("ids"):
                col.delete(ids=old_hits["ids"])
        except Exception as e:
            logger.warning(f"ChromaDB 清理旧 chunks 失败：{e}")

        # 3. 重新解析分块（保留既有 tags / report_modules / sources）
        chunks = parse_file(
            str(path),
            user_id=doc.get("user_id"),
            org_id=doc.get("org_id"),
            scope=scope,
            tags=doc.get("tags"),
            report_modules=doc.get("report_modules"),
            sources=doc.get("sources"),
        )
        if not chunks:
            raise ValueError("新正文解析结果为空，请确认内容非空白")

        # 4. 写入新 chunks
        col = self._collection(collection_name)
        ids, contents, metas = [], [], []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{scope}_{doc.get('user_id') or 0}_{doc.get('org_id') or 0}_{path.stem}_{i}"
            ids.append(chunk_id)
            contents.append(chunk["page_content"])
            meta = {k: (str(v) if v is not None else "") for k, v in chunk["metadata"].items()}
            metas.append(meta)
        embeddings = self._embed(contents)
        col.add(ids=ids, embeddings=embeddings, documents=contents, metadatas=metas)

        # 5. 更新 DB chunk_count
        with __import__("database").get_db() as conn:
            conn.execute(
                "UPDATE kb_documents SET chunk_count = ? WHERE id = ?",
                (len(chunks), doc_id),
            )

        # 6. 写变更日志
        db.kb_log_change(
            doc_id, requester_id, doc.get("org_id"),
            "edit_content", doc["filename"],
            f"编辑正文：{path.name}，重建 {len(chunks)} 块",
        )

        logger.info(f"已编辑文档正文 doc_id={doc_id} ({scope})：{path.name}，新 chunk_count={len(chunks)}")
        return len(chunks)

    # ─────────────────────────────────────────
    # 检索（三层合并）
    # ─────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        user_id: int,
        org_ids: List[int],
        role: str = "user",
        top_k: int = 5,
        min_score: float = 0.0,
        enable_system: bool = True,
        enable_personal: bool = True,
        enable_org: bool = True,
    ) -> List[Dict[str, Any]]:
        """合并检索 personal + org + system，按相关度排序返回。"""
        if enable_system:
            self.ensure_system_kb()
        query_emb = self._embed([query])[0]

        collections_to_search: List[str] = []
        if enable_personal:
            collections_to_search.append(f"user_{user_id}")
        if enable_org:
            for oid in org_ids:
                collections_to_search.append(f"org_{oid}")
        if enable_system:
            collections_to_search.append("system")

        all_results: List[Dict[str, Any]] = []
        seen_ids = set()

        for col_name in collections_to_search:
            try:
                col = self._collection(col_name)
                count = col.count()
                if count == 0:
                    continue
                n = min(top_k, count)
                res = col.query(query_embeddings=[query_emb], n_results=n)
                if not res or not res["ids"]:
                    continue
                for i, cid in enumerate(res["ids"][0]):
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    score = 1 - (res["distances"][0][i] if res["distances"] else 0)
                    if score < min_score:
                        continue
                    all_results.append({
                        "id": cid,
                        "content": res["documents"][0][i] if res["documents"] else "",
                        "metadata": res["metadatas"][0][i] if res["metadatas"] else {},
                        "score": round(score, 4),
                        "collection": col_name,
                    })
            except Exception as e:
                logger.debug(f"检索 {col_name} 失败（可能集合不存在）: {e}")

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    # ─────────────────────────────────────────
    # 列表
    # ─────────────────────────────────────────

    def list_personal(self, user_id: int) -> List[Dict]:
        import database as db
        docs = db.kb_list_personal(user_id)
        docs = [self._hydrate_doc_metadata(doc) for doc in docs]
        # 为每个文档补充 content_preview
        col_name = f"user_{user_id}"
        try:
            col = self._collection(col_name)
            for doc in docs:
                try:
                    result = col.get(
                        where={"filename": doc["filename"]},
                        include=["documents"],
                        limit=1,
                    )
                    if result and result["documents"]:
                        doc["content_preview"] = self._build_doc_preview(doc, result["documents"][0])
                    else:
                        doc["content_preview"] = self._build_doc_preview(doc)
                except Exception:
                    doc["content_preview"] = self._build_doc_preview(doc)
        except Exception:
            for doc in docs:
                doc["content_preview"] = self._build_doc_preview(doc)
        return docs

    def get_personal_doc_content(self, user_id: int, doc_id: int) -> str:
        """获取个人文档的完整内容（合并所有 chunk）"""
        import database as db
        doc = db.kb_get_document(doc_id)
        if not doc or doc["user_id"] != user_id or doc["scope"] != "personal":
            return ""
        body = self._read_clean_markdown_body(doc)
        if body:
            return body
        col_name = f"user_{user_id}"
        try:
            col = self._collection(col_name)
            result = col.get(
                where={"filename": doc["filename"]},
                include=["documents"],
            )
            if result and result["documents"]:
                return "\n\n".join(result["documents"])
        except Exception:
            pass
        return ""

    def get_org_doc_content(self, org_id: int, doc_id: int) -> str:
        """获取组织文档的完整内容（合并所有 chunk）"""
        import database as db
        doc = db.kb_get_document(doc_id)
        if not doc or doc["org_id"] != org_id or doc["scope"] != "org":
            return ""
        body = self._read_clean_markdown_body(doc)
        if body:
            return body
        col_name = f"org_{org_id}"
        try:
            col = self._collection(col_name)
            res = col.get(where={"filename": doc["filename"]}, include=["documents", "metadatas"])
            pairs = []
            for text, meta in zip(res.get("documents", []), res.get("metadatas", [])):
                pos = int(meta.get("chunk_index", 0) or 0)
                pairs.append((pos, text))
            pairs.sort(key=lambda x: x[0])
            return "\n\n".join(text for _, text in pairs)
        except Exception:
            pass
        return ""

    def list_org(self, org_id: int) -> List[Dict]:
        import database as db
        docs = db.kb_list_org(org_id)
        docs = [self._hydrate_doc_metadata(doc) for doc in docs]
        col_name = f"org_{org_id}"
        try:
            col = self._collection(col_name)
            for doc in docs:
                try:
                    result = col.get(
                        where={"filename": doc["filename"]},
                        include=["documents"],
                        limit=1,
                    )
                    if result and result["documents"]:
                        doc["content_preview"] = self._build_doc_preview(doc, result["documents"][0])
                    else:
                        doc["content_preview"] = self._build_doc_preview(doc)
                except Exception:
                    doc["content_preview"] = self._build_doc_preview(doc)
        except Exception:
            for doc in docs:
                doc["content_preview"] = self._build_doc_preview(doc)
        return docs

    def get_personal_log(self, user_id: int, limit: int = 100) -> List[Dict]:
        import database as db
        return db.kb_get_personal_log(user_id, limit)

    def get_org_log(self, org_id: int, limit: int = 100) -> List[Dict]:
        import database as db
        return db.kb_get_org_log(org_id, limit)

    def delete_org_collection(self, org_id: int) -> None:
        if not self._client:
            return
        try:
            self._client.delete_collection(f"org_{org_id}")
        except Exception:
            pass
