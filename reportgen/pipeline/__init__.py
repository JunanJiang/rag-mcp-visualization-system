"""Pipeline 模块：报告生成流水线"""

from .build_facts import build_run_facts
from .build_md import build_markdown_report
from .build_docx import build_docx_report

__all__ = ["build_run_facts", "build_markdown_report", "build_docx_report"]
