#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舞蹈动作库管理器
负责加载、管理和分析舞蹈动作
"""

import csv
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class DanceAction:
    """舞蹈动作数据类"""
    seq: str
    title: str
    label: str
    time: int  # 毫秒
    
    # 自动分析的特征
    energy_level: str = "medium"    # low/medium/high
    tempo_match: str = "any"        # slow/medium/fast/any
    mood_match: str = "any"         # calm/neutral/energetic/any
    movement_type: str = "general"  # forward/turn/side/stand/gesture/combo/general
    segment_preference: str = "any" # intro/verse/chorus/bridge/outro/any


class ActionLibrary:
    """舞蹈动作库管理器"""
    
    def __init__(self, csv_file: str = "动作库.csv"):
        """
        初始化动作库
        
        Args:
            csv_file: CSV动作映射文件路径
        """
        self.csv_file = csv_file
        self.actions: List[DanceAction] = []
        self.mapping: Dict[str, Dict] = {}
        
        self._load_actions()
        self._analyze_actions()
        
        print(f"📁 舞蹈动作库加载完成: {len(self.actions)}个动作")
    
    def _load_actions(self):
        """从CSV文件加载动作"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 清理数据
                    seq = row['Seq'].strip()
                    title = row['title'].strip()
                    label = row['label'].strip()
                    time = int(row['time'].strip())
                    
                    # 创建动作对象
                    action = DanceAction(
                        seq=seq,
                        title=title,
                        label=label,
                        time=time
                    )
                    
                    self.actions.append(action)
                    
                    # 创建映射（保持向后兼容）
                    self.mapping[label] = {
                        'seq': seq,
                        'title': title,
                        'time': time
                    }
                    
                    print(f"  ✅ {label} -> Seq {seq} ({title}, {time/1000:.1f}s)")
                    
        except FileNotFoundError:
            print(f"❌ 动作库文件未找到: {self.csv_file}")
            raise
        except Exception as e:
            print(f"❌ 动作库加载失败: {e}")
            raise
    
    def _analyze_actions(self):
        """自动分析动作特征"""
        for action in self.actions:
            # 分析能量级别
            action.energy_level = self._analyze_energy_level(action)
            
            # 分析节奏匹配
            action.tempo_match = self._analyze_tempo_match(action)
            
            # 分析情绪匹配
            action.mood_match = self._analyze_mood_match(action)
            
            # 分析动作类型
            action.movement_type = self._analyze_movement_type(action)
            
            # 分析段落偏好
            action.segment_preference = self._analyze_segment_preference(action)
    
    def _analyze_energy_level(self, action: DanceAction) -> str:
        """分析动作能量级别"""
        title_lower = action.title.lower()
        label_lower = action.label.lower()
        
        # 高能量关键词
        high_energy_keywords = ['前进', '跳', '快', '激烈', '动感', '冲刺', '汇总']
        if any(keyword in title_lower or keyword in label_lower for keyword in high_energy_keywords):
            return "high"
        
        # 低能量关键词
        low_energy_keywords = ['立正', '站立', '静止', '缓慢', '优雅', '初始化']
        if any(keyword in title_lower or keyword in label_lower for keyword in low_energy_keywords):
            return "low"
        
        # 时长判断
        if action.time > 10000:  # 超过10秒的动作通常是高能量
            return "high"
        elif action.time < 3000:  # 少于3秒的动作通常是低能量
            return "low"
        
        return "medium"
    
    def _analyze_tempo_match(self, action: DanceAction) -> str:
        """分析节奏匹配"""
        title_lower = action.title.lower()
        label_lower = action.label.lower()
        
        # 快节奏关键词
        fast_keywords = ['前进', '快', '冲', '跑', '急']
        if any(keyword in title_lower or keyword in label_lower for keyword in fast_keywords):
            return "fast"
        
        # 慢节奏关键词
        slow_keywords = ['立正', '站立', '缓', '慢', '优雅']
        if any(keyword in title_lower or keyword in label_lower for keyword in slow_keywords):
            return "slow"
        
        return "medium"
    
    def _analyze_mood_match(self, action: DanceAction) -> str:
        """分析情绪匹配"""
        title_lower = action.title.lower()
        label_lower = action.label.lower()
        
        # 动感情绪
        energetic_keywords = ['前进', '大创', '跳', '激烈', '动感']
        if any(keyword in title_lower or keyword in label_lower for keyword in energetic_keywords):
            return "energetic"
        
        # 平静情绪
        calm_keywords = ['立正', '站立', '优雅', '初始化']
        if any(keyword in title_lower or keyword in label_lower for keyword in calm_keywords):
            return "calm"
        
        return "neutral"
    
    def _analyze_movement_type(self, action: DanceAction) -> str:
        """分析动作类型"""
        title_lower = action.title.lower()
        label_lower = action.label.lower()
        
        # 前进类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['前进', '后退']):
            return "forward"
        
        # 转向类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['转', '旋转']):
            return "turn"
        
        # 侧移类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['侧', '左', '右']):
            return "side"
        
        # 站立类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['立正', '站立', '大字']):
            return "stand"
        
        # 手势类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['招手', '挥手']):
            return "gesture"
        
        # 组合类
        if any(keyword in title_lower or keyword in label_lower for keyword in ['汇总', '组合']):
            return "combo"
        
        return "general"
    
    def _analyze_segment_preference(self, action: DanceAction) -> str:
        """分析音乐段落偏好"""
        title_lower = action.title.lower()
        label_lower = action.label.lower()
        
        # 前奏偏好
        if any(keyword in title_lower or keyword in label_lower for keyword in ['初始化', '立正', '准备', '开始']):
            return "intro"
        
        # 高潮偏好
        if any(keyword in title_lower or keyword in label_lower for keyword in ['前进', '大创', '跳', '激烈', '高潮', '汇总']):
            return "chorus"
        
        # 过渡偏好
        if any(keyword in title_lower or keyword in label_lower for keyword in ['转', '侧移', '过渡']):
            return "bridge"
        
        return "any"
    
    def get_actions(self) -> List[DanceAction]:
        """获取所有动作"""
        return self.actions
    
    def get_mapping(self) -> Dict[str, Dict]:
        """获取映射表（向后兼容）"""
        return self.mapping
    
    def get_action_by_label(self, label: str) -> DanceAction:
        """根据标签获取动作"""
        for action in self.actions:
            if action.label == label:
                return action
        raise ValueError(f"动作未找到: {label}")
    
    def print_action_analysis(self):
        """打印动作分析结果"""
        print(f"\n🎭 动作特征分析:")
        for action in self.actions:
            print(f"   {action.label}:")
            print(f"     能量: {action.energy_level}, 节奏: {action.tempo_match}")
            print(f"     情绪: {action.mood_match}, 类型: {action.movement_type}")
            print(f"     段落偏好: {action.segment_preference}")
