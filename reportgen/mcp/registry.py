"""MCP Tool Registry — 插件式工具注册与分发

替代 app_v2.py 中的 if/elif 链式分发，支持装饰器注册、JSON Schema 导出、热插拔。
"""

import json
import logging
from typing import Dict, Any, Callable, Optional, List
from functools import wraps

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """MCP 工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
    
    def tool(self, name: str, *, description: str = "", schema: Dict = None, category: str = "other"):
        """装饰器：注册一个 MCP 工具
        
        Usage:
            @registry.tool("get_run_info", description="查询数据包元信息", category="data")
            def get_run_info(context, **args):
                ...
        """
        def decorator(func: Callable):
            self._tools[name] = {
                "name": name,
                "handler": func,
                "description": description,
                "schema": schema or {"type": "object", "properties": {}, "required": []},
                "category": category,
            }
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def register(self, name: str, handler: Callable, description: str = "", schema: Dict = None, category: str = "other"):
        """编程式注册工具"""
        self._tools[name] = {
            "name": name,
            "handler": handler,
            "description": description,
            "schema": schema or {"type": "object", "properties": {}, "required": []},
            "category": category,
        }
    
    def call(self, name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """调用指定工具，返回 JSON 字符串"""
        if name not in self._tools:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        
        tool_info = self._tools[name]
        handler = tool_info["handler"]
        
        try:
            result = handler(context or {}, **args)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"工具 {name} 执行失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有已注册工具（OpenAI function calling 格式）"""
        tools = []
        for name, info in self._tools.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["schema"],
                }
            })
        return tools
    
    def list_tools_summary(self) -> List[Dict[str, str]]:
        """列出工具摘要（名称+描述+类别）"""
        return [
            {"name": info["name"], "description": info["description"], "category": info["category"]}
            for info in self._tools.values()
        ]
    
    def has_tool(self, name: str) -> bool:
        return name in self._tools
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)
    
    def get_categories(self) -> Dict[str, List[str]]:
        """按类别分组返回工具名称"""
        cats: Dict[str, List[str]] = {}
        for name, info in self._tools.items():
            cat = info["category"]
            cats.setdefault(cat, []).append(name)
        return cats


# Global singleton
mcp_registry = MCPToolRegistry()
