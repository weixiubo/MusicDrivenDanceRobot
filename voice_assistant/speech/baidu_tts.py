#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度语音合成模块
处理文字转语音功能
"""

import os
import time
import tempfile
import requests
import threading
from typing import Optional
from urllib.parse import urlencode

from ..config import config


class BaiduTTS:
    """百度语音合成客户端"""
    
    def __init__(self, api_key: str, secret_key: str, voice_person: int = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0
        self.voice_person = voice_person or config.TTS_DEFAULT_VOICE
        
        # 获取访问令牌
        self._get_access_token()
    
    def _get_access_token(self) -> bool:
        """获取百度API访问令牌"""
        try:
            url = config.BAIDU_TOKEN_URL
            params = {
                'grant_type': 'client_credentials',
                'client_id': self.api_key,
                'client_secret': self.secret_key
            }
            
            response = requests.post(url, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if 'access_token' in result:
                    self.access_token = result['access_token']
                    self.token_expires_at = time.time() + (29 * 24 * 60 * 60)
                    return True
            
            return False
                
        except Exception as e:
            print(f"❌ 获取TTS令牌异常: {e}")
            return False
    
    def _is_token_valid(self) -> bool:
        """检查令牌是否有效"""
        return (self.access_token is not None and 
                time.time() < self.token_expires_at)
    
    def _ensure_valid_token(self) -> bool:
        """确保令牌有效"""
        if not self._is_token_valid():
            return self._get_access_token()
        return True
    
    def _clean_text_for_tts(self, text: str) -> str:
        """清理文本，移除TTS不支持的字符"""
        # 移除markdown格式
        import re
        
        # 移除markdown标题
        text = re.sub(r'#+\s*', '', text)
        
        # 移除markdown粗体和斜体
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # 移除markdown代码块
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # 移除特殊符号
        text = re.sub(r'[#*`\[\](){}]', '', text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def speak(self, text: str, volume_level: int = None, tts_manager=None, async_mode: bool = True) -> bool:
        """语音合成并播放 - 基于百度官方示例"""
        if not self._ensure_valid_token():
            print("❌ 无法获取有效的TTS访问令牌")
            return False

        # 清理文本
        cleaned_text = self._clean_text_for_tts(text)
        if not cleaned_text:
            print("⚠️ 清理后的文本为空，跳过TTS")
            return False

        print(f"🎵 百度TTS合成: {cleaned_text[:50]}{'...' if len(cleaned_text) > 50 else ''}")

        def _play_audio():
            try:
                # 按照百度官方示例准备参数
                from urllib.parse import quote_plus, urlencode

                tex = quote_plus(cleaned_text)  # 文本需要URL编码
                params = {
                    'tok': self.access_token,
                    'tex': tex,
                    'per': self.voice_person,  # 发音人
                    'spd': 5,  # 语速
                    'pit': 5,  # 音调
                    'vol': volume_level or config.TTS_DEFAULT_VOLUME,  # 音量
                    'aue': 3,  # MP3格式
                    'cuid': 'python_client',
                    'lan': 'zh',
                    'ctp': 1
                }

                # 发送请求 - 按照官方示例
                data = urlencode(params)
                req_url = f"{config.BAIDU_TTS_URL}?{data}"

                response = requests.get(req_url, timeout=30)

                if response.status_code == 200:
                    # 检查是否为音频数据
                    headers = dict((name.lower(), value) for name, value in response.headers.items())
                    has_error = ('content-type' not in headers.keys() or headers['content-type'].find('audio/') < 0)

                    if not has_error:
                        # 保存音频文件
                        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                            temp_filename = temp_file.name
                            temp_file.write(response.content)

                        print(f"🎵 音频文件已生成: {len(response.content)} bytes")

                        # 简单直接的播放方式
                        played = False

                        # 优先使用mpg123 - 最直接的MP3播放器
                        if os.system(f"which mpg123 > /dev/null 2>&1") == 0:
                            print("🎵 使用mpg123播放...")
                            result = os.system(f"mpg123 '{temp_filename}' > /dev/null 2>&1")
                            if result == 0:
                                played = True
                                print("✅ mpg123播放完成")

                        # 备用方案：aplay + 转换
                        if not played and os.system(f"which aplay > /dev/null 2>&1") == 0:
                            print("🎵 转换并使用aplay播放...")
                            wav_filename = temp_filename.replace('.mp3', '.wav')
                            if os.system(f"which ffmpeg > /dev/null 2>&1") == 0:
                                convert_cmd = f"ffmpeg -i '{temp_filename}' '{wav_filename}' > /dev/null 2>&1"
                                if os.system(convert_cmd) == 0:
                                    play_cmd = f"aplay '{wav_filename}' > /dev/null 2>&1"
                                    if os.system(play_cmd) == 0:
                                        played = True
                                        print("✅ aplay播放完成")
                                    os.remove(wav_filename)

                        # 清理临时文件
                        os.remove(temp_filename)

                        if not played:
                            print("⚠️ 音频播放失败，但TTS合成成功")

                        print("✅ 百度TTS处理完成")
                    else:
                        # 错误响应
                        error_info = response.text
                        print(f"❌ TTS API错误: {error_info}")
                else:
                    print(f"❌ TTS请求失败，状态码: {response.status_code}")

            except Exception as e:
                print(f"❌ 百度TTS异常: {e}")

        def _play_with_callback():
            try:
                _play_audio()
            finally:
                if tts_manager:
                    tts_manager.is_speaking = False

        if async_mode:
            thread = threading.Thread(target=_play_with_callback)
            thread.daemon = True
            thread.start()
        else:
            _play_with_callback()

        return True


def create_baidu_tts(voice_person: int = None) -> Optional[BaiduTTS]:
    """创建百度TTS实例"""
    if not config.BAIDU_API_KEY or not config.BAIDU_SECRET_KEY:
        print("❌ 百度API密钥未配置")
        return None

    return BaiduTTS(config.BAIDU_API_KEY, config.BAIDU_SECRET_KEY, voice_person)
