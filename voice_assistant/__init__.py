#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orange Pi AI Pro 语音智能助手
重构版本 - 模块化设计
"""

__version__ = "2.0.0"
__author__ = "AI Assistant"
__description__ = "Orange Pi AI Pro 语音智能助手 - 重构版"

from .config import config
from .core.assistant import create_voice_assistant

__all__ = [
    'config',
    'create_voice_assistant'
]
