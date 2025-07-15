#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能语音舞蹈机器人
"""

import sys
import signal
from voice_assistant.core.assistant import VoiceAssistant
from dance_system import DanceRobot


def signal_handler(signum, frame):
    """信号处理器"""
    _ = signum, frame  # 避免未使用变量警告
    print("\n👋 再见")
    sys.exit(0)


def main():
    """主函数"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🤖 智能语音舞蹈机器人")
    print("🎤 语音控制模式，说'真实跳舞X秒'或'模拟跳舞X秒'开始跳舞")

    try:
        print("🔧 正在初始化系统...")

        # 创建舞蹈机器人（会自动检测串口设备）
        dance_robot = DanceRobot()

        # 创建语音助手（集成舞蹈功能）
        assistant = VoiceAssistant(use_baidu_tts=True)
        assistant.set_dance_handler(dance_robot)

        # 建立双向连接：舞蹈机器人也需要控制语音助手
        dance_robot.set_voice_assistant(assistant)

        print("✅ 系统初始化完成")

        assistant.run_voice_chat()

    except KeyboardInterrupt:
        print("\n👋 再见")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    main()
