#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的自适应语音活动检测系统
专门解决噪音干扰和敏感度平衡问题
"""

import numpy as np
import time
from typing import Dict
from enum import Enum
import warnings

warnings.filterwarnings("ignore")

try:
    from ..config import config
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from voice_assistant.config import config

# 尝试导入WebRTC VAD
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


class VADState(Enum):
    """简化的VAD状态"""
    IDLE = "idle"           # 空闲状态
    DETECTING = "detecting" # 检测到可能的语音
    SPEAKING = "speaking"   # 确认语音状态


# 删除复杂的环境监控，直接使用简单阈值


class AdaptiveVAD:
    """自适应语音活动检测器"""
    
    def __init__(self,
                 sample_rate: int = 16000,
                 chunk_size: int = 1024,
                 base_volume_threshold: float = 10.0,  # 极低阈值，超敏感
                 webrtc_aggressiveness: int = 0):      # 最敏感的WebRTC设置
        """
        初始化自适应VAD
        
        Args:
            sample_rate: 采样率
            chunk_size: 音频块大小
            base_volume_threshold: 基础音量阈值
            webrtc_aggressiveness: WebRTC激进程度(0-3)
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.base_volume_threshold = base_volume_threshold
        
        # 动态音量阈值
        self.volume_threshold = base_volume_threshold
        self.base_volume_threshold = base_volume_threshold

        # 环境噪音自适应（从配置文件读取）
        self.noise_samples = []
        self.noise_baseline = 0.0
        self.noise_adaptation_frames = getattr(config, 'VAD_NOISE_ADAPTATION_FRAMES', 50)
        self.noise_multiplier = getattr(config, 'VAD_NOISE_MULTIPLIER', 3.0)
        self.enable_noise_adaptation = getattr(config, 'VAD_ENABLE_NOISE_ADAPTATION', True)
        
        # WebRTC VAD（如果可用）
        self.webrtc_vad = None
        self.webrtc_frame_size = int(sample_rate * 0.03)  # 30ms帧
        if WEBRTC_AVAILABLE:
            try:
                self.webrtc_vad = webrtcvad.Vad(webrtc_aggressiveness)
                print("✅ WebRTC VAD已启用")
            except Exception as e:
                print(f"⚠️ WebRTC VAD初始化失败: {e}")
        
        # 状态管理
        self.state = VADState.IDLE
        self.speech_start_time = None
        self.last_speech_time = None

        # 音量变化检测（新增）
        self.volume_history = []
        self.volume_history_size = 30  # 保留最近30帧的音量（约1.9秒）
        self.volume_drop_threshold = 0.65  # 音量下降65%认为是静音，平衡重读保护和响应速度

        # 智能语音连续性检测（简化版）
        self.pause_detection_enabled = True  # 启用停顿检测
        self.pause_tolerance_frames = 8      # 允许8帧（约0.5秒）的停顿
        self.pause_start_time = None         # 停顿开始时间
        self.in_pause_state = False          # 是否在停顿状态
        self.pause_recovery_frames = 2       # 恢复语音需要连续2帧
        
        # 检测参数（从配置文件读取）
        self.detection_frames = getattr(config, 'VAD_DETECTION_FRAMES', 1)
        self.confirmation_frames = getattr(config, 'VAD_CONFIRMATION_FRAMES', 2)
        self.silence_frames_limit = getattr(config, 'VAD_SILENCE_FRAMES_LIMIT', 5)
        
        # 帧计数器
        self.speech_frame_count = 0
        self.silence_frame_count = 0
        
        # 删除复杂的置信度平滑
        
        # 时序参数（从配置文件读取）
        self.min_speech_duration = getattr(config, 'VAD_MIN_SPEECH_DURATION', 0.3)
        self.max_silence_duration = getattr(config, 'VAD_MAX_SILENCE_DURATION', 0.8)
        self.max_speech_duration = getattr(config, 'VAD_MAX_SPEECH_DURATION', 8.0)
        
        print("🎤 自适应VAD系统初始化完成")
        print(f"   基础阈值: {self.base_volume_threshold}")
        print(f"   WebRTC可用: {'是' if self.webrtc_vad else '否'}")
    
    def _calculate_volume(self, audio_data: np.ndarray) -> float:
        """计算音频音量(RMS)"""
        if len(audio_data) == 0:
            return 0.0
        volume = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))

        # 更新音量历史（新增）
        self.volume_history.append(volume)
        if len(self.volume_history) > self.volume_history_size:
            self.volume_history.pop(0)

        # 更新噪音基线（仅在空闲状态时且启用自适应）
        if (self.enable_noise_adaptation and
            self.state == VADState.IDLE and
            len(self.noise_samples) < self.noise_adaptation_frames):
            self.noise_samples.append(volume)
            if len(self.noise_samples) == self.noise_adaptation_frames:
                self.noise_baseline = np.mean(self.noise_samples)
                # 动态调整阈值：噪音基线 * 倍数
                self.volume_threshold = max(self.base_volume_threshold, self.noise_baseline * self.noise_multiplier)
                print(f"🔧 噪音基线: {self.noise_baseline:.1f}, 调整阈值: {self.volume_threshold:.1f}")

        return volume

    def _detect_volume_drop(self) -> bool:
        """检测音量是否显著下降（优化版智能检测，避免重读误判）"""
        if len(self.volume_history) < 15:  # 需要更多历史数据避免误判
            return False

        # 使用更长的时间窗口来避免重读导致的误判
        recent_avg = np.mean(self.volume_history[-8:])
        previous_avg = np.mean(self.volume_history[-16:-8]) if len(self.volume_history) >= 16 else np.mean(self.volume_history[:-8])

        # 额外检查：如果最近有音量峰值，说明可能是重读，不应该结束
        recent_max = np.max(self.volume_history[-8:])
        overall_avg = np.mean(self.volume_history[-20:]) if len(self.volume_history) >= 20 else np.mean(self.volume_history)

        # 如果最近有明显的音量峰值（重读），则不认为是静音
        if recent_max > overall_avg * 1.5:  # 最近有超过平均音量1.5倍的峰值
            return False

        # 如果最近音量比之前音量下降超过阈值，认为是静音
        if previous_avg > 0:
            drop_ratio = (previous_avg - recent_avg) / previous_avg
            # 可选调试信息（仅在配置启用时显示）
            if getattr(config, 'VAD_ENABLE_DEBUG', False) and self.state == VADState.SPEAKING and drop_ratio > 0.1:
                if hasattr(self, '_volume_debug_count'):
                    self._volume_debug_count += 1
                else:
                    self._volume_debug_count = 1
                if self._volume_debug_count % 20 == 0:  # 每20帧打印一次
                    print(f"🔍 音量: 之前={previous_avg:.3f}, 最近={recent_avg:.3f}, 下降={drop_ratio:.2f}, 峰值={recent_max:.3f}")

            return drop_ratio > self.volume_drop_threshold

        return False

    def _detect_speech_pause(self, is_speech_frame: bool) -> bool:
        """
        简化的智能语音停顿检测
        只在连续静音时间过长时才结束语音

        Returns:
            bool: 是否应该结束语音（True=结束，False=继续等待）
        """
        if not self.pause_detection_enabled:
            return False

        current_time = time.time()

        if is_speech_frame:
            # 检测到语音，重置停顿状态
            if self.in_pause_state:
                self.in_pause_state = False
                self.pause_start_time = None
                print(f"🔄 语音恢复，继续录音")

        else:
            # 检测到静音
            if not self.in_pause_state:
                # 开始停顿
                self.in_pause_state = True
                self.pause_start_time = current_time

            elif self.pause_start_time:
                # 检查停顿时长
                pause_duration = current_time - self.pause_start_time

                if pause_duration >= 1.5:  # 停顿超过1.5秒结束，平衡长句支持和响应速度
                    print(f"⏹️ 停顿时间过长({pause_duration:.1f}s)，确认语音结束")
                    return True

        return False

    def _webrtc_detect(self, audio_data: np.ndarray) -> float:
        """使用WebRTC VAD检测"""
        if not self.webrtc_vad:
            return 0.0
        
        try:
            # 确保数据长度正确
            if len(audio_data) < self.webrtc_frame_size:
                padded = np.zeros(self.webrtc_frame_size, dtype=audio_data.dtype)
                padded[:len(audio_data)] = audio_data
                audio_data = padded
            elif len(audio_data) > self.webrtc_frame_size:
                audio_data = audio_data[:self.webrtc_frame_size]
            
            # 转换为16位整数
            audio_int16 = (audio_data * 32767).astype(np.int16)
            frame_bytes = audio_int16.tobytes()
            
            # WebRTC检测
            is_speech = self.webrtc_vad.is_speech(frame_bytes, self.sample_rate)
            return 0.8 if is_speech else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_confidence(self, volume: float, webrtc_confidence: float) -> float:
        """智能置信度计算 - 彻底修复WebRTC权重导致的延迟问题"""
        # 音量置信度（使用更严格的阈值）
        if volume < self.volume_threshold:
            volume_confidence = 0.0
        else:
            # 超过阈值后，需要显著超过才认为是语音
            volume_confidence = min((volume - self.volume_threshold) / (self.volume_threshold * 2), 1.0)

        # 综合置信度 - 从配置文件读取权重
        webrtc_weight = getattr(config, 'VAD_WEBRTC_WEIGHT', 0.4)
        volume_weight = getattr(config, 'VAD_VOLUME_WEIGHT', 0.6)

        if self.webrtc_vad and webrtc_weight > 0:
            # 彻底修复：在SPEAKING状态下，如果音量置信度为0，直接忽略WebRTC
            # 这样可以确保静音时能够快速结束语音检测
            if self.state == VADState.SPEAKING and volume_confidence == 0.0:
                # 在语音状态下遇到静音，完全忽略WebRTC，只看音量
                confidence = volume_confidence
            elif volume_confidence == 0.0:
                # 非语音状态下的静音，WebRTC权重降低到5%
                effective_webrtc_weight = webrtc_weight * 0.05
                effective_volume_weight = 1.0 - effective_webrtc_weight
                confidence = effective_webrtc_weight * webrtc_confidence + effective_volume_weight * volume_confidence
            else:
                # 有音量时，使用正常权重
                confidence = webrtc_weight * webrtc_confidence + volume_weight * volume_confidence
        else:
            # 没有WebRTC时，仅使用音量
            confidence = volume_confidence

        return confidence

    def _update_state_machine(self, confidence: float) -> bool:
        """更新状态机，返回是否发生状态变化"""
        current_time = time.time()
        state_changed = False
        # 从配置文件读取置信度阈值
        confidence_threshold = getattr(config, 'VAD_CONFIDENCE_THRESHOLD', 0.2)
        is_speech_frame = confidence > confidence_threshold

        # 可选调试信息（仅在配置启用时显示）
        if getattr(config, 'VAD_ENABLE_DEBUG', False):
            if hasattr(self, '_debug_frame_count'):
                self._debug_frame_count += 1
            else:
                self._debug_frame_count = 1

            if self._debug_frame_count % 50 == 0 and self.state == VADState.SPEAKING:
                print(f"🔍 调试: 置信度={confidence:.3f}, 阈值={confidence_threshold}, 静音帧={self.silence_frame_count}")

        if is_speech_frame:
            self.speech_frame_count += 1
            self.silence_frame_count = 0
            self.last_speech_time = current_time
        else:
            self.speech_frame_count = 0
            self.silence_frame_count += 1



        # 状态转换逻辑（更敏感的判断）
        if self.state == VADState.IDLE:
            if self.speech_frame_count >= self.detection_frames:
                self.state = VADState.DETECTING

        elif self.state == VADState.DETECTING:
            if self.speech_frame_count >= self.confirmation_frames:
                self.state = VADState.SPEAKING
                self.speech_start_time = current_time
                state_changed = True
                print(f"🔴 语音开始 (置信度: {confidence:.2f})")
            elif self.silence_frame_count > 5:  # 降低静音容忍度
                self.state = VADState.IDLE

        elif self.state == VADState.SPEAKING:
            speech_duration = current_time - self.speech_start_time

            # 强制超时检查
            if speech_duration >= self.max_speech_duration:
                self.state = VADState.IDLE
                state_changed = True
                print(f"⏰ 语音强制结束 (超时: {speech_duration:.1f}秒)")
            else:
                # 智能停顿检测（优先级最高）
                should_end_by_pause = self._detect_speech_pause(is_speech_frame)

                # 传统检测方法（作为备选）
                should_end_by_silence = self.silence_frame_count >= self.silence_frames_limit
                should_end_by_volume = self._detect_volume_drop()

                # 简化判断逻辑：任何一种检测方法触发都可以结束
                if should_end_by_pause or should_end_by_silence or should_end_by_volume:
                    # 检查最小语音时长
                    if speech_duration >= self.min_speech_duration:
                        self.state = VADState.IDLE
                        state_changed = True

                        # 根据结束原因显示不同信息
                        if should_end_by_pause:
                            print(f"⏹️ 语音结束 (智能停顿检测, 时长: {speech_duration:.1f}秒)")
                        elif should_end_by_volume:
                            print(f"⏹️ 语音结束 (音量下降检测, 时长: {speech_duration:.1f}秒)")
                        else:
                            print(f"⏹️ 语音结束 (静音检测, 时长: {speech_duration:.1f}秒)")
                    else:
                        # 语音太短，继续等待
                        self.silence_frame_count = max(0, self.silence_frame_count - 3)

        return state_changed

    def detect(self, audio_data: np.ndarray) -> Dict:
        """
        检测语音活动

        Returns:
            dict: {
                'is_speech': bool,
                'confidence': float,
                'state': str,
                'state_changed': bool,
                'debug_info': dict
            }
        """
        # 计算音频特征
        volume = self._calculate_volume(audio_data)
        webrtc_confidence = self._webrtc_detect(audio_data)

        # 简单检测，不需要环境监控

        # 计算综合置信度
        confidence = self._calculate_confidence(volume, webrtc_confidence)

        # 更新状态机
        state_changed = self._update_state_machine(confidence)

        # 计算语音持续时间
        speech_duration = 0.0
        if self.speech_start_time:
            speech_duration = time.time() - self.speech_start_time

        return {
            'is_speech': self.state == VADState.SPEAKING,
            'confidence': confidence,
            'state': self.state.value,
            'state_changed': state_changed,
            'speech_duration': speech_duration,
            'debug_info': {
                'volume': volume,
                'webrtc_confidence': webrtc_confidence,
                'threshold': self.volume_threshold,
                'speech_frames': self.speech_frame_count,
                'silence_frames': self.silence_frame_count
            }
        }

    def reset(self):
        """重置VAD状态"""
        self.state = VADState.IDLE
        self.speech_frame_count = 0
        self.silence_frame_count = 0
        self.speech_start_time = None
        self.last_speech_time = None

        # 重置智能停顿检测状态
        self.pause_start_time = None
        self.in_pause_state = False
        if hasattr(self, '_recovery_frame_count'):
            self._recovery_frame_count = 0
        if hasattr(self, '_volume_debug_count'):
            self._volume_debug_count = 0

        print("🔄 VAD状态已重置")

    def get_status(self) -> Dict:
        """获取VAD状态信息"""
        return {
            'state': self.state.value,
            'webrtc_available': self.webrtc_vad is not None,
            'volume_threshold': self.volume_threshold,
            'speech_duration': (
                time.time() - self.speech_start_time
                if self.speech_start_time else 0.0
            )
        }

    def adjust_sensitivity(self, factor: float):
        """调整VAD敏感度"""
        self.volume_threshold *= factor
        print(f"🎛️ VAD敏感度已调整，新阈值: {self.volume_threshold:.1f}")


def create_optimized_vad(**kwargs) -> AdaptiveVAD:
    """创建优化的自适应VAD实例"""
    return AdaptiveVAD(**kwargs)
