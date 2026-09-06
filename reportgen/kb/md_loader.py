"""解析 Markdown 知识卡片（带 YAML Front Matter）"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class KnowledgeCard:
    """知识卡片"""
    id: str
    title: str
    content: str
    file_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def tags(self) -> List[str]:
        return self.metadata.get("tags", [])
    
    @property
    def report_modules(self) -> List[str]:
        return self.metadata.get("report_modules", [])
    
    @property
    def confidence(self) -> str:
        return self.metadata.get("confidence", "medium")
    
    @property
    def sources(self) -> List[str]:
        return self.metadata.get("sources", [])


def parse_front_matter(content: str) -> tuple:
    """
    解析 YAML Front Matter
    
    Returns:
        (metadata_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content
    
    # 查找结束标记
    end_match = re.search(r'\n---\s*\n', content[3:])
    if not end_match:
        return {}, content
    
    yaml_content = content[3:end_match.start() + 3]
    body_content = content[end_match.end() + 3:].strip()
    
    if not HAS_YAML:
        # 简单解析
        metadata = {}
        for line in yaml_content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # 简单处理列表
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
                metadata[key] = value
        return metadata, body_content
    
    try:
        metadata = yaml.safe_load(yaml_content)
        if metadata is None:
            metadata = {}
        return metadata, body_content
    except yaml.YAMLError:
        return {}, content


def load_single_card(file_path: Path) -> Optional[KnowledgeCard]:
    """加载单个知识卡片"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return None
    
    metadata, body = parse_front_matter(content)
    
    card_id = metadata.get("id", file_path.stem)
    title = metadata.get("title", file_path.stem)
    
    return KnowledgeCard(
        id=card_id,
        title=title,
        content=body,
        file_path=str(file_path),
        metadata=metadata
    )


def load_knowledge_cards(kb_dir: str) -> List[KnowledgeCard]:
    """
    加载知识库目录中的所有 Markdown 卡片
    
    Args:
        kb_dir: 知识库目录路径
        
    Returns:
        知识卡片列表
    """
    kb_path = Path(kb_dir)
    
    if not kb_path.exists():
        return []
    
    cards = []
    
    # 递归查找所有 .md 文件
    for md_file in kb_path.rglob("*.md"):
        # 跳过 README
        if md_file.name.lower() == "readme.md":
            continue
        
        card = load_single_card(md_file)
        if card:
            cards.append(card)
    
    return cards


def cards_to_documents(cards: List[KnowledgeCard]) -> List[Dict[str, Any]]:
    """
    将知识卡片转换为文档格式（用于向量化）
    
    Returns:
        文档列表，每个文档包含 page_content 和 metadata
    """
    documents = []
    for card in cards:
        doc = {
            "page_content": f"# {card.title}\n\n{card.content}",
            "metadata": {
                "id": card.id,
                "title": card.title,
                "tags": card.tags,
                "report_modules": card.report_modules,
                "confidence": card.confidence,
                "sources": card.sources,
                "file_path": card.file_path
            }
        }
        documents.append(doc)
    return documents
