"""DeepSeek API 客户端（OpenAI 兼容）"""

import os
import json
from typing import Dict, Any, Optional, List

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class DeepSeekClient:
    """DeepSeek API 客户端"""
    
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化 DeepSeek 客户端
        
        Args:
            api_key: API 密钥，默认从环境变量 DEEPSEEK_API_KEY 读取
            base_url: API 基础 URL
            model: 模型名称
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.client = None
        
        if HAS_OPENAI and self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
    
    @property
    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return self.client is not None and bool(self.api_key)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            json_mode: 是否启用 JSON 模式
            
        Returns:
            响应字典，包含 content, usage, error
        """
        if not self.is_available:
            return {
                "content": "",
                "usage": {},
                "error": "DeepSeek 客户端不可用（缺少 API Key 或 openai 库）"
            }
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content if response.choices else ""
            
            return {
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "error": None
            }
        except Exception as e:
            return {
                "content": "",
                "usage": {},
                "error": str(e)
            }
    
    def fill_slot(
        self,
        slot_id: str,
        slot_instruction: str,
        facts: Dict[str, Any],
        retrieved_cards: List[Dict[str, Any]],
        max_chars: int = 200,
        structured: bool = False,
        var_key: str = ""
    ) -> Dict[str, Any]:
        """
        填充单个槽位
        
        Args:
            slot_id: 槽位 ID
            slot_instruction: 槽位指令
            facts: 运行时事实
            retrieved_cards: 检索到的知识卡片
            max_chars: 最大输出字符数
            structured: 是否使用结构化解释块
            
        Returns:
            包含 text, cards_used, error 的字典
        """
        # 构建系统提示
        if structured and slot_id.startswith("result_"):
            system_prompt = f"""你是一个专业的 CFD 仿真报告撰写助手。请根据提供的数据事实和知识背景，为变量结果生成解释性文字。

必须输出4句话（总共120-200字）：
1. 变量是什么（通俗解释）
2. 本次数据范围 + 是否有明显跨度/正负分布（引用facts中的range）
3. 看图应关注什么现象（梯度集中区/高低值区位置）
4. 限制说明（缺少单位/边界条件时只能相对描述）

禁止：
- 不要编造数值或边界条件
- 不要堆砌公式
- 不要给出性能结论（效率/压比/推力）
- 缺少信息时写“数据包未提供，以下为相对描述”

直接输出连贯段落，不要加标题或编号。"""
        else:
            system_prompt = f"""你是一个专业的 CFD 仿真报告撰写助手。请根据提供的数据事实和知识背景，填写报告中的指定内容。

要求：
1. 输出必须简洁易懂，不超过 {max_chars} 个中文字符
2. 只使用提供的事实数据，不要编造数值
3. 如果数据不足，明确说明“数据包未包含该信息”
4. 避免复杂公式推导，使用工程描述语言
5. 直接输出内容，不要加任何前缀或解释"""

        # 构建用户消息
        facts_str = json.dumps(facts, ensure_ascii=False, indent=2)
        
        cards_str = ""
        for card in retrieved_cards[:3]:
            cards_str += f"\n### {card.get('title', 'Unknown')}\n{card.get('content', '')[:500]}\n"
        
        user_prompt = f"""## 任务
填写槽位：{slot_id}
指令：{slot_instruction}

## 数据事实
```json
{facts_str[:2000]}
```

## 相关知识背景
{cards_str if cards_str else "（无相关知识卡片）"}

请直接输出填充内容："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.chat(messages, temperature=0.5, max_tokens=500)
        
        return {
            "text": response["content"].strip(),
            "cards_used": [c.get("id", "") for c in retrieved_cards[:3]],
            "error": response.get("error")
        }


class DryRunClient:
    """Dry-run 模式客户端（不调用 LLM）"""
    
    # 变量解释模板（用于 dry-run 模式生成示例文本）
    VARIABLE_TEMPLATES = {
        "density": "密度表示单位体积内气体的质量，在可压缩流动中会随压力和温度变化。本次数据范围为 {min:.4f} ~ {max:.4f}，可观察到明显的梯度分布。图中高值区通常对应压缩区域，低值区可能为膨胀区。由于数据包未提供单位和无量纲参考，以上为相对描述。",
        "momentum": "动量表示气体流动的惯性，即密度与速度的乘积。本次数据范围为 {min:.4f} ~ {max:.4f}，正负值表示流动方向。图中应关注动量方向突变区域，可能存在流动分离或漩流。缺少边界条件信息，无法确定绝对速度大小。",
        "energy": "总能量密度包含内能和动能，是可压缩流中的关键守恒量。本次数据范围为 {min:.4f} ~ {max:.4f}，变化跨度较大。图中高能量区对应高温/高速区域，低值区为低温/低速区。缺少参考状态信息，以上为相对描述。"
    }
    
    def __init__(self):
        self.model = "dry-run"
    
    @property
    def is_available(self) -> bool:
        return True
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        return {
            "content": "[DRY-RUN] LLM 调用已跳过",
            "usage": {},
            "error": None
        }
    
    def fill_slot(
        self,
        slot_id: str,
        slot_instruction: str,
        facts: Dict[str, Any],
        retrieved_cards: List[Dict[str, Any]],
        max_chars: int = 200,
        structured: bool = False,
        var_key: str = ""
    ) -> Dict[str, Any]:
        """Dry-run 模式下返回模拟解释文本（不包含调试信息）"""
        
        # 对于结果槽位，生成模拟解释文本
        if slot_id.startswith("result_F1V") and var_key:
            var_name = slot_id.replace("result_", "")
            # 获取变量范围
            range_min, range_max = 0, 1
            for var in facts.get("variables", []):
                if var.get("name") == var_name:
                    range_min = var.get("range_min", 0)
                    range_max = var.get("range_max", 1)
                    break
            
            template = self.VARIABLE_TEMPLATES.get(var_key, self.VARIABLE_TEMPLATES["density"])
            text = template.format(min=range_min, max=range_max)
        else:
            # 其他槽位使用通用占位文本
            text = f"[待填充] {slot_instruction[:50]}..."
        
        return {
            "text": text,
            "cards_used": [c.get("id", "") for c in retrieved_cards[:3]],
            "error": None
        }
