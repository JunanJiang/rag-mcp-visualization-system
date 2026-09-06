"""知识库文件解析器

支持 PDF（PyMuPDF）、DOCX（python-docx）、TXT/MD，
将文档分块为 500 字左右的片段并返回结构化列表。

用法：
    from reportgen.kb.parser import parse_file
    chunks = parse_file("/path/to/doc.pdf", user_id=1, scope="personal")
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 500      # 每块目标字符数（中文约 500 字 ≈ 合理粒度）
_CHUNK_OVERLAP = 50    # 相邻块重叠字符数


def parse_file(
    file_path: str,
    user_id: int | None = None,
    org_id: int | None = None,
    scope: str = "personal",
    tags: List[str] | None = None,
    report_modules: List[str] | None = None,
    sources: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """解析文件，返回分块列表。

    每个块格式：
        {
            "page_content": str,
            "metadata": {
                "filename": str,
                "file_type": str,
                "page": int,
                "chunk_index": int,
                "user_id": int | None,
                "org_id": int | None,
                "scope": str,
            }
        }
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    filename = path.name
    tags = _normalize_list(tags)
    report_modules = _normalize_list(report_modules)
    sources = _normalize_list(sources)

    if suffix == ".pdf":
        raw_pages = _parse_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        raw_pages = _parse_docx(file_path)
    elif suffix in (".txt", ".md"):
        raw_pages = _parse_text(file_path)
    else:
        logger.warning(f"不支持的文件类型: {suffix}，尝试按纯文本处理")
        raw_pages = _parse_text(file_path)

    if suffix == ".md" and raw_pages:
        inferred_meta, body = _extract_markdown_metadata(raw_pages[0][1])
        raw_pages[0] = (raw_pages[0][0], body)
        if not tags:
            tags = _normalize_list(inferred_meta.get("tags"))
        if not report_modules:
            report_modules = _normalize_list(inferred_meta.get("report_modules"))
        if not sources:
            sources = _normalize_list(inferred_meta.get("sources"))

    chunks = []
    chunk_index = 0
    for page_num, text in raw_pages:
        for block in _chunk_text(text):
            if not block.strip():
                continue
            chunks.append({
                "page_content": block,
                "metadata": {
                    "filename": filename,
                    "file_type": suffix.lstrip("."),
                    "page": page_num,
                    "chunk_index": chunk_index,
                    "user_id": user_id,
                    "org_id": org_id,
                    "scope": scope,
                    "tags": tags,
                    "report_modules": report_modules,
                    "sources": sources,
                }
            })
            chunk_index += 1

    logger.info(f"解析完成: {filename}，共 {chunk_index} 块")
    return chunks


# ─────────────────────────────────────────────
# 各格式解析器
# ─────────────────────────────────────────────

def _parse_pdf(file_path: str) -> List[tuple]:
    """PDF → [(page_num, text), ...]，使用 PyMuPDF"""
    try:
        import fitz  # PyMuPDF
        pages = []
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages.append((i + 1, text))
        doc.close()
        return pages
    except ImportError:
        logger.warning("PyMuPDF 未安装，尝试 pypdf 回退")
        return _parse_pdf_pypdf(file_path)
    except Exception as e:
        logger.error(f"PyMuPDF 解析失败: {e}")
        return []


def _parse_pdf_pypdf(file_path: str) -> List[tuple]:
    """PDF 回退方案：pypdf"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i + 1, text))
        return pages
    except Exception as e:
        logger.error(f"pypdf 解析失败: {e}")
        return []


def _parse_docx(file_path: str) -> List[tuple]:
    """DOCX → [(1, full_text)]"""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)
        return [(1, full_text)] if full_text else []
    except Exception as e:
        logger.error(f"DOCX 解析失败: {e}")
        return []


def _parse_text(file_path: str) -> List[tuple]:
    """TXT / MD → [(1, full_text)]"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return [(1, text)] if text.strip() else []
    except Exception as e:
        logger.error(f"文本解析失败: {e}")
        return []


def _normalize_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = re.split(r"[,，\n]+", values)
    if not isinstance(values, (list, tuple, set)):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def _extract_markdown_metadata(text: str) -> tuple[Dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end_match = re.search(r'\n---\s*\n', text[3:])
    if not end_match:
        return {}, text
    yaml_content = text[3:end_match.start() + 3]
    body_content = text[end_match.end() + 3:].strip()
    try:
        import yaml
        metadata = yaml.safe_load(yaml_content) or {}
        return metadata if isinstance(metadata, dict) else {}, body_content
    except Exception:
        metadata = {}
        for line in yaml_content.split('\n'):
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('[') and value.endswith(']'):
                metadata[key] = [item.strip().strip('"\'') for item in value[1:-1].split(',') if item.strip()]
            else:
                metadata[key] = value
        return metadata, body_content


# ─────────────────────────────────────────────
# 分块算法
# ─────────────────────────────────────────────

def _chunk_text(text: str) -> List[str]:
    """将长文本按段落聚合为 ~CHUNK_SIZE 字的块，相邻块保留 OVERLAP 字符重叠。"""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 段落本身超长则强制按字符切割
        if len(para) > _CHUNK_SIZE * 2:
            for sub in _hard_split(para):
                if current:
                    chunks.append(current)
                    current = current[-_CHUNK_OVERLAP:] if _CHUNK_OVERLAP else ""
                current += sub
            continue

        if len(current) + len(para) + 1 <= _CHUNK_SIZE:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append(current)
                current = current[-_CHUNK_OVERLAP:] + "\n" + para if _CHUNK_OVERLAP else para
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str) -> List[str]:
    """对超长段落按 CHUNK_SIZE 硬切割"""
    parts = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        parts.append(text[start:end])
        start = end - _CHUNK_OVERLAP
    return parts


def get_supported_extensions() -> List[str]:
    """返回支持的文件扩展名列表"""
    return [".pdf", ".docx", ".doc", ".txt", ".md"]
