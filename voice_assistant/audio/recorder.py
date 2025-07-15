#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频录音模块
处理音频录音功能，支持按键控制和智能VAD自动检测
"""

import os
import sys
import time
import wave
import threading
import warnings
from typing import Optional, Callable, Dict, Any, Union
from enum import Enum

# 抑制警告
warnings.filterwarnings("ignore")

# 重定向stderr工具
class NullWriter:
    def write(self, _): pass
    def flush(self): pass

original_stderr = sys.stderr

def silence_stderr():
    sys.stderr = NullWriter()

def restore_stderr():
    sys.stderr = original_stderr

# 导入pyaudio
try:
    silence_stderr()
    import pyaudio
    restore_stderr()
    AUDIO_AVAILABLE = True
except ImportError:
    restore_stderr()
    AUDIO_AVAILABLE = False
    print("警告: pyaudio未安装")

try:
    from ..config import config
    from .smart_recorder import SmartRecorder, create_smart_recorder
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from voice_assistant.config import config
    from voice_assistant.audio.smart_recorder import SmartRecorder, create_smart_recorder


class RecordingMode(Enum):
    """录音模式枚举"""
    ENTER_KEY = "enter_key"          # 按回车键控制
    FIXED_DURATION = "fixed_duration"  # 固定时长
    SMART_VAD = "smart_vad"          # 智能VAD检测


class AudioRecorder:
    """音频录音器 - 支持多种录音模式"""

    def __init__(self):
        if not AUDIO_AVAILABLE:
            raise ImportError("pyaudio不可用，无法进行录音")

        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = config.AUDIO_CHANNELS
        self.sample_rate = config.AUDIO_SAMPLE_RATE
        self.chunk_size = config.AUDIO_CHUNK_SIZE
        self.stream = None
        self.frames = []

        # 智能录音器
        self._smart_recorder = None

        # 回调函数
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_complete: Optional[Callable] = None
    
    def record_with_enter_control(self, filename: str, max_duration: float = None) -> bool:
        """按回车开始/停止录音"""
        if max_duration is None:
            max_duration = config.AUDIO_RECORD_TIMEOUT
        
        try:
            print("🎤 按回车键开始录音...")
            input()  # 等待用户按回车开始录音
            
            print("🔴 录音中... 再按回车键停止录音")
            
            silence_stderr()
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            restore_stderr()
            
            self.frames = []
            recording = True
            
            def wait_for_stop():
                nonlocal recording
                input()  # 等待用户再次按回车停止录音
                recording = False
                print("\n⏹️ 停止录音")
            
            # 启动等待停止的线程
            stop_thread = threading.Thread(target=wait_for_stop)
            stop_thread.daemon = True
            stop_thread.start()
            
            start_time = time.time()
            frames_recorded = 0
            
            while recording and (time.time() - start_time) < max_duration:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                    frames_recorded += 1
                    
                    # 每0.5秒显示一次录音状态
                    if frames_recorded % (self.sample_rate // self.chunk_size // 2) == 0:
                        print("🔊", end="", flush=True)
                        
                except:
                    continue
            
            if time.time() - start_time >= max_duration:
                print(f"\n⏰ 达到最大录音时长 {max_duration}秒")
            
            self.stream.stop_stream()
            self.stream.close()
            
            # 保存文件
            self._save_audio_file(filename)
            
            duration = time.time() - start_time
            print(f"\n✅ 录音完成，时长: {duration:.1f}秒")
            return True
            
        except Exception as e:
            print(f"❌ 录音失败: {e}")
            return False
        finally:
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
    
    def record_for_duration(self, duration: float, filename: str) -> bool:
        """录音指定时长"""
        try:
            silence_stderr()
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            restore_stderr()
            
            self.frames = []
            
            print(f"🎤 录音中 ({duration}秒)...")
            
            # 录音
            frames_to_record = int(self.sample_rate / self.chunk_size * duration)
            for i in range(frames_to_record):
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                    
                    # 简单的进度指示
                    if i % (frames_to_record // 4) == 0:
                        print("🔊", end="", flush=True)
                        
                except:
                    continue
            
            print()  # 换行
            
            self.stream.stop_stream()
            self.stream.close()
            
            # 保存文件
            self._save_audio_file(filename)
            
            return True
            
        except Exception as e:
            print(f"❌ 录音失败: {e}")
            return False

    def record_with_smart_vad(self, filename: str,
                             max_duration: float = None,
                             enable_webrtc: bool = True) -> bool:
        """
        智能VAD录音 - 持续监听模式

        Args:
            filename: 录音文件路径
            max_duration: 最大单次录音时长
            enable_webrtc: 是否启用WebRTC VAD

        Returns:
            bool: 录音是否成功
        """
        try:
            # 每次都创建新的智能录音器，避免状态问题
            if self._smart_recorder:
                self._smart_recorder.cleanup()

            self._smart_recorder = create_smart_recorder(
                sample_rate=self.sample_rate,
                chunk_size=self.chunk_size,
                max_recording_duration=max_duration or config.AUDIO_MAX_RECORDING_DURATION,
                enable_webrtc=enable_webrtc
            )

            # 设置回调函数
            self._smart_recorder.set_callbacks(
                listening_start=self._on_listening_start,
                recording_start=self._on_recording_start,
                recording_stop=self._on_recording_stop,
                recording_complete=self._on_recording_complete,
                timeout=self._on_timeout,
                error=self._on_error
            )

            # 开始智能录音
            success = self._smart_recorder.start_smart_recording(filename)

            if success:
                # 等待录音完成
                while self._smart_recorder.state.value in ['listening', 'recording']:
                    time.sleep(0.1)

                return self._smart_recorder.state.value == 'completed'

            return False

        except Exception as e:
            print(f"❌ 智能VAD录音失败: {e}")
            return False

    def _on_listening_start(self):
        """监听开始回调"""
        print("👂 智能监听已启动")
        if self.on_recording_start:
            self.on_recording_start()

    def _on_recording_start(self):
        """录音开始回调"""
        print("🔴 智能录音已开始")

    def _on_recording_stop(self):
        """录音停止回调"""
        print("⏹️ 智能录音已停止")

    def _on_recording_complete(self, filename: str):
        """录音完成回调"""
        print(f"✅ 智能录音完成: {filename}")
        if self.on_recording_complete:
            self.on_recording_complete(filename)

    def _on_timeout(self):
        """超时回调"""
        print("⏰ 智能录音超时")

    def _on_error(self, error):
        """错误回调"""
        print(f"❌ 智能录音错误: {error}")

    def get_smart_recorder_status(self) -> Optional[Dict[str, Any]]:
        """获取智能录音器状态"""
        if self._smart_recorder:
            return self._smart_recorder.get_status()
        return None

    def stop_smart_recording(self):
        """停止智能录音"""
        if self._smart_recorder:
            self._smart_recorder.stop_recording()

    def _save_audio_file(self, filename: str):
        """保存音频文件"""
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.frames))

    def cleanup(self):
        """清理资源"""
        if self._smart_recorder:
            self._smart_recorder.cleanup()
        if self.audio:
            self.audio.terminate()


def record_audio(filename: str,
              mode: Union[RecordingMode, str] = RecordingMode.SMART_VAD,
              **kwargs) -> bool:
    """
    便捷的录音函数，支持多种录音模式

    Args:
        filename: 录音文件路径
        mode: 录音模式 (smart_vad, enter_key, fixed_duration)
        **kwargs: 其他参数

    Returns:
        bool: 录音是否成功
    """
    try:
        recorder = AudioRecorder()

        # 转换字符串模式为枚举
        if isinstance(mode, str):
            try:
                mode = RecordingMode(mode)
            except ValueError:
                print(f"⚠️ 未知的录音模式: {mode}，使用智能VAD模式")
                mode = RecordingMode.SMART_VAD

        # 根据模式选择录音方法
        if mode == RecordingMode.SMART_VAD:
            print("🎤 使用智能VAD录音模式")
            success = recorder.record_with_smart_vad(filename, **kwargs)
        elif mode == RecordingMode.ENTER_KEY:
            print("🎤 使用按回车键录音模式")
            success = recorder.record_with_enter_control(filename, **kwargs)
        elif mode == RecordingMode.FIXED_DURATION:
            duration = kwargs.get('duration', 4.0)
            print(f"🎤 使用固定时长录音模式 ({duration}秒)")
            success = recorder.record_for_duration(duration, filename)
        else:
            print(f"⚠️ 不支持的录音模式: {mode}")
            success = False

        return success

    except Exception as e:
        print(f"❌ 录音失败: {e}")
        return False
    finally:
        if 'recorder' in locals():
            recorder.cleanup()


def is_audio_available() -> bool:
    """检查音频功能是否可用"""
    return AUDIO_AVAILABLE
