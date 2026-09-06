"""网络搜索模块 - 使用 Tavily Search API 进行联网搜索

优先使用 Tavily API（高质量结构化搜索），回退到模拟搜索。
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from .domains import is_trusted_domain, TRUSTED_DOMAINS

logger = logging.getLogger(__name__)

# Tavily API 端点
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str
    snippet: str
    domain: str
    relevance_score: float = 0.0
    is_trusted: bool = False


@dataclass
class EvidencePack:
    """证据包 - 用于槽位生成"""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    definitions: Dict[str, str] = field(default_factory=dict)
    standards: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": self.sources,
            "definitions": self.definitions,
            "standards": self.standards,
            "warnings": self.warnings,
            "search_queries": self.search_queries
        }
    
    def is_empty(self) -> bool:
        return not self.sources and not self.definitions


class WebSearcher:
    """网络搜索器 — 优先 Tavily API，回退 Mock"""
    
    def __init__(
        self,
        trusted_domains: List[str] = None,
        max_results: int = 5,
        timeout: int = 15,
        llm_api_key: str = None,
        use_mock: bool = False,
        tavily_api_key: str = None,
    ):
        self.trusted_domains = trusted_domains or TRUSTED_DOMAINS
        self.max_results = max_results
        self.timeout = timeout
        self.llm_api_key = llm_api_key

        # 从参数或环境变量获取 Tavily Key
        self.tavily_api_key = tavily_api_key or self._load_tavily_key()
        self.use_mock = use_mock and not self.tavily_api_key

        if self.tavily_api_key:
            logger.info("[WebSearcher] Tavily API 已配置，使用真实搜索")
        else:
            logger.warning("[WebSearcher] 未配置 Tavily API Key，将使用模拟搜索")

    @staticmethod
    def _load_tavily_key() -> str:
        """尝试从 config 或环境变量加载 Tavily Key"""
        import os
        key = os.environ.get('TAVILY_API_KEY', '')
        if not key:
            try:
                from config import TAVILY_API_KEY
                key = TAVILY_API_KEY
            except ImportError:
                pass
        return key

    # ─── 主入口 ───

    def search(
        self,
        query: str,
        domain_filter: List[str] = None,
        max_results: int = None
    ) -> List[SearchResult]:
        """执行搜索（同步）"""
        max_results = max_results or self.max_results

        # 优先 Tavily
        if self.tavily_api_key and not self.use_mock:
            try:
                return self._tavily_search(query, domain_filter, max_results)
            except Exception as e:
                logger.error(f"[Tavily] 搜索失败，回退 Mock: {e}")

        return self._mock_search(query, domain_filter, max_results)

    # ─── Tavily Search API ───

    def _tavily_search(
        self,
        query: str,
        domain_filter: List[str] = None,
        max_results: int = None
    ) -> List[SearchResult]:
        """调用 Tavily Search API"""
        max_results = max_results or self.max_results

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
        }

        # 可选：域名过滤
        if domain_filter:
            payload["include_domains"] = domain_filter

        resp = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        results: List[SearchResult] = []
        for item in data.get("results", []):
            url = item.get("url", "")
            domain = self._extract_domain(url)
            results.append(SearchResult(
                url=url,
                title=item.get("title", ""),
                snippet=item.get("content", "")[:500],
                domain=domain,
                relevance_score=round(item.get("score", 0.5), 3),
                is_trusted=is_trusted_domain(url),
            ))

        logger.info(f"[Tavily] query='{query}' → {len(results)} results")
        return results[:max_results]

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    # ─── Mock（回退/测试） ───

    def _mock_search(
        self,
        query: str,
        domain_filter: List[str] = None,
        max_results: int = None
    ) -> List[SearchResult]:
        """模拟搜索（用于测试或无 Tavily Key 时）"""
        max_results = max_results or self.max_results
        
        mock_results = [
            SearchResult(
                url="https://cfd-online.com/wiki/density",
                title="Density in CFD - CFD-Online Wiki",
                snippet="In computational fluid dynamics, density is a fundamental property representing mass per unit volume. For compressible flows, density varies significantly...",
                domain="cfd-online.com",
                relevance_score=0.95,
                is_trusted=True
            ),
            SearchResult(
                url="https://en.wikipedia.org/wiki/Computational_fluid_dynamics",
                title="Computational fluid dynamics - Wikipedia",
                snippet="Computational fluid dynamics (CFD) is a branch of fluid mechanics that uses numerical analysis and data structures to analyze and solve problems...",
                domain="wikipedia.org",
                relevance_score=0.90,
                is_trusted=True
            ),
            SearchResult(
                url="https://www.ansys.com/blog/cfd-simulation",
                title="CFD Simulation Guide - ANSYS",
                snippet="CFD simulation allows engineers to virtually test designs and optimize performance before physical prototyping...",
                domain="ansys.com",
                relevance_score=0.85,
                is_trusted=True
            ),
        ]
        
        if "密度" in query or "density" in query.lower():
            mock_results[0].snippet = "密度（Density）是流体力学中的基本物理量，表示单位体积的质量。在可压缩流动中，密度随压力和温度变化，是判断流动马赫数的关键参数。"
        elif "动量" in query or "momentum" in query.lower():
            mock_results[0].snippet = "动量（Momentum）在CFD中通常表示为ρu、ρv、ρw，即密度与速度分量的乘积。动量方程是Navier-Stokes方程的核心组成部分。"
        elif "能量" in query or "energy" in query.lower():
            mock_results[0].snippet = "总能量密度（Total Energy Density, ρE）包含流体的内能和动能。在可压缩流动计算中，能量方程用于求解温度场和热力学状态。"
        
        return mock_results[:max_results]
    
    def search_term_definition(
        self,
        domain: str,
        term: str,
        context: str = ""
    ) -> EvidencePack:
        """搜索术语定义"""
        queries = [
            f"{domain} {term} 定义 物理意义",
            f"{domain} CFD {term} meaning",
        ]
        
        evidence = EvidencePack(search_queries=queries)
        
        for query in queries:
            results = self.search(query, max_results=3)
            
            for result in results:
                if result.is_trusted:
                    evidence.sources.append({
                        "url": result.url,
                        "title": result.title,
                        "snippet": result.snippet,
                        "relevance": result.relevance_score
                    })
                    
                    # 提取定义
                    if term.lower() in result.snippet.lower():
                        evidence.definitions[term] = result.snippet
        
        return evidence
    
    def search_evaluation_criteria(
        self,
        domain: str,
        analysis_type: str
    ) -> EvidencePack:
        """搜索评定准则"""
        queries = [
            f"{domain} {analysis_type} 评定标准 规范",
            f"{domain} {analysis_type} evaluation criteria standard",
        ]
        
        evidence = EvidencePack(search_queries=queries)
        
        for query in queries:
            results = self.search(query, max_results=3)
            
            for result in results:
                if result.is_trusted:
                    evidence.sources.append({
                        "url": result.url,
                        "title": result.title,
                        "snippet": result.snippet,
                        "relevance": result.relevance_score
                    })
                    evidence.standards.append(result.snippet)
        
        return evidence
    
    def search_background_knowledge(
        self,
        domain: str,
        topics: List[str]
    ) -> EvidencePack:
        """搜索背景知识"""
        evidence = EvidencePack()
        
        for topic in topics:
            query = f"{domain} {topic} 原理 说明"
            evidence.search_queries.append(query)
            
            results = self.search(query, max_results=2)
            
            for result in results:
                if result.is_trusted:
                    evidence.sources.append({
                        "url": result.url,
                        "title": result.title,
                        "snippet": result.snippet,
                        "topic": topic,
                        "relevance": result.relevance_score
                    })
        
        return evidence


class MockWebSearcher(WebSearcher):
    """模拟搜索器 - 用于测试和演示"""
    
    def __init__(self, **kwargs):
        super().__init__(use_mock=True, **kwargs)
    
    def set_mock_results(self, results: List[Dict[str, Any]]):
        """设置模拟结果"""
        self._custom_mock_results = [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                domain=r.get("domain", ""),
                relevance_score=r.get("relevance", 0.8),
                is_trusted=r.get("is_trusted", True)
            )
            for r in results
        ]
    
    def _mock_search(self, query, domain_filter, max_results):
        if hasattr(self, '_custom_mock_results'):
            return self._custom_mock_results[:max_results]
        return super()._mock_search(query, domain_filter, max_results)
