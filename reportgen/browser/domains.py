"""可信域名白名单配置"""

from typing import List
from urllib.parse import urlparse

# 可信域名白名单
TRUSTED_DOMAINS: List[str] = [
    # 百科/知识库
    "wikipedia.org",
    "en.wikipedia.org",
    "zh.wikipedia.org",
    "baike.baidu.com",
    "zhihu.com",
    "www.zhihu.com",
    
    # CFD/仿真技术
    "cfd-online.com",
    "www.cfd-online.com",
    "ansys.com",
    "www.ansys.com",
    "comsol.com",
    "www.comsol.com",
    "openfoam.com",
    "www.openfoam.org",
    "simscale.com",
    "www.simscale.com",
    
    # 学术资源
    "sciencedirect.com",
    "www.sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "researchgate.net",
    "www.researchgate.net",
    "arxiv.org",
    
    # 工程技术
    "engineering.com",
    "www.engineering.com",
    "engineeringtoolbox.com",
    "www.engineeringtoolbox.com",
    
    # 标准/规范
    "iso.org",
    "www.iso.org",
    "asme.org",
    "www.asme.org",
    "aiaa.org",
    "www.aiaa.org",
    
    # 中文技术社区
    "cnki.net",
    "www.cnki.net",
    "csdn.net",
    "blog.csdn.net",
]

# 域名分类
DOMAIN_CATEGORIES = {
    "encyclopedia": ["wikipedia.org", "baike.baidu.com"],
    "cfd_simulation": ["cfd-online.com", "ansys.com", "comsol.com", "openfoam.com", "simscale.com"],
    "academic": ["sciencedirect.com", "springer.com", "researchgate.net", "arxiv.org", "cnki.net"],
    "engineering": ["engineering.com", "engineeringtoolbox.com"],
    "standards": ["iso.org", "asme.org", "aiaa.org"],
    "community": ["zhihu.com", "csdn.net"],
}


def is_trusted_domain(url: str) -> bool:
    """检查URL是否来自可信域名"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀进行匹配
        if domain.startswith("www."):
            domain_without_www = domain[4:]
        else:
            domain_without_www = domain
        
        for trusted in TRUSTED_DOMAINS:
            trusted_clean = trusted.lower()
            if trusted_clean.startswith("www."):
                trusted_clean = trusted_clean[4:]
            
            if domain_without_www == trusted_clean or domain_without_www.endswith("." + trusted_clean):
                return True
        
        return False
    except Exception:
        return False


def get_domains_for_category(category: str) -> List[str]:
    """获取特定分类的域名列表"""
    return DOMAIN_CATEGORIES.get(category, [])


def get_search_domains(categories: List[str] = None) -> List[str]:
    """获取搜索时使用的域名列表"""
    if categories is None:
        return TRUSTED_DOMAINS
    
    domains = []
    for cat in categories:
        domains.extend(get_domains_for_category(cat))
    
    return list(set(domains)) if domains else TRUSTED_DOMAINS
