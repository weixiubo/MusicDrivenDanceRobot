#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时音乐分析模块
使用librosa进行音乐特征提取和节拍检测
"""

import numpy as np
import time
import threading
import queue
from typing import Dict, Optional, Callable
from dataclasses import dataclass

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("⚠️ librosa未安装，音乐分析功能将被禁用")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

from ..config import config

try:
    from .music_structure_analyzer import create_structure_analyzer, MusicStructureAnalyzer
    STRUCTURE_ANALYSIS_AVAILABLE = True
except ImportError:
    STRUCTURE_ANALYSIS_AVAILABLE = False
    MusicStructureAnalyzer = None


@dataclass
class MusicFeatures:
    """音乐特征数据类"""
    tempo: float = 0.0              # 节拍速度 (BPM)
    beat_strength: float = 0.0      # 节拍强度
    energy: float = 0.0             # 音频能量
    spectral_centroid: float = 0.0  # 频谱重心
    zero_crossing_rate: float = 0.0 # 过零率
    mfcc_mean: np.ndarray = None    # MFCC特征均值
    onset_strength: float = 0.0     # 起始强度
    rhythm_pattern: str = "steady"  # 节奏模式
    mood: str = "neutral"           # 音乐情绪
    timestamp: float = 0.0          # 时间戳

    # 新增：音乐结构信息
    segment_type: str = "unknown"   # 音乐段落类型
    segment_intensity: float = 0.5  # 段落强度
    energy_trend: str = "stable"    # 能量趋势
    structure_confidence: float = 0.5  # 结构识别置信度


class MusicAnalyzer:
    """实时音乐分析器"""
    
    def __init__(self, 
                 sample_rate: int = 22050,
                 chunk_size: int = 1024,
                 analysis_window: float = 2.0,
                 enable_analysis: bool = True):
        """
        初始化音乐分析器
        
        Args:
            sample_rate: 音频采样率
            chunk_size: 音频块大小
            analysis_window: 分析窗口时长（秒）
            enable_analysis: 是否启用分析功能
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.analysis_window = analysis_window
        self.enable_analysis = enable_analysis and LIBROSA_AVAILABLE
        
        # 音频缓冲区
        self.audio_buffer = queue.Queue(maxsize=100)
        self.analysis_buffer = []
        self.buffer_duration = 0.0
        
        # 分析结果
        self.current_features = MusicFeatures()
        self.features_history = []
        self.max_history = 10
        
        # 线程控制
        self.is_analyzing = False
        self.analysis_thread = None
        self.stop_event = threading.Event()
        
        # 回调函数
        self.feature_callback: Optional[Callable] = None

        # 音乐结构分析器
        self.structure_analyzer = None
        if STRUCTURE_ANALYSIS_AVAILABLE and enable_analysis:
            try:
                self.structure_analyzer = create_structure_analyzer(enable_analysis)
                print("✅ 音乐结构分析器已集成")
            except Exception as e:
                print(f"⚠️ 音乐结构分析器初始化失败: {e}")

        # 音频设备
        self.audio = None
        self.stream = None
        
        if not self.enable_analysis:
            print("⚠️ 音乐分析功能已禁用（librosa不可用）")
        else:
            print("✅ 音乐分析器初始化完成")
    
    def set_feature_callback(self, callback: Callable[[MusicFeatures], None]):
        """设置特征更新回调函数"""
        self.feature_callback = callback
    
    def start_analysis(self) -> bool:
        """开始音乐分析"""
        if not self.enable_analysis:
            print("⚠️ 音乐分析功能未启用")
            return False
            
        if self.is_analyzing:
            print("⚠️ 音乐分析已在运行")
            return False
        
        if not PYAUDIO_AVAILABLE:
            print("❌ pyaudio不可用，无法进行音乐分析")
            return False
        
        try:
            # 初始化音频设备
            self.audio = pyaudio.PyAudio()
            
            # 创建音频流（使用较低的采样率以减少计算负担）
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            # 启动分析线程
            self.is_analyzing = True
            self.stop_event.clear()
            self.analysis_thread = threading.Thread(
                target=self._analysis_loop,
                daemon=True
            )
            self.analysis_thread.start()
            
            # 开始音频流
            self.stream.start_stream()
            
            print("🎵 音乐分析已启动")
            return True
            
        except Exception as e:
            print(f"❌ 启动音乐分析失败: {e}")
            self.stop_analysis()
            return False
    
    def stop_analysis(self):
        """停止音乐分析"""
        if not self.is_analyzing:
            return
        
        print("⏹️ 停止音乐分析")
        
        # 停止线程
        self.is_analyzing = False
        self.stop_event.set()
        
        # 停止音频流
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None
        
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
            self.audio = None
        
        # 等待线程结束
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=2)
        
        # 清理缓冲区
        while not self.audio_buffer.empty():
            try:
                self.audio_buffer.get_nowait()
            except:
                break

        self.analysis_buffer.clear()

        # 重置结构分析器
        if self.structure_analyzer:
            self.structure_analyzer.reset_analysis()

        print("✅ 音乐分析已停止")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数"""
        if self.is_analyzing:
            try:
                # 将音频数据放入缓冲区
                audio_data = np.frombuffer(in_data, dtype=np.float32)
                if not self.audio_buffer.full():
                    self.audio_buffer.put(audio_data)
            except:
                pass
        
        return (None, pyaudio.paContinue)
    
    def _analysis_loop(self):
        """音乐分析主循环"""
        print("🔄 音乐分析循环启动")
        
        while self.is_analyzing and not self.stop_event.is_set():
            try:
                # 从缓冲区获取音频数据
                if not self.audio_buffer.empty():
                    audio_chunk = self.audio_buffer.get(timeout=0.1)
                    self._process_audio_chunk(audio_chunk)
                else:
                    time.sleep(0.05)  # 短暂休眠
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ 音乐分析错误: {e}")
                time.sleep(0.1)
        
        print("🔄 音乐分析循环结束")
    
    def _process_audio_chunk(self, audio_chunk: np.ndarray):
        """处理音频块"""
        # 添加到分析缓冲区
        self.analysis_buffer.extend(audio_chunk)
        self.buffer_duration += len(audio_chunk) / self.sample_rate
        
        # 当缓冲区达到分析窗口大小时进行分析
        if self.buffer_duration >= self.analysis_window:
            self._analyze_buffer()
            
            # 保留一半数据作为重叠窗口
            overlap_samples = len(self.analysis_buffer) // 2
            self.analysis_buffer = self.analysis_buffer[-overlap_samples:]
            self.buffer_duration = len(self.analysis_buffer) / self.sample_rate
    
    def _analyze_buffer(self):
        """分析音频缓冲区"""
        if len(self.analysis_buffer) < self.sample_rate * 0.5:  # 至少0.5秒数据
            return
        
        try:
            # 转换为numpy数组
            audio_data = np.array(self.analysis_buffer, dtype=np.float32)
            
            # 提取音乐特征
            features = self._extract_features(audio_data)
            
            # 更新当前特征
            self.current_features = features
            
            # 添加到历史记录
            self.features_history.append(features)
            if len(self.features_history) > self.max_history:
                self.features_history.pop(0)
            
            # 调用回调函数
            if self.feature_callback:
                try:
                    self.feature_callback(features)
                except Exception as e:
                    print(f"⚠️ 特征回调函数错误: {e}")
                    
        except Exception as e:
            print(f"⚠️ 音频分析错误: {e}")
    
    def _extract_features(self, audio_data: np.ndarray) -> MusicFeatures:
        """提取音乐特征"""
        features = MusicFeatures()
        features.timestamp = time.time()
        
        try:
            # 基础特征
            features.energy = float(np.mean(audio_data ** 2))
            features.zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(audio_data)[0]))
            
            # 频谱特征
            if len(audio_data) > 512:  # 确保有足够的数据
                spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)[0]
                features.spectral_centroid = float(np.mean(spectral_centroids))
                
                # MFCC特征
                mfcc = librosa.feature.mfcc(y=audio_data, sr=self.sample_rate, n_mfcc=13)
                features.mfcc_mean = np.mean(mfcc, axis=1)
                
                # 节拍和节奏分析
                try:
                    tempo, beats = librosa.beat.beat_track(y=audio_data, sr=self.sample_rate)
                    features.tempo = float(tempo)
                    
                    # 计算节拍强度
                    onset_envelope = librosa.onset.onset_strength(y=audio_data, sr=self.sample_rate)
                    features.onset_strength = float(np.mean(onset_envelope))
                    features.beat_strength = float(np.std(onset_envelope))
                    
                except:
                    # 如果节拍检测失败，使用默认值
                    features.tempo = 120.0
                    features.beat_strength = 0.5
                    features.onset_strength = 0.5
            
            # 分析节奏模式和情绪
            features.rhythm_pattern = self._analyze_rhythm_pattern(features)
            features.mood = self._analyze_mood(features)

            # 集成音乐结构分析
            if self.structure_analyzer:
                try:
                    # 为结构分析器准备特征数据
                    structure_features = {
                        'rms_energy': features.energy,
                        'tempo': features.tempo,
                        'onset_strength': features.onset_strength,
                        'spectral_centroid': features.spectral_centroid,
                        'timestamp': features.timestamp
                    }

                    # 更新结构分析
                    structure_state = self.structure_analyzer.update_structure_analysis(structure_features)
                    structure_info = self.structure_analyzer.get_current_structure_info()

                    # 将结构信息添加到特征中
                    features.segment_type = structure_info.get('segment_type', 'unknown')
                    features.segment_intensity = structure_info.get('intensity', 0.5)
                    features.energy_trend = structure_info.get('energy_trend', 'stable')
                    features.structure_confidence = structure_info.get('confidence', 0.5)

                except Exception as e:
                    print(f"⚠️ 结构分析更新失败: {e}")
                    # 使用默认值
                    features.segment_type = "unknown"
                    features.segment_intensity = 0.5
                    features.energy_trend = "stable"
                    features.structure_confidence = 0.3
            
        except Exception as e:
            print(f"⚠️ 特征提取错误: {e}")
            # 返回默认特征
            features.tempo = 120.0
            features.energy = 0.1
            features.rhythm_pattern = "steady"
            features.mood = "neutral"
        
        return features
    
    def _analyze_rhythm_pattern(self, features: MusicFeatures) -> str:
        """分析节奏模式"""
        if features.tempo > 140:
            return "fast"
        elif features.tempo < 80:
            return "slow"
        elif features.beat_strength > 0.7:
            return "strong"
        elif features.beat_strength < 0.3:
            return "gentle"
        else:
            return "steady"
    
    def _analyze_mood(self, features: MusicFeatures) -> str:
        """分析音乐情绪"""
        if features.energy > 0.5 and features.tempo > 120:
            return "energetic"
        elif features.energy < 0.2 and features.tempo < 90:
            return "calm"
        elif features.spectral_centroid > 2000:
            return "bright"
        elif features.spectral_centroid < 1000:
            return "dark"
        else:
            return "neutral"
    
    def get_current_features(self) -> MusicFeatures:
        """获取当前音乐特征"""
        return self.current_features
    
    def get_average_features(self, window: int = 5) -> MusicFeatures:
        """获取平均音乐特征"""
        if not self.features_history:
            return self.current_features
        
        recent_features = self.features_history[-window:]
        if not recent_features:
            return self.current_features
        
        # 计算平均值
        avg_features = MusicFeatures()
        avg_features.tempo = np.mean([f.tempo for f in recent_features])
        avg_features.energy = np.mean([f.energy for f in recent_features])
        avg_features.beat_strength = np.mean([f.beat_strength for f in recent_features])
        avg_features.spectral_centroid = np.mean([f.spectral_centroid for f in recent_features])
        avg_features.zero_crossing_rate = np.mean([f.zero_crossing_rate for f in recent_features])
        avg_features.onset_strength = np.mean([f.onset_strength for f in recent_features])
        
        # 使用最新的分类特征
        avg_features.rhythm_pattern = recent_features[-1].rhythm_pattern
        avg_features.mood = recent_features[-1].mood
        avg_features.timestamp = time.time()
        
        return avg_features


def create_music_analyzer(enable_analysis: bool = True) -> MusicAnalyzer:
    """创建音乐分析器实例"""
    return MusicAnalyzer(
        sample_rate=22050,  # 使用较低采样率减少计算负担
        chunk_size=1024,
        analysis_window=2.0,
        enable_analysis=enable_analysis
    )
