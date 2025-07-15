#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度语音识别模块
处理语音转文字功能
"""

import os
import time
import json
import base64
import requests
from typing import Optional

from ..config import config


class BaiduASR:
    """百度语音识别客户端"""
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0
        
        # 获取访问令牌
        self._get_access_token()
    
    def _get_access_token(self) -> bool:
        """获取百度API访问令牌"""
        try:
            print("🔑 获取百度API访问令牌...")
            
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
                    # 令牌有效期通常是30天，这里设置为29天后过期
                    self.token_expires_at = time.time() + (29 * 24 * 60 * 60)
                    print("✅ 百度API令牌获取成功")
                    return True
                else:
                    print(f"❌ 令牌响应中没有access_token: {result}")
                    return False
            else:
                print(f"❌ 获取令牌失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取令牌异常: {e}")
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
    
    def recognize_audio_file(self, audio_file_path: str) -> Optional[str]:
        """识别音频文件"""
        if not self._ensure_valid_token():
            print("❌ 无法获取有效的访问令牌")
            return None
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(audio_file_path)
            if file_size < config.ASR_MIN_FILE_SIZE:
                print("🔇 音频文件太小，可能没有录到声音")
                return None
            
            print(f"📁 录音文件: {file_size/1024:.1f}KB")
            
            # 读取音频文件
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            # 获取音频信息
            import wave
            with wave.open(audio_file_path, 'rb') as wf:
                frames = wf.getnframes()
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()

            print(f"📊 音频信息: {sample_rate}Hz, {channels}声道, {sample_width*8}位, {frames}帧")

            # 百度API采样率处理 - 现在统一使用16000Hz
            api_sample_rate = sample_rate
            if sample_rate == 16000:
                print(f"✅ 使用原生16000Hz，与百度API完美兼容")
            else:
                print(f"⚠️ 非标准采样率{sample_rate}Hz，可能影响识别效果")

            # Base64编码
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            # 音频质量检查
            audio_energy = sum(abs(x) for x in audio_data) / len(audio_data)
            print(f"🔍 音频能量: {audio_energy:.1f}")

            if audio_energy < 50:
                print("⚠️ 音频能量过低，可能影响识别效果")

            # 准备请求数据 - 按照百度官方示例格式
            data = {
                'format': 'wav',
                'rate': api_sample_rate,
                'channel': channels,
                'cuid': 'python_client',
                'token': self.access_token,
                'dev_pid': 1537,  # 1537表示识别普通话，使用输入法模型
                'speech': audio_base64,
                'len': len(audio_data)
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            print("🔄 百度API识别中...")
            start_time = time.time()
            
            # 发送请求
            response = requests.post(
                config.BAIDU_ASR_URL,
                headers=headers,
                json=data,
                timeout=config.ASR_TIMEOUT
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 百度API响应: {result}")  # 调试信息

                if result.get('err_no') == 0:
                    # 识别成功
                    if 'result' in result and len(result['result']) > 0:
                        recognized_text = result['result'][0].strip()
                        if recognized_text:  # 检查是否为空字符串
                            print(f"✅ 百度API识别成功 (耗时: {elapsed_time:.1f}秒)")
                            print(f"📝 识别结果: {recognized_text}")
                            return recognized_text
                        else:
                            print(f"⚠️ 百度API识别成功但内容为空（可能是静音或音质问题）")
                            return None
                    else:
                        print(f"⚠️ 百度API返回成功但结果为空: {result}")
                        return None
                else:
                    # 识别失败
                    err_msg = result.get('err_msg', '未知错误')
                    err_no = result.get('err_no', '未知错误码')
                    print(f"❌ 百度API识别失败: 错误码{err_no}, {err_msg}")
                    return None
            else:
                print(f"❌ 请求失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 语音识别异常: {e}")
            return None
    
    def get_audio_info(self, audio_file_path: str) -> dict:
        """获取音频文件信息"""
        try:
            import wave
            with wave.open(audio_file_path, 'rb') as wf:
                return {
                    'frames': wf.getnframes(),
                    'sample_rate': wf.getframerate(),
                    'channels': wf.getnchannels(),
                    'sample_width': wf.getsampwidth(),
                    'duration': wf.getnframes() / wf.getframerate()
                }
        except Exception as e:
            print(f"❌ 获取音频信息失败: {e}")
            return {}


def create_baidu_asr() -> Optional[BaiduASR]:
    """创建百度语音识别实例"""
    if not config.BAIDU_API_KEY or not config.BAIDU_SECRET_KEY:
        print("❌ 百度API密钥未配置")
        return None
    
    return BaiduASR(config.BAIDU_API_KEY, config.BAIDU_SECRET_KEY)
