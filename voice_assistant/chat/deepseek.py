#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek AI聊天模块
处理与DeepSeek API的交互
"""

import requests
from typing import Optional, List, Dict

from ..config import config


class DeepSeekChat:
    """DeepSeek聊天客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = config.DEEPSEEK_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # 初始化对话历史，包含系统提示
        self.conversation_history = [
            {
                "role": "system", 
                "content": config.AI_SYSTEM_PROMPT
            }
        ]
    
    def add_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_response(self, user_input: str) -> Optional[str]:
        """获取AI回复"""
        self.add_message("user", user_input)
        
        data = {
            "model": config.DEEPSEEK_MODEL,
            "messages": self.conversation_history,
            "stream": False,
            "temperature": config.DEEPSEEK_TEMPERATURE,
            "max_tokens": config.DEEPSEEK_MAX_TOKENS,
        }
        
        try:
            print("🤖 AI思考中...")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=config.DEEPSEEK_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"]
                self.add_message("assistant", ai_response)
                return ai_response
            else:
                print(f"❌ API错误: {response.status_code}")
                if response.status_code == 401:
                    print("💡 请检查DEEPSEEK_API_KEY是否正确")
                elif response.status_code == 429:
                    print("💡 API调用频率过高，请稍后重试")
                return None
        
        except requests.exceptions.Timeout:
            print("❌ 请求超时，请检查网络连接")
            return None
        except requests.exceptions.ConnectionError:
            print("❌ 连接失败，请检查网络连接")
            return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    def clear_history(self):
        """清空对话历史（保留系统提示）"""
        self.conversation_history = [
            {
                "role": "system", 
                "content": config.AI_SYSTEM_PROMPT
            }
        ]
        print("🧹 对话历史已清空")
    
    def get_conversation_count(self) -> int:
        """获取对话轮数（不包括系统提示）"""
        return (len(self.conversation_history) - 1) // 2
    
    def get_last_response(self) -> Optional[str]:
        """获取最后一次AI回复"""
        for message in reversed(self.conversation_history):
            if message["role"] == "assistant":
                return message["content"]
        return None
    
    def export_conversation(self) -> List[Dict[str, str]]:
        """导出对话历史"""
        return self.conversation_history.copy()
    
    def import_conversation(self, conversation: List[Dict[str, str]]):
        """导入对话历史"""
        # 验证格式
        if not isinstance(conversation, list):
            raise ValueError("对话历史必须是列表格式")
        
        for message in conversation:
            if not isinstance(message, dict) or "role" not in message or "content" not in message:
                raise ValueError("对话消息格式错误")
            
            if message["role"] not in ["system", "user", "assistant"]:
                raise ValueError(f"无效的角色: {message['role']}")
        
        self.conversation_history = conversation
        print("📥 对话历史已导入")


def create_deepseek_chat() -> Optional[DeepSeekChat]:
    """创建DeepSeek聊天实例"""
    if not config.DEEPSEEK_API_KEY:
        print("❌ DeepSeek API密钥未配置")
        return None
    
    return DeepSeekChat(config.DEEPSEEK_API_KEY)
