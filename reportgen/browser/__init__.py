"""Browser模块 - 网络搜索集成"""

from .search import WebSearcher
from .domains import TRUSTED_DOMAINS, is_trusted_domain

__all__ = ['WebSearcher', 'TRUSTED_DOMAINS', 'is_trusted_domain']
