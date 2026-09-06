"""MCP Tool Observer — 工具调用可观测性

记录每次工具调用的时间戳、耗时、参数、结果摘要、成功/失败。
提供统计分析 API 数据。
"""

import time
import json
import logging
import sqlite3
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolObserver:
    """工具调用观测器"""
    
    def __init__(self, db_path: str = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._in_memory_logs: List[Dict[str, Any]] = []
        self._max_memory = 500
        
        if db_path:
            self._init_db()
    
    def _init_db(self):
        """初始化 SQLite 表"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    args_json TEXT DEFAULT '{}',
                    result_preview TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    error_message TEXT DEFAULT '',
                    duration_ms REAL DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    session_id TEXT DEFAULT ''
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"ToolObserver DB 初始化失败: {e}")
            self._db_path = None
    
    def record(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str,
        success: bool,
        duration_ms: float,
        category: str = "",
        session_id: str = "",
        error_message: str = ""
    ):
        """记录一次工具调用"""
        log_entry = {
            "tool_name": tool_name,
            "category": category,
            "args": args,
            "result_preview": result[:300] if result else "",
            "success": success,
            "error_message": error_message,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
        }
        
        with self._lock:
            self._in_memory_logs.append(log_entry)
            if len(self._in_memory_logs) > self._max_memory:
                self._in_memory_logs = self._in_memory_logs[-self._max_memory:]
        
        if self._db_path:
            try:
                conn = sqlite3.connect(self._db_path)
                conn.execute(
                    "INSERT INTO tool_call_logs (tool_name, category, args_json, result_preview, success, error_message, duration_ms, timestamp, session_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (tool_name, category, json.dumps(args, ensure_ascii=False)[:500], result[:300], int(success), error_message, duration_ms, log_entry["timestamp"], session_id)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"ToolObserver 写入 DB 失败: {e}")
    
    def observe_call(self, tool_name: str, args: Dict[str, Any], call_fn, category: str = "", session_id: str = "") -> str:
        """包装工具调用，自动记录时间和结果"""
        start = time.time()
        try:
            result = call_fn()
            duration_ms = (time.time() - start) * 1000
            success = True
            error_msg = ""
            try:
                parsed = json.loads(result) if isinstance(result, str) else result
                if isinstance(parsed, dict) and "error" in parsed:
                    success = False
                    error_msg = parsed["error"]
            except Exception:
                pass
            self.record(tool_name, args, result if isinstance(result, str) else json.dumps(result), success, duration_ms, category, session_id, error_msg)
            return result
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.record(tool_name, args, "", False, duration_ms, category, session_id, str(e))
            raise
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的调用记录"""
        with self._lock:
            return list(reversed(self._in_memory_logs[-limit:]))
    
    def get_analytics(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        with self._lock:
            logs = self._in_memory_logs
        
        if not logs:
            return {"total_calls": 0, "tools": {}, "avg_duration_ms": 0, "success_rate": 1.0}
        
        total = len(logs)
        success_count = sum(1 for l in logs if l["success"])
        
        tool_stats: Dict[str, Dict[str, Any]] = {}
        for log in logs:
            name = log["tool_name"]
            if name not in tool_stats:
                tool_stats[name] = {"count": 0, "total_duration": 0, "errors": 0}
            tool_stats[name]["count"] += 1
            tool_stats[name]["total_duration"] += log["duration_ms"]
            if not log["success"]:
                tool_stats[name]["errors"] += 1
        
        for name, stats in tool_stats.items():
            stats["avg_duration_ms"] = round(stats["total_duration"] / stats["count"], 2) if stats["count"] > 0 else 0
        
        total_duration = sum(l["duration_ms"] for l in logs)
        
        return {
            "total_calls": total,
            "success_rate": round(success_count / total, 3) if total > 0 else 1.0,
            "avg_duration_ms": round(total_duration / total, 2) if total > 0 else 0,
            "tools": tool_stats,
            "by_category": self._group_by_category(logs),
        }
    
    @staticmethod
    def _group_by_category(logs: List[Dict]) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for l in logs:
            cat = l.get("category", "other")
            cats[cat] = cats.get(cat, 0) + 1
        return cats


# Global singleton
tool_observer = ToolObserver()


def init_observer(db_path: str):
    """初始化全局 observer（带 DB 持久化）"""
    global tool_observer
    tool_observer = ToolObserver(db_path)
    return tool_observer
