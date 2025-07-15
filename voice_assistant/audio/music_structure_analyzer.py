#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音乐结构分析模块
分析音乐的段落结构、情感强度变化和节奏模式
"""

import numpy as np
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False


@dataclass
class MusicSegment:
    """音乐段落数据类"""
    segment_type: str = "unknown"       # intro, verse, chorus, bridge, outro, transition
    intensity: float = 0.5              # 强度 0-1
    energy_trend: str = "stable"        # rising, falling, stable, fluctuating
    duration: float = 0.0               # 段落持续时间
    confidence: float = 0.5             # 识别置信度
    start_time: float = 0.0             # 开始时间
    characteristics: Dict = None        # 其他特征


@dataclass
class MusicStructureState:
    """音乐结构状态"""
    current_segment: MusicSegment = None
    previous_segments: List[MusicSegment] = None
    intensity_history: List[float] = None
    energy_trend: str = "stable"
    structure_confidence: float = 0.5
    predicted_next_segment: str = "unknown"
    
    def __post_init__(self):
        if self.previous_segments is None:
            self.previous_segments = []
        if self.intensity_history is None:
            self.intensity_history = []


class MusicStructureAnalyzer:
    """音乐结构分析器"""
    
    def __init__(self, 
                 analysis_window: float = 4.0,
                 history_length: int = 20,
                 enable_analysis: bool = True):
        """
        初始化音乐结构分析器
        
        Args:
            analysis_window: 分析窗口时长（秒）
            history_length: 保持的历史记录长度
            enable_analysis: 是否启用分析
        """
        self.analysis_window = analysis_window
        self.history_length = history_length
        self.enable_analysis = enable_analysis and LIBROSA_AVAILABLE
        
        # 分析状态
        self.current_state = MusicStructureState()
        self.feature_history = deque(maxlen=history_length)
        self.segment_history = deque(maxlen=10)
        
        # 分析参数
        self.intensity_threshold_high = 0.7
        self.intensity_threshold_low = 0.3
        self.energy_change_threshold = 0.2
        self.segment_min_duration = 8.0  # 最小段落时长
        
        # 状态跟踪
        self.current_segment_start = time.time()
        self.last_analysis_time = 0
        
        if not self.enable_analysis:
            print("⚠️ 音乐结构分析功能已禁用（librosa不可用）")
        else:
            print("✅ 音乐结构分析器初始化完成")
    
    def analyze_music_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict:
        """
        分析音频特征用于结构识别
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            
        Returns:
            Dict: 音乐特征字典
        """
        if not self.enable_analysis or len(audio_data) < sample_rate * 0.5:
            return {}
        
        try:
            features = {}
            
            # 基础能量特征
            features['rms_energy'] = float(np.sqrt(np.mean(audio_data ** 2)))
            features['zero_crossing_rate'] = float(np.mean(librosa.feature.zero_crossing_rate(audio_data)[0]))
            
            # 频谱特征
            if len(audio_data) > 1024:
                # 频谱重心
                spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
                features['spectral_centroid'] = float(np.mean(spectral_centroids))
                features['spectral_centroid_var'] = float(np.var(spectral_centroids))
                
                # 频谱带宽
                spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_data, sr=sample_rate)[0]
                features['spectral_bandwidth'] = float(np.mean(spectral_bandwidth))
                
                # 频谱对比度
                spectral_contrast = librosa.feature.spectral_contrast(y=audio_data, sr=sample_rate)
                features['spectral_contrast'] = float(np.mean(spectral_contrast))
                
                # MFCC特征
                mfcc = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
                features['mfcc_mean'] = np.mean(mfcc, axis=1)
                features['mfcc_var'] = np.var(mfcc, axis=1)
                
                # 节拍相关
                try:
                    tempo, beats = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
                    features['tempo'] = float(tempo)
                    
                    # 节拍强度
                    onset_envelope = librosa.onset.onset_strength(y=audio_data, sr=sample_rate)
                    features['onset_strength'] = float(np.mean(onset_envelope))
                    features['onset_strength_var'] = float(np.var(onset_envelope))
                    
                    # 节拍规律性
                    if len(beats) > 1:
                        beat_intervals = np.diff(beats)
                        features['beat_regularity'] = float(1.0 / (1.0 + np.var(beat_intervals)))
                    else:
                        features['beat_regularity'] = 0.5
                        
                except:
                    features['tempo'] = 120.0
                    features['onset_strength'] = 0.5
                    features['onset_strength_var'] = 0.1
                    features['beat_regularity'] = 0.5
            
            features['timestamp'] = time.time()
            return features
            
        except Exception as e:
            print(f"⚠️ 音乐特征分析错误: {e}")
            return {}
    
    def update_structure_analysis(self, features: Dict) -> MusicStructureState:
        """
        更新音乐结构分析
        
        Args:
            features: 音乐特征字典
            
        Returns:
            MusicStructureState: 更新后的结构状态
        """
        if not features or not self.enable_analysis:
            return self.current_state
        
        # 添加到历史记录
        self.feature_history.append(features)
        
        # 计算当前强度
        current_intensity = self._calculate_intensity(features)
        self.current_state.intensity_history.append(current_intensity)
        
        # 保持历史记录长度
        if len(self.current_state.intensity_history) > self.history_length:
            self.current_state.intensity_history.pop(0)
        
        # 分析能量趋势
        self.current_state.energy_trend = self._analyze_energy_trend()
        
        # 检测段落变化
        segment_changed = self._detect_segment_change(features, current_intensity)
        
        if segment_changed:
            # 结束当前段落
            if self.current_state.current_segment:
                self.current_state.current_segment.duration = time.time() - self.current_segment_start
                self.segment_history.append(self.current_state.current_segment)
            
            # 开始新段落
            new_segment = self._classify_new_segment(features, current_intensity)
            self.current_state.current_segment = new_segment
            self.current_segment_start = time.time()
            
            # 预测下一个段落
            self.current_state.predicted_next_segment = self._predict_next_segment()
        
        # 更新当前段落信息
        if self.current_state.current_segment:
            self.current_state.current_segment.intensity = current_intensity
            self.current_state.current_segment.energy_trend = self.current_state.energy_trend
            self.current_state.current_segment.duration = time.time() - self.current_segment_start
        
        # 更新结构置信度
        self.current_state.structure_confidence = self._calculate_structure_confidence()
        
        self.last_analysis_time = time.time()
        return self.current_state
    
    def _calculate_intensity(self, features: Dict) -> float:
        """计算音乐强度"""
        intensity = 0.0
        
        # RMS能量贡献 (40%)
        rms = features.get('rms_energy', 0.1)
        intensity += min(1.0, rms * 2.0) * 0.4
        
        # 起始强度贡献 (30%)
        onset = features.get('onset_strength', 0.5)
        intensity += min(1.0, onset) * 0.3
        
        # 频谱对比度贡献 (20%)
        contrast = features.get('spectral_contrast', 0.5)
        intensity += min(1.0, contrast / 10.0) * 0.2
        
        # 节拍规律性贡献 (10%)
        regularity = features.get('beat_regularity', 0.5)
        intensity += regularity * 0.1
        
        return min(1.0, intensity)
    
    def _analyze_energy_trend(self) -> str:
        """分析能量趋势"""
        if len(self.current_state.intensity_history) < 5:
            return "stable"
        
        recent_intensities = self.current_state.intensity_history[-5:]
        
        # 计算趋势
        x = np.arange(len(recent_intensities))
        slope = np.polyfit(x, recent_intensities, 1)[0]
        
        # 计算变化幅度
        intensity_range = max(recent_intensities) - min(recent_intensities)
        
        if abs(slope) < 0.02 and intensity_range < 0.1:
            return "stable"
        elif slope > 0.05:
            return "rising"
        elif slope < -0.05:
            return "falling"
        elif intensity_range > 0.2:
            return "fluctuating"
        else:
            return "stable"
    
    def _detect_segment_change(self, features: Dict, current_intensity: float) -> bool:
        """检测段落变化"""
        if len(self.feature_history) < 3:
            return False
        
        # 检查是否达到最小段落时长
        current_segment_duration = time.time() - self.current_segment_start
        if current_segment_duration < self.segment_min_duration:
            return False
        
        # 检查强度变化
        if len(self.current_state.intensity_history) >= 3:
            recent_avg = np.mean(self.current_state.intensity_history[-3:])
            previous_avg = np.mean(self.current_state.intensity_history[-6:-3]) if len(self.current_state.intensity_history) >= 6 else recent_avg
            
            intensity_change = abs(recent_avg - previous_avg)
            if intensity_change > self.energy_change_threshold:
                return True
        
        # 检查频谱特征变化
        if len(self.feature_history) >= 2:
            current_features = self.feature_history[-1]
            previous_features = self.feature_history[-2]
            
            # 频谱重心变化
            centroid_change = abs(current_features.get('spectral_centroid', 1000) - 
                                previous_features.get('spectral_centroid', 1000))
            if centroid_change > 500:  # 频谱重心变化超过500Hz
                return True
            
            # 节拍变化
            tempo_change = abs(current_features.get('tempo', 120) - 
                             previous_features.get('tempo', 120))
            if tempo_change > 20:  # BPM变化超过20
                return True
        
        return False
    
    def _classify_new_segment(self, features: Dict, intensity: float) -> MusicSegment:
        """分类新段落"""
        segment = MusicSegment()
        segment.start_time = time.time()
        segment.intensity = intensity
        
        # 基于强度和历史分类段落类型
        if intensity > self.intensity_threshold_high:
            if len(self.segment_history) == 0:
                segment.segment_type = "intro"
                segment.confidence = 0.7
            else:
                segment.segment_type = "chorus"
                segment.confidence = 0.8
        elif intensity < self.intensity_threshold_low:
            if len(self.segment_history) > 0 and self.segment_history[-1].segment_type == "chorus":
                segment.segment_type = "bridge"
                segment.confidence = 0.7
            else:
                segment.segment_type = "verse"
                segment.confidence = 0.8
        else:
            # 中等强度
            if len(self.segment_history) == 0:
                segment.segment_type = "intro"
                segment.confidence = 0.6
            elif len(self.segment_history) > 3:
                segment.segment_type = "outro"
                segment.confidence = 0.6
            else:
                segment.segment_type = "transition"
                segment.confidence = 0.5
        
        # 添加特征信息
        segment.characteristics = {
            'tempo': features.get('tempo', 120),
            'spectral_centroid': features.get('spectral_centroid', 1000),
            'onset_strength': features.get('onset_strength', 0.5)
        }
        
        return segment
    
    def _predict_next_segment(self) -> str:
        """预测下一个段落类型"""
        if not self.segment_history:
            return "verse"
        
        current_type = self.current_state.current_segment.segment_type if self.current_state.current_segment else "unknown"
        
        # 简单的状态转移预测
        transitions = {
            "intro": "verse",
            "verse": "chorus",
            "chorus": "verse",
            "bridge": "chorus",
            "transition": "verse",
            "outro": "end"
        }
        
        return transitions.get(current_type, "verse")
    
    def _calculate_structure_confidence(self) -> float:
        """计算结构识别置信度"""
        if not self.current_state.current_segment:
            return 0.3
        
        base_confidence = self.current_state.current_segment.confidence
        
        # 基于历史一致性调整置信度
        if len(self.segment_history) > 1:
            # 检查段落时长的合理性
            durations = [seg.duration for seg in self.segment_history if seg.duration > 0]
            if durations:
                avg_duration = np.mean(durations)
                if 5 < avg_duration < 30:  # 合理的段落时长
                    base_confidence += 0.1
        
        # 基于特征稳定性调整
        if len(self.current_state.intensity_history) > 5:
            intensity_stability = 1.0 - np.var(self.current_state.intensity_history[-5:])
            base_confidence += intensity_stability * 0.1
        
        return min(1.0, base_confidence)
    
    def get_current_structure_info(self) -> Dict:
        """获取当前结构信息"""
        if not self.current_state.current_segment:
            return {
                'segment_type': 'unknown',
                'intensity': 0.5,
                'energy_trend': 'stable',
                'confidence': 0.3,
                'duration': 0.0,
                'predicted_next': 'unknown'
            }
        
        return {
            'segment_type': self.current_state.current_segment.segment_type,
            'intensity': self.current_state.current_segment.intensity,
            'energy_trend': self.current_state.energy_trend,
            'confidence': self.current_state.structure_confidence,
            'duration': self.current_state.current_segment.duration,
            'predicted_next': self.current_state.predicted_next_segment,
            'characteristics': self.current_state.current_segment.characteristics or {}
        }
    
    def reset_analysis(self):
        """重置分析状态"""
        self.current_state = MusicStructureState()
        self.feature_history.clear()
        self.segment_history.clear()
        self.current_segment_start = time.time()
        print("🔄 音乐结构分析状态已重置")


def create_structure_analyzer(enable_analysis: bool = True) -> MusicStructureAnalyzer:
    """创建音乐结构分析器实例"""
    return MusicStructureAnalyzer(
        analysis_window=4.0,
        history_length=20,
        enable_analysis=enable_analysis
    )
