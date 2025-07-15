#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舞蹈系统模块
包含智能舞蹈选择器、马尔可夫链连贯性算法和舞蹈机器人控制
"""

from .dance_robot import DanceRobot
from .music_selector import MusicAwareMarkovSelector, DanceAction
from .action_library import ActionLibrary

__all__ = [
    'DanceRobot',
    'MusicAwareMarkovSelector', 
    'DanceAction',
    'ActionLibrary'
]

__version__ = "1.0.0"
