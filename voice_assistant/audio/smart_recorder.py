#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能录音管理器
基于VAD的自动语音检测录音，无需按键操作
"""

import os
import sys
import time
import wave
import threading
import tempfile
import numpy as np
from typing import Optional, Callable
from enum import Enum
import warnings

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
    from .optimized_vad import create_optimized_vad
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from voice_assistant.config import config
    from voice_assistant.audio.optimized_vad import create_optimized_vad


class RecordingState(Enum):
    """录音状态枚举"""
    IDLE = "idle"                    # 空闲状态
    LISTENING = "listening"          # 监听状态（等待语音）
    RECORDING = "recording"          # 录音状态
    PROCESSING = "processing"        # 处理状态
    COMPLETED = "completed"          # 完成状态
    ERROR = "error"                  # 错误状态


class SmartRecorder:
    """智能录音器 - 基于VAD的自动语音检测"""
    
    def __init__(self,
                 sample_rate: int = None,
                 chunk_size: int = None,
                 max_recording_duration: float = None,
                 enable_webrtc: bool = True):
        """
        初始化智能录音器

        Args:
            sample_rate: 采样率
            chunk_size: 音频块大小
            max_recording_duration: 最大单次录音时长
            enable_webrtc: 是否启用WebRTC VAD
        """
        if not AUDIO_AVAILABLE:
            raise ImportError("pyaudio不可用，无法进行录音")
        
        # 自动检测采样率
        if config.AUDIO_SAMPLE_RATE is None:
            self.sample_rate = sample_rate or config.get_best_sample_rate()
        else:
            self.sample_rate = sample_rate or config.AUDIO_SAMPLE_RATE

        self.chunk_size = chunk_size or config.AUDIO_CHUNK_SIZE
        self.max_recording_duration = max_recording_duration or config.AUDIO_MAX_RECORDING_DURATION

        # 音频设备配置 - 支持拓展坞设备
        self.input_device_index = getattr(config, 'AUDIO_INPUT_DEVICE_INDEX', None)
        self.alsa_device = getattr(config, 'AUDIO_ALSA_DEVICE', None)
        
        # 音频设置
        try:
            self.audio = pyaudio.PyAudio()
            print(f"✅ PyAudio初始化成功")

            # 检查默认设备
            try:
                default_input = self.audio.get_default_input_device_info()
                print(f"🎤 默认输入设备: {default_input['name']} (索引: {default_input['index']})")
            except Exception as e:
                print(f"⚠️ 获取默认输入设备失败: {e}")

            try:
                default_output = self.audio.get_default_output_device_info()
                print(f"🔊 默认输出设备: {default_output['name']} (索引: {default_output['index']})")
            except Exception as e:
                print(f"⚠️ 获取默认输出设备失败: {e}")

        except Exception as e:
            print(f"❌ PyAudio初始化失败: {e}")
            raise

        self.audio_format = pyaudio.paInt16
        self.channels = config.AUDIO_CHANNELS
        
        # VAD系统 - 使用优化的自适应VAD系统（所有参数从配置文件读取）
        self.vad = create_optimized_vad(
            sample_rate=self.sample_rate,
            chunk_size=self.chunk_size,
            base_volume_threshold=getattr(config, 'VAD_BASE_VOLUME_THRESHOLD', 10.0),
            webrtc_aggressiveness=getattr(config, 'VAD_WEBRTC_AGGRESSIVENESS', 0)
        )

        # 音频质量检查（简化版）
        self.enable_quality_check = getattr(config, 'VAD_ENABLE_QUALITY_CHECK', False)

        # 录音状态
        self.state = RecordingState.IDLE
        self.stream = None
        self.frames = []
        self.recording_start_time = None
        self.listening_start_time = None

        # 暂停控制（用于跳舞时暂停录音）
        self.is_paused = False
        
        # 回调函数
        self.on_listening_start: Optional[Callable] = None
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_stop: Optional[Callable] = None
        self.on_recording_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        print("🎤 智能录音器初始化完成")
        print(f"   采样率: {self.sample_rate}Hz")
        print(f"   最大单次录音时长: {self.max_recording_duration}秒")
        print(f"   模式: 持续待机监听")
    
    def set_callbacks(self, **callbacks):
        """设置回调函数"""
        for name, callback in callbacks.items():
            if hasattr(self, f"on_{name}"):
                setattr(self, f"on_{name}", callback)
    
    def _change_state(self, new_state: RecordingState):
        """改变录音状态"""
        old_state = self.state
        self.state = new_state
        print(f"🔄 录音状态: {old_state.value} → {new_state.value}")
    
    def _call_callback(self, callback_name: str, *args, **kwargs):
        """安全调用回调函数"""
        callback = getattr(self, f"on_{callback_name}", None)
        if callback and callable(callback):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"⚠️ 回调函数 {callback_name} 执行失败: {e}")
    
    def start_smart_recording(self, filename: str) -> bool:
        """
        开始智能录音
        
        Args:
            filename: 录音文件路径
            
        Returns:
            bool: 是否成功开始录音
        """
        if self.state != RecordingState.IDLE:
            print(f"⚠️ 录音器忙碌中，当前状态: {self.state.value}")
            return False
        
        try:
            # 初始化音频流
            print(f"🔧 尝试创建音频流: {self.sample_rate}Hz, {self.channels}声道")

            # 构建音频流参数
            stream_params = {
                'format': self.audio_format,
                'channels': self.channels,
                'rate': self.sample_rate,
                'input': True,
                'frames_per_buffer': self.chunk_size
            }

            # 注释：移除有问题的alsaaudio逻辑，统一使用PyAudio

            # 如果指定了输入设备索引，则添加该参数
            if self.input_device_index is not None:
                stream_params['input_device_index'] = self.input_device_index
                print(f"🎤 使用指定音频设备: 索引 {self.input_device_index}")
            else:
                print(f"🎤 使用默认音频设备")

            print(f"📋 音频流参数: {stream_params}")

            silence_stderr()
            self.stream = self.audio.open(**stream_params)
            restore_stderr()

            print(f"✅ 音频流创建成功")
            
            self.frames = []
            self.listening_start_time = time.time()
            self._change_state(RecordingState.LISTENING)
            
            print("👂 开始持续监听，随时可以说话...")
            print("💡 智能待机模式：说话即可开始录音")
            self._call_callback('listening_start')
            
            # 启动录音线程
            recording_thread = threading.Thread(
                target=self._recording_loop,
                args=(filename,),
                daemon=True
            )
            recording_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ 启动智能录音失败: {e}")
            self._change_state(RecordingState.ERROR)
            self._call_callback('error', e)
            return False
    
    def _recording_loop(self, filename: str):
        """录音主循环 - 持续监听模式"""
        try:
            while self.state in [RecordingState.LISTENING, RecordingState.RECORDING]:
                current_time = time.time()

                # 检查是否暂停（跳舞时暂停录音）
                if self.is_paused:
                    time.sleep(0.1)  # 暂停期间短暂休眠
                    continue

                # 只检查录音时长限制（防止单次录音过长）
                if (self.state == RecordingState.RECORDING and
                    self.recording_start_time and
                    current_time - self.recording_start_time > self.max_recording_duration):
                    print(f"⏰ 单次录音达到上限 {self.max_recording_duration}秒，自动停止")
                    break
                
                # 读取音频数据
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    
                    # VAD检测
                    vad_result = self.vad.detect(audio_array)
                    
                    # 状态转换逻辑
                    if self.state == RecordingState.LISTENING:
                        if vad_result['is_speech'] and vad_result['state_changed']:
                            # 开始录音
                            self._change_state(RecordingState.RECORDING)
                            self.recording_start_time = current_time
                            print("🔴 检测到语音，开始录音...")
                            print("🔴 智能录音已开始")
                            self._call_callback('recording_start')

                            # 将当前帧加入录音
                            self.frames.append(data)
                    
                    elif self.state == RecordingState.RECORDING:
                        # 录音中，保存音频数据
                        self.frames.append(data)
                        
                        # 显示录音状态
                        if len(self.frames) % (self.sample_rate // self.chunk_size // 2) == 0:
                            duration = len(self.frames) * self.chunk_size / self.sample_rate
                            print(f"🔊 录音中... {duration:.1f}s", end="\r")
                        
                        # 检查是否停止说话
                        if not vad_result['is_speech'] and vad_result['state_changed']:
                            print("\n⏹️ 检测到语音结束，停止录音")
                            self._call_callback('recording_stop')
                            break
                
                except Exception as e:
                    print(f"⚠️ 音频读取错误: {e}")
                    continue
            
            # 保存录音文件
            if self.frames and len(self.frames) > 0:
                self._save_recording(filename)
                self._change_state(RecordingState.COMPLETED)
                self._call_callback('recording_complete', filename)
                # 录音完成后重置为IDLE状态，准备下次录音
                time.sleep(0.1)  # 短暂延迟确保回调完成
                self._change_state(RecordingState.IDLE)
            else:
                self._change_state(RecordingState.IDLE)
                
        except Exception as e:
            print(f"❌ 录音循环错误: {e}")
            self._change_state(RecordingState.ERROR)
            self._call_callback('error', e)
        finally:
            self._cleanup_stream()
    
    def _save_recording(self, filename: str):
        """保存录音文件并进行质量检查"""
        try:
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(self.frames))

            duration = len(self.frames) * self.chunk_size / self.sample_rate
            file_size = os.path.getsize(filename)

            # 简化的录音信息显示
            print(f"\n✅ 录音保存成功: {filename}")
            print(f"   时长: {duration:.1f}秒")
            print(f"   大小: {file_size/1024:.1f}KB")

            # 简单的质量检查
            if self.enable_quality_check:
                if file_size > 1000 and duration > 0.5:
                    print("🔍 音频质量: 正常")
                else:
                    print("⚠️ 音频质量: 可能过短或过小")
                    print("💡 建议: 请在安静环境中录音，确保麦克风距离适中")

            # 自动清理旧录音文件
            self._auto_cleanup_audio_files()

        except Exception as e:
            print(f"❌ 保存录音失败: {e}")
            raise

    def _auto_cleanup_audio_files(self):
        """自动清理录音文件 - 简化版，删除所有旧录音"""
        try:
            if not getattr(config, 'AUDIO_AUTO_DELETE', True):
                return

            from pathlib import Path

            # 查找并删除所有录音文件（除了当前正在使用的）
            audio_patterns = ["*.wav", "temp_*.wav", "recording_*.wav", "user_audio_*.wav"]

            for pattern in audio_patterns:
                files = list(Path(".").glob(pattern))
                for file_path in files:
                    try:
                        # 简单检查：如果文件不是刚创建的，就删除
                        import time
                        if time.time() - file_path.stat().st_mtime > 60:  # 超过1分钟的文件
                            file_path.unlink()
                    except:
                        pass

        except Exception:
            # 清理失败不影响主流程
            pass
    
    def stop_recording(self):
        """手动停止录音"""
        if self.state in [RecordingState.LISTENING, RecordingState.RECORDING]:
            print("🛑 手动停止录音")
            self._change_state(RecordingState.IDLE)

    def pause_recording(self):
        """暂停录音（用于跳舞时）"""
        if not self.is_paused:
            self.is_paused = True
            print("⏸️ 录音已暂停（跳舞模式）")

    def resume_recording(self):
        """恢复录音"""
        if self.is_paused:
            self.is_paused = False
            print("▶️ 录音已恢复")
    
    def _cleanup_stream(self):
        """清理音频流"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None
    
    def cleanup(self):
        """清理资源"""
        self.stop_recording()
        self._cleanup_stream()
        if self.audio:
            self.audio.terminate()
    
    def get_status(self) -> dict:
        """获取录音器状态"""
        return {
            'state': self.state.value,
            'vad_status': self.vad.get_status() if self.vad else None,
            'recording_duration': (
                time.time() - self.recording_start_time
                if self.recording_start_time else 0
            ),
            'continuous_listening': True  # 标识为持续监听模式
        }


def create_smart_recorder(**kwargs) -> SmartRecorder:
    """创建智能录音器实例"""
    return SmartRecorder(**kwargs)
