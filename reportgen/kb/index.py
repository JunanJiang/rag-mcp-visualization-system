"""向量索引构建与加载 — 支持 Hybrid Search (Dense + BM25 + RRF)"""

import re
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False


class SimpleEmbedding:
    """简单的嵌入函数（当没有 sentence-transformers 时使用）"""
    
    def __init__(self):
        self.dim = 384
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """使用简单的哈希方法生成伪嵌入"""
        embeddings = []
        for text in texts:
            # 使用 MD5 哈希生成固定长度的向量
            hash_bytes = hashlib.md5(text.encode('utf-8')).digest()
            # 扩展到所需维度
            embedding = []
            for i in range(self.dim):
                byte_idx = i % len(hash_bytes)
                embedding.append((hash_bytes[byte_idx] - 128) / 128.0)
            embeddings.append(embedding)
        return embeddings


def _tokenize_chinese(text: str) -> List[str]:
    """简单的中英文混合分词（按字/词粒度）"""
    tokens = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text.lower())
    return tokens


class VectorIndex:
    """向量索引封装 — 支持 Dense、BM25、Hybrid 三种检索模式"""
    
    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir
        self.collection = None
        self.embedder = None
        self._bm25_index = None
        self._bm25_docs: List[Dict[str, Any]] = []
        self._bm25_corpus: List[List[str]] = []
        self._init_embedder()
        self._init_chroma()
    
    def _init_embedder(self):
        """初始化嵌入模型"""
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                # 设置较短超时，避免网络问题导致长时间等待
                import os
                os.environ.setdefault('HF_HUB_OFFLINE', '1')  # 优先使用本地缓存
                self.embedder = SentenceTransformer(
                    'paraphrase-multilingual-MiniLM-L12-v2',
                    device='cpu'
                )
            except Exception as e:
                print(f"[嵌入模型] 加载失败，使用简单哈希方法: {e}")
                self.embedder = SimpleEmbedding()
        else:
            self.embedder = SimpleEmbedding()
    
    def _init_chroma(self):
        """初始化 ChromaDB"""
        if not HAS_CHROMA:
            self.collection = None
            return
        
        try:
            if self.persist_dir:
                self.client = chromadb.PersistentClient(path=self.persist_dir)
            else:
                self.client = chromadb.Client()
            
            self.collection = self.client.get_or_create_collection(
                name="knowledge_cards",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"ChromaDB 初始化失败: {e}")
            self.collection = None
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """
        添加文档到索引
        
        Args:
            documents: 文档列表，每个包含 page_content 和 metadata
        """
        if not self.collection:
            return False
        
        ids = []
        contents = []
        metadatas = []
        
        for doc in documents:
            doc_id = doc["metadata"].get("id", hashlib.md5(doc["page_content"].encode()).hexdigest())
            ids.append(doc_id)
            contents.append(doc["page_content"])
            
            # ChromaDB 要求 metadata 值必须是基本类型
            meta = {}
            for k, v in doc["metadata"].items():
                if isinstance(v, list):
                    meta[k] = json.dumps(v, ensure_ascii=False)
                elif isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)
            metadatas.append(meta)
        
        embeddings = self.embedder.encode(contents)
        
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False
        
        # Build BM25 index in parallel
        if HAS_BM25:
            for i, doc_id in enumerate(ids):
                self._bm25_docs.append({
                    "id": doc_id,
                    "content": contents[i],
                    "metadata": metadatas[i]
                })
                self._bm25_corpus.append(_tokenize_chinese(contents[i]))
            try:
                self._bm25_index = BM25Okapi(self._bm25_corpus)
            except Exception as e:
                logger.warning(f"BM25 索引构建失败: {e}")
                self._bm25_index = None
        
        return True
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        filter_modules: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            filter_modules: 按 report_modules 过滤
            
        Returns:
            搜索结果列表
        """
        if not self.collection:
            return []
        
        # 生成查询嵌入
        query_embedding = self.embedder.encode([query])[0]
        
        # 注意：ChromaDB 不支持 $contains，改为不使用 where 过滤
        # 后续在结果中手动过滤
        where = None
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # 格式化结果
            formatted = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"][0]):
                    result = {
                        "id": doc_id,
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1 - results["distances"][0][i] if results["distances"] else 0
                    }
                    # 解析 JSON 格式的列表字段
                    for key in ["tags", "report_modules", "sources"]:
                        if key in result["metadata"] and isinstance(result["metadata"][key], str):
                            try:
                                result["metadata"][key] = json.loads(result["metadata"][key])
                            except json.JSONDecodeError:
                                pass
                    formatted.append(result)
            
            return formatted
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def _bm25_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """BM25 关键词检索"""
        if not self._bm25_index or not self._bm25_docs:
            return []
        
        tokens = _tokenize_chinese(query)
        if not tokens:
            return []
        
        scores = self._bm25_index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        max_score = ranked[0][1] if ranked and ranked[0][1] > 0 else 1
        for idx, score in ranked:
            if score <= 0:
                continue
            doc = self._bm25_docs[idx]
            results.append({
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": score / max_score
            })
        return results
    
    def hybrid_search(
        self, query: str, top_k: int = 5,
        filter_modules: Optional[List[str]] = None,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        混合检索：Dense + BM25，通过 RRF (Reciprocal Rank Fusion) 融合排序。
        
        RRF score = sum(1 / (k + rank_i)) across retrieval lists
        """
        dense_results = self.search(query, top_k=top_k * 2, filter_modules=filter_modules)
        
        if not HAS_BM25 or not self._bm25_index:
            return dense_results[:top_k]
        
        sparse_results = self._bm25_search(query, top_k=top_k * 2)
        
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}
        
        for rank, doc in enumerate(dense_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rrf_k + rank + 1)
            doc_map[doc_id] = doc
        
        for rank, doc in enumerate(sparse_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]
        
        merged = []
        for doc_id in sorted_ids:
            doc = doc_map[doc_id]
            doc["score"] = rrf_scores[doc_id]
            doc["_retrieval"] = "hybrid"
            merged.append(doc)
        
        return merged


def build_vector_index(documents: List[Dict[str, Any]], persist_dir: Optional[str] = None) -> VectorIndex:
    """
    构建向量索引
    
    Args:
        documents: 文档列表
        persist_dir: 持久化目录
        
    Returns:
        VectorIndex 实例
    """
    index = VectorIndex(persist_dir)
    index.add_documents(documents)
    return index


def load_vector_index(persist_dir: str) -> VectorIndex:
    """
    加载已有的向量索引
    
    Args:
        persist_dir: 持久化目录
        
    Returns:
        VectorIndex 实例
    """
    return VectorIndex(persist_dir)
