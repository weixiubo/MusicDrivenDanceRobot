#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音乐感知马尔可夫链舞蹈选择器
结合音乐特征匹配和动作连贯性的智能舞蹈选择系统
"""

import numpy as np
import random
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from voice_assistant.audio.music_analyzer import MusicFeatures
from voice_assistant.config import config
from .action_library import ActionLibrary, DanceAction


class ActionTransitionMatrix:
    """动作转移矩阵管理器"""
    
    def __init__(self, actions: List[DanceAction]):
        """初始化转移矩阵"""
        self.actions = actions
        self.action_types = {action.label: action.movement_type for action in actions}
        self.base_transitions = self._build_base_transition_matrix()
        
        print(f"🔗 马尔可夫转移矩阵初始化完成")
        print(f"   动作分类: {len(set(self.action_types.values()))}个类型")
        print(f"   转移规则: {len(self.base_transitions)}条")
    
    def _build_base_transition_matrix(self) -> Dict[str, Dict[str, float]]:
        """构建基础转移概率矩阵"""
        # 基于动作类型的转移规律
        type_transitions = {
            "stand": {"forward": 0.35, "gesture": 0.25, "turn": 0.20, "side": 0.15, "stand": 0.05},
            "forward": {"turn": 0.30, "side": 0.25, "stand": 0.20, "gesture": 0.15, "forward": 0.10},
            "turn": {"forward": 0.35, "side": 0.25, "stand": 0.20, "gesture": 0.15, "turn": 0.05},
            "side": {"forward": 0.30, "turn": 0.25, "stand": 0.20, "gesture": 0.15, "side": 0.10},
            "gesture": {"forward": 0.30, "stand": 0.25, "turn": 0.20, "side": 0.15, "gesture": 0.10},
            "combo": {"stand": 0.40, "gesture": 0.25, "forward": 0.20, "turn": 0.10, "side": 0.05},
            "general": {"forward": 0.25, "stand": 0.25, "turn": 0.20, "side": 0.15, "gesture": 0.15}
        }
        
        # 转换为具体动作的转移矩阵
        action_transitions = {}
        for from_action in self.actions:
            from_type = self.action_types[from_action.label]
            action_transitions[from_action.label] = {}
            
            type_probs = type_transitions.get(from_type, type_transitions["general"])
            
            for to_action in self.actions:
                to_type = self.action_types[to_action.label]
                base_prob = type_probs.get(to_type, 0.1)
                
                # 添加随机性
                noise = random.uniform(-0.05, 0.05)
                final_prob = max(0.01, base_prob + noise)
                action_transitions[from_action.label][to_action.label] = final_prob
            
            # 归一化概率
            total_prob = sum(action_transitions[from_action.label].values())
            for to_label in action_transitions[from_action.label]:
                action_transitions[from_action.label][to_label] /= total_prob
        
        return action_transitions
    
    def get_all_transitions_from(self, from_action: str) -> Dict[str, float]:
        """获取从指定动作出发的所有转移概率"""
        return self.base_transitions.get(from_action, {})


class MusicAwareMarkovSelector:
    """音乐感知马尔可夫链舞蹈选择器"""
    
    def __init__(self, dance_mapping: Dict = None, csv_file: str = "动作库.csv"):
        """初始化选择器"""
        # 加载动作库
        self.action_library = ActionLibrary(csv_file)
        self.dance_actions = self.action_library.get_actions()
        self.dance_mapping = dance_mapping or self.action_library.get_mapping()
        
        # 马尔可夫链
        self.transition_matrix = ActionTransitionMatrix(self.dance_actions)
        self.current_action = None
        self.action_history = []
        
        # 融合参数
        self.music_weight = 0.7
        self.markov_weight = 0.3
        self.temperature = 0.8
        self.max_history = 10
        
        # 选择历史（多样性控制）
        self.selection_history = []
        
        print(f"🎭 音乐感知马尔可夫链选择器初始化完成")
        print(f"   融合权重: 音乐{self.music_weight:.1f} + 连贯性{self.markov_weight:.1f}")
    
    def select_dance_by_music(self, music_features: MusicFeatures, remaining_time: float, mode: str = "real"):
        """基于音乐特征和马尔可夫链选择舞蹈动作"""
        if not config.MUSIC_DRIVEN_SELECTION:
            return self._select_by_time_only(remaining_time)
        
        # 筛选可用动作
        available_actions = [
            action for action in self.dance_actions 
            if action.time <= remaining_time * 1000
        ]
        
        if not available_actions:
            return None
        
        # 音乐特征评分
        music_scores = {}
        for action in available_actions:
            music_scores[action.label] = self._calculate_music_match_score(action, music_features)
        
        # 马尔可夫连贯性评分
        markov_scores = {}
        if self.current_action:
            transitions = self.transition_matrix.get_all_transitions_from(self.current_action)
            adjusted_transitions = self._adjust_transitions_by_music(transitions, music_features)
            
            for action in available_actions:
                markov_scores[action.label] = adjusted_transitions.get(action.label, 0.1)
        else:
            for action in available_actions:
                markov_scores[action.label] = 1.0 / len(available_actions)
        
        # 融合评分
        final_scores = []
        for action in available_actions:
            music_score = music_scores[action.label]
            markov_score = markov_scores[action.label]
            
            final_score = (
                music_score * self.music_weight +
                markov_score * self.markov_weight
            )
            
            final_scores.append((action, final_score))
        
        # 选择动作
        final_scores.sort(key=lambda x: x[1], reverse=True)
        selected_action = self._weighted_random_selection(final_scores)
        
        if selected_action:
            # 更新状态
            self.current_action = selected_action.label
            self.action_history.append(selected_action.label)
            if len(self.action_history) > self.max_history:
                self.action_history.pop(0)
            
            self.selection_history.append(selected_action.label)
            if len(self.selection_history) > self.max_history:
                self.selection_history.pop(0)
            
            # 生成选择理由
            reason = self._generate_markov_music_reason(
                selected_action, music_features, 
                music_scores[selected_action.label],
                markov_scores[selected_action.label]
            )
            
            # 返回结果
            dance_data = self.dance_mapping[selected_action.label]
            return selected_action.label, dance_data, reason
        
        return None
    
    def _calculate_music_match_score(self, action: DanceAction, music_features: MusicFeatures) -> float:
        """计算音乐匹配分数"""
        score = 0.0
        
        # 节奏匹配 (30%)
        tempo_score = self._score_tempo_match(action, music_features)
        score += tempo_score * 0.3
        
        # 能量匹配 (25%)
        energy_score = self._score_energy_match(action, music_features)
        score += energy_score * 0.25
        
        # 情绪匹配 (20%)
        mood_score = self._score_mood_match(action, music_features)
        score += mood_score * 0.2
        
        # 音乐结构匹配 (15%)
        structure_score = self._score_structure_match(action, music_features)
        score += structure_score * 0.15
        
        # 多样性奖励 (10%)
        diversity_score = self._score_diversity(action)
        score += diversity_score * 0.1
        
        return score

    def _score_tempo_match(self, action: DanceAction, music_features: MusicFeatures) -> float:
        """节奏匹配评分"""
        if action.tempo_match == "any":
            return 0.8

        if music_features.tempo > 140:  # 快节奏
            return 1.0 if action.tempo_match == "fast" else 0.3
        elif music_features.tempo < 80:  # 慢节奏
            return 1.0 if action.tempo_match == "slow" else 0.3
        else:  # 中等节奏
            return 1.0 if action.tempo_match == "medium" else 0.6

    def _score_energy_match(self, action: DanceAction, music_features: MusicFeatures) -> float:
        """能量匹配评分"""
        if music_features.energy > 0.5:  # 高能量
            return 1.0 if action.energy_level == "high" else 0.4
        elif music_features.energy < 0.2:  # 低能量
            return 1.0 if action.energy_level == "low" else 0.4
        else:  # 中等能量
            return 1.0 if action.energy_level == "medium" else 0.7

    def _score_mood_match(self, action: DanceAction, music_features: MusicFeatures) -> float:
        """情绪匹配评分"""
        if action.mood_match == "any":
            return 0.8

        if hasattr(music_features, 'mood'):
            if music_features.mood == action.mood_match:
                return 1.0
            elif action.mood_match == "neutral":
                return 0.8
            else:
                return 0.4
        return 0.8

    def _score_structure_match(self, action: DanceAction, music_features: MusicFeatures) -> float:
        """音乐结构匹配评分"""
        if action.segment_preference == "any":
            return 0.8

        if hasattr(music_features, 'segment_type'):
            if music_features.segment_type == action.segment_preference:
                return 1.0
            else:
                return 0.5
        return 0.8

    def _score_diversity(self, action: DanceAction) -> float:
        """多样性评分"""
        if not self.selection_history:
            return 1.0

        recent_count = self.selection_history[-5:].count(action.label)
        if recent_count == 0:
            return 1.0
        elif recent_count == 1:
            return 0.7
        else:
            return 0.3

    def _adjust_transitions_by_music(self, base_transitions: Dict[str, float], music_features: MusicFeatures) -> Dict[str, float]:
        """根据音乐特征调整转移概率"""
        adjusted = base_transitions.copy()

        # 快节奏音乐：增加动感动作
        if music_features.tempo > 140:
            for to_action in adjusted:
                action_type = self.transition_matrix.action_types.get(to_action, "general")
                if action_type in ["forward", "turn"]:
                    adjusted[to_action] *= 1.5
                elif action_type in ["stand"]:
                    adjusted[to_action] *= 0.7

        # 慢节奏音乐：增加优雅动作
        elif music_features.tempo < 80:
            for to_action in adjusted:
                action_type = self.transition_matrix.action_types.get(to_action, "general")
                if action_type in ["stand", "gesture"]:
                    adjusted[to_action] *= 1.4
                elif action_type in ["forward"]:
                    adjusted[to_action] *= 0.8

        # 归一化概率
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {action: prob / total for action, prob in adjusted.items()}

        return adjusted

    def _weighted_random_selection(self, scored_actions: List[Tuple[DanceAction, float]]) -> Optional[DanceAction]:
        """加权随机选择"""
        if not scored_actions:
            return None

        scores = [score for _, score in scored_actions]
        scaled_scores = [score / self.temperature for score in scores]
        max_score = max(scaled_scores)
        exp_scores = [np.exp(score - max_score) for score in scaled_scores]

        total_exp = sum(exp_scores)
        probabilities = [exp_score / total_exp for exp_score in exp_scores]

        rand_val = random.random()
        cumulative_prob = 0

        for i, prob in enumerate(probabilities):
            cumulative_prob += prob
            if rand_val <= cumulative_prob:
                return scored_actions[i][0]

        return scored_actions[0][0]

    def _generate_markov_music_reason(self, action: DanceAction, music_features: MusicFeatures, music_score: float, markov_score: float) -> str:
        """生成融合选择理由"""
        # 基础音乐理由
        music_reason = self._generate_music_match_reason(action.label, {
            'title': action.title,
            'time': action.time
        })

        # 连贯性理由
        markov_reason = ""
        if self.current_action:
            current_type = self.transition_matrix.action_types.get(self.current_action, "general")
            next_type = self.transition_matrix.action_types.get(action.label, "general")

            if markov_score > 0.3:
                markov_reason = f"从{current_type}到{next_type}的转换很自然"
            elif markov_score > 0.2:
                markov_reason = f"动作连接较为流畅"
            else:
                markov_reason = f"提供舞蹈变化"

        # 融合理由
        if music_score > 0.7 and markov_score > 0.3:
            return f"{music_reason}，且{markov_reason}（音乐+连贯性双优）"
        elif music_score > 0.7:
            return f"{music_reason}（音乐主导选择）"
        elif markov_score > 0.3:
            return f"{markov_reason}，{music_reason}（连贯性主导选择）"
        else:
            return f"{music_reason}，{markov_reason}"

    def _generate_music_match_reason(self, dance_label: str, dance_data: Dict) -> str:
        """生成音乐匹配理由"""
        if '前进' in dance_label:
            return "当前音乐节拍适合前进动作，展现向前的动感"
        elif '转' in dance_label:
            return "音乐旋律转折，转身动作呼应音乐变化"
        elif '大字站立' in dance_label:
            return "音乐高潮部分，大字站立展现气势"
        elif '立正' in dance_label:
            return "音乐节奏平稳，立正动作保持稳定"
        elif '侧移' in dance_label:
            return "音乐律动适合侧向移动，增加舞蹈层次"
        elif '招手' in dance_label:
            return "音乐温和，招手动作展现友好"
        elif '汇总' in dance_label:
            return "音乐丰富，组合动作展现完整性"
        else:
            return f"根据音乐特征选择{dance_label}动作"

    def _select_by_time_only(self, remaining_time: float):
        """仅基于时间的选择（回退方案）"""
        available_actions = [
            action for action in self.dance_actions
            if action.time <= remaining_time * 1000
        ]

        if not available_actions:
            return None

        # 随机选择
        selected_action = random.choice(available_actions)
        dance_data = self.dance_mapping[selected_action.label]
        reason = f"基于剩余时间{remaining_time:.1f}秒选择"

        return selected_action.label, dance_data, reason

    def get_music_analysis_summary(self, music_features: MusicFeatures) -> str:
        """获取音乐分析摘要"""
        tempo_desc = "快节奏" if music_features.tempo > 140 else "慢节奏" if music_features.tempo < 80 else "中等节奏"
        energy_desc = "高能量" if music_features.energy > 0.5 else "低能量" if music_features.energy < 0.2 else "中等能量"

        summary = f"音乐分析: {tempo_desc}({music_features.tempo:.0f}BPM), {energy_desc}({music_features.energy:.2f})"

        if hasattr(music_features, 'mood'):
            summary += f", {music_features.mood}情绪"

        if hasattr(music_features, 'segment_type'):
            segment_names = {
                'intro': '前奏', 'verse': '主歌', 'chorus': '副歌',
                'bridge': '过渡', 'outro': '尾奏'
            }
            segment_name = segment_names.get(music_features.segment_type, music_features.segment_type)
            summary += f", {segment_name}段落"

        return summary

    def reset_markov_state(self):
        """重置马尔可夫状态"""
        self.current_action = None
        self.action_history = []
        print("🔄 马尔可夫状态已重置")

    def get_transition_stats(self) -> Dict:
        """获取转移统计信息"""
        if len(self.action_history) < 2:
            return {"message": "历史动作不足，无法统计"}

        transitions = defaultdict(int)
        for i in range(len(self.action_history) - 1):
            from_action = self.action_history[i]
            to_action = self.action_history[i + 1]
            transitions[f"{from_action}→{to_action}"] += 1

        return dict(transitions)

    def print_markov_status(self):
        """打印马尔可夫状态信息"""
        print(f"\n🎭 马尔可夫链状态:")
        print(f"   当前动作: {self.current_action or '无'}")
        print(f"   历史长度: {len(self.action_history)}")
        print(f"   融合权重: 音乐{self.music_weight:.2f} + 连贯性{self.markov_weight:.2f}")

        if len(self.action_history) >= 2:
            print(f"   最近转移: {self.action_history[-2]} → {self.action_history[-1]}")

        type_counts = defaultdict(int)
        for action_label in self.action_history:
            action_type = self.transition_matrix.action_types.get(action_label, "general")
            type_counts[action_type] += 1

        if type_counts:
            print(f"   动作类型分布: {dict(type_counts)}")
