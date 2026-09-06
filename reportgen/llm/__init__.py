"""LLM 模块：DeepSeek API 调用、提示词管理"""

from .deepseek_client import DeepSeekClient
from .prompts import get_slot_prompt, SLOT_INSTRUCTIONS

__all__ = ["DeepSeekClient", "get_slot_prompt", "SLOT_INSTRUCTIONS"]
