#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS管理器 - 只使用百度TTS
"""

import os
import time
import subprocess
import threading
from typing import Optional

from ..config import config
from ..speech.baidu_tts import create_baidu_tts


class TTSManager:
    """TTS管理器 - 只使用百度TTS"""
    
    def __init__(self, use_baidu: bool = True, voice_person: int = None, initial_volume: int = None):
        self.use_baidu = use_baidu
        self.enabled = True
        self.volume_level = initial_volume or config.TTS_DEFAULT_VOLUME
        self.muted = False
        self.is_speaking = False
        
        # 初始化百度TTS
        self.baidu_tts = None
        if use_baidu:
            self.baidu_tts = create_baidu_tts(voice_person)
            if self.baidu_tts:
                print("✅ 百度TTS初始化成功")
            else:
                print("❌ 百度TTS初始化失败")
                raise RuntimeError("百度TTS初始化失败")
        else:
            raise RuntimeError("必须使用百度TTS")
    
    def speak(self, text: str):
        """语音播放 - 只使用百度TTS"""
        if not self.enabled or self.muted:
            return
        
        if not text or not text.strip():
            return
        
        self.is_speaking = True
        
        # 使用百度TTS
        if self.baidu_tts:
            self.baidu_tts.speak(text, volume_level=self.volume_level, tts_manager=self)
        else:
            print("❌ 百度TTS不可用")
            self.is_speaking = False
    
    def _check_audio_device(self) -> bool:
        """检查音频设备是否可用"""
        try:
            # 检查是否有音频输出设备
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
            if result.returncode == 0 and 'card' in result.stdout:
                print("✅ 检测到音频播放设备")
                return True
            else:
                print("⚠️ 未检测到音频播放设备")
                return False
        except FileNotFoundError:
            print("⚠️ aplay命令不可用")
            return False
        except Exception as e:
            print(f"⚠️ 音频设备检测失败: {e}")
            return False
    
    def set_volume(self, volume: int):
        """设置音量 (1-10)"""
        if 1 <= volume <= 10:
            self.volume_level = volume
            print(f"🔊 音量设置为: {volume}/10")
        else:
            print(f"⚠️ 音量必须在1-10之间，当前: {volume}")
    
    def volume_up(self):
        """音量增加"""
        if self.volume_level < 10:
            self.volume_level += 1
            print(f"🔊 音量增加到: {self.volume_level}/10")
        else:
            print("🔊 音量已达最大值")
    
    def volume_down(self):
        """音量减少"""
        if self.volume_level > 1:
            self.volume_level -= 1
            print(f"🔊 音量减少到: {self.volume_level}/10")
        else:
            print("🔊 音量已达最小值")
    
    def mute(self):
        """静音"""
        self.muted = True
        print("🔇 AI语音已静音")
    
    def unmute(self):
        """取消静音"""
        self.muted = False
        print("🔊 AI语音已开启")
    
    def toggle_mute(self):
        """切换静音状态"""
        if self.muted:
            self.unmute()
        else:
            self.mute()
    
    def stop_current_speech(self):
        """停止当前语音播放"""
        if self.is_speaking:
            # 停止百度TTS播放
            if self.baidu_tts:
                try:
                    self.baidu_tts.stop_playback()
                except:
                    pass
            print("⏭️ 已停止当前语音播放")

    def wait_for_speech_complete(self, timeout: float = 60.0):
        """等待语音播放完成"""
        import time
        start_time = time.time()

        print("⏳ 等待语音播放完成...")
        print("🔍 开始等待播放完成...")

        while self.is_speaking and (time.time() - start_time) < timeout:
            elapsed = time.time() - start_time
            print(f"⏳ 等待播放中... ({elapsed:.1f}s)")
            time.sleep(3.0)  # 每3秒检查一次

        if self.is_speaking:
            print(f"⚠️ 播放超时 ({timeout}秒)，强制结束")
            self.stop_current_speech()
        else:
            elapsed = time.time() - start_time
            print(f"✅ 播放完成，等待了 {elapsed:.1f}秒")


def create_tts_manager(use_baidu: bool = True, voice_person: int = None, initial_volume: int = None) -> TTSManager:
    """创建TTS管理器 - 强制使用百度TTS"""
    return TTSManager(use_baidu=True, voice_person=voice_person, initial_volume=initial_volume)
