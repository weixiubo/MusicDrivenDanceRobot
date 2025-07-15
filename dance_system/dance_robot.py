#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舞蹈机器人控制器
集成马尔可夫链智能选择器的舞蹈机器人
"""

import os
import time
import threading
from typing import Optional

# 音乐分析相关导入
try:
    from voice_assistant.audio.music_analyzer import create_music_analyzer, MusicFeatures
    from voice_assistant.config import config
    MUSIC_ANALYSIS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 音乐分析模块导入失败: {e}")
    MUSIC_ANALYSIS_AVAILABLE = False
    MusicFeatures = None

from .music_selector import MusicAwareMarkovSelector


class DanceRobot:
    """舞蹈机器人 - 集成马尔可夫链智能选择器"""

    def __init__(self, mapping_file: str = "动作库.csv"):
        """初始化舞蹈机器人"""
        self.mapping_file = mapping_file
        self.is_dancing = False
        self.dance_thread = None
        self.stop_event = threading.Event()

        # 语音助手回调
        self.voice_assistant = None

        # 音乐分析器和智能选择器
        self.music_analyzer = None
        self.music_selector = None
        self.current_music_features = None
        self.music_analysis_enabled = MUSIC_ANALYSIS_AVAILABLE

        # 串口设备状态
        self.serial_port = None
        self.serial_baudrate = None
        self.serial_available = False

        # 初始化各个组件
        self._init_music_analysis()
        self._initialize_serial_connection()

        # 打印初始化信息
        print(f"🤖 舞蹈机器人初始化完成")
        print(f"   舞蹈动作库: {len(self.music_selector.dance_actions) if self.music_selector else 0}个动作")
        print(f"   串口设备: {'可用' if self.serial_available else '不可用（模拟模式）'}")
        print(f"   音乐分析: {'启用' if self.music_analysis_enabled else '禁用'}")
        if self.serial_available:
            print(f"   串口路径: {self.serial_port}")
            print(f"   波特率: {self.serial_baudrate}")

    def set_voice_assistant(self, voice_assistant):
        """设置语音助手实例"""
        self.voice_assistant = voice_assistant
        print("✅ 舞蹈机器人已连接语音助手")

    def _init_music_analysis(self):
        """初始化音乐分析功能"""
        if not self.music_analysis_enabled:
            print("⚠️ 音乐分析功能不可用（缺少依赖）")
            return

        try:
            # 创建音乐分析器
            self.music_analyzer = create_music_analyzer(
                enable_analysis=config.MUSIC_ANALYSIS_ENABLED
            )

            # 创建马尔可夫链智能选择器
            self.music_selector = MusicAwareMarkovSelector(csv_file=self.mapping_file)

            # 设置音乐特征回调
            self.music_analyzer.set_feature_callback(self._on_music_features_updated)

            print("✅ 音乐分析功能初始化完成")

        except Exception as e:
            print(f"⚠️ 音乐分析功能初始化失败: {e}")
            self.music_analysis_enabled = False

    def _on_music_features_updated(self, features: MusicFeatures):
        """音乐特征更新回调"""
        self.current_music_features = features

    def _initialize_serial_connection(self):
        """初始化串口连接"""
        print("🔧 初始化舵机控制板连接...")
        
        # 首先尝试配置文件中指定的串口
        configured_port = config.SERVO_SERIAL_PORT
        self.serial_baudrate = config.SERVO_BAUDRATE
        if self._test_serial_port(configured_port):
            self.serial_port = configured_port
            self.serial_available = True
            print(f"✅ 使用配置的串口: {configured_port}")
            return

        # 如果配置的串口不可用，尝试自动检测
        print(f"⚠️ 配置的串口 {configured_port} 不可用，尝试自动检测...")
        
        # 常见的串口设备路径
        potential_ports = [
            '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
            '/dev/ttyAMA0', '/dev/ttyAMA1', '/dev/ttyAMA2', '/dev/ttyAMA3', '/dev/ttyAMA4',
            '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyS2', '/dev/ttyS3'
        ]
        
        for port in potential_ports:
            if self._test_serial_port(port):
                self.serial_port = port
                self.serial_available = True
                print(f"✅ 自动检测到可用串口: {port}")
                return
        
        print("⚠️ 未找到可用的串口设备，将使用模拟模式")
        self.serial_available = False

    def _test_serial_port(self, port: str) -> bool:
        """测试串口是否可用"""
        if not os.path.exists(port):
            return False

        try:
            import serial
            with serial.Serial(port, config.SERVO_BAUDRATE, timeout=1) as ser:
                return True
        except ImportError:
            print("⚠️ pyserial模块未安装，无法测试串口")
            return False
        except Exception:
            return False

    def start_timed_dance(self, duration_seconds: int, mode: str = "simulate") -> bool:
        """开始定时跳舞"""
        if self.is_dancing:
            print("⚠️ 机器人正在跳舞中，请等待结束")
            return False

        print(f"🎭 开始跳舞 {duration_seconds}秒 ({'真实模式' if mode == 'real' else '模拟模式'})")
        
        # 重置马尔可夫状态
        if self.music_selector:
            self.music_selector.reset_markov_state()

        # 暂停语音识别
        if self.voice_assistant:
            self.voice_assistant.set_dance_mode(True)

        # 启动跳舞线程
        self.stop_event.clear()
        self.dance_thread = threading.Thread(
            target=self._dance_loop,
            args=(duration_seconds, mode),
            daemon=True
        )
        self.dance_thread.start()
        return True

    def stop_dance(self):
        """停止跳舞"""
        if self.is_dancing:
            print("🛑 停止跳舞")
            self.stop_event.set()
            if self.dance_thread and self.dance_thread.is_alive():
                self.dance_thread.join(timeout=2)
            self.is_dancing = False

            # 恢复语音识别
            if self.voice_assistant:
                self.voice_assistant.set_dance_mode(False)

    def _dance_loop(self, duration_seconds: int, mode: str):
        """舞蹈主循环"""
        self.is_dancing = True
        start_time = time.time()
        end_time = start_time + duration_seconds

        # 启动音乐分析
        music_analysis_active = False
        if self.music_analysis_enabled and self.music_analyzer:
            try:
                self.music_analyzer.start_analysis()
                music_analysis_active = True
                print("🎵 音乐分析已启动，开始智能听音编舞")
            except Exception as e:
                print(f"⚠️ 音乐分析启动失败: {e}")
                print("🎭 使用传统时间选择方式")

        while not self.stop_event.is_set():
            current_time = time.time()
            remaining_time = end_time - current_time

            if remaining_time <= 0:
                print(f"⏰ 已达到目标时间 {duration_seconds}秒，结束跳舞")
                break

            # 智能选择舞蹈动作
            if music_analysis_active and self.music_selector and self.current_music_features:
                result = self.music_selector.select_dance_by_music(
                    self.current_music_features, remaining_time, mode
                )
                if result:
                    dance_label, dance_data, selection_reason = result
                    # 显示音乐分析摘要
                    music_summary = self.music_selector.get_music_analysis_summary(self.current_music_features)
                    print(f"🎵 {music_summary}")
                else:
                    # 回退到传统选择
                    dance_label, dance_data, selection_reason = self._select_dance_with_reason(remaining_time)
            else:
                # 传统时间选择
                dance_label, dance_data, selection_reason = self._select_dance_with_reason(remaining_time)

            duration_s = dance_data['time'] / 1000.0
            print(f"💃 执行舞蹈: {dance_label} (Seq: {dance_data['seq']}, {duration_s:.1f}秒)")
            print(f"🤔 选择理由: {selection_reason}")

            # 执行舞蹈动作
            print(f"   🎵 开始执行舞蹈动作 {duration_s:.1f}秒...")
            self._execute_dance_action(dance_data, mode)

            # 检查是否应该继续
            elapsed = time.time() - start_time
            if elapsed >= duration_seconds:
                print(f"   ✅ 舞蹈动作执行完毕，总时长: {elapsed:.1f}秒（超出 {elapsed - duration_seconds:.1f}秒完成最后动作）")
                break

        # 停止音乐分析
        if music_analysis_active and self.music_analyzer:
            try:
                self.music_analyzer.stop_analysis()
                print("🎵 音乐分析已停止")
            except Exception as e:
                print(f"⚠️ 停止音乐分析时出错: {e}")

        self.is_dancing = False

        # 恢复语音识别
        if self.voice_assistant:
            self.voice_assistant.set_dance_mode(False)

        print("🎭 跳舞结束")

        # 显示马尔可夫状态
        if self.music_selector:
            self.music_selector.print_markov_status()

    def _select_dance_with_reason(self, remaining_time: float):
        """传统的基于时间的舞蹈选择（回退方案）"""
        if self.music_selector:
            result = self.music_selector._select_by_time_only(remaining_time)
            if result:
                return result
            else:
                # 如果没有可用动作，返回最短的动作
                shortest_action = min(self.music_selector.dance_actions, key=lambda x: x.time)
                dance_data = self.music_selector.dance_mapping[shortest_action.label]
                return shortest_action.label, dance_data, f"时间不足，选择最短动作({shortest_action.time/1000:.1f}秒)"
        else:
            # 如果没有选择器，返回默认动作
            return "立正", {"seq": "001", "title": "立正", "time": 1000}, "默认动作"

    def _execute_dance_action(self, dance_data: dict, mode: str):
        """执行舞蹈动作"""
        seq = dance_data['seq']
        duration_ms = dance_data['time']

        if mode == "real" and self.serial_available:
            # 真实模式：发送串口命令
            self._send_servo_command(seq)
        else:
            # 模拟模式：仅显示信息
            print(f"   🎭 模拟执行: Seq {seq}")

        # 等待动作完成
        time.sleep(duration_ms / 1000.0)

    def _send_servo_command(self, seq: str):
        """
        发送舵机控制命令
        格式: ser0.write(b'\\xA9\\x9A\\x03\\x41\\x{Seq}\\x{checksum}\\xED\\n\\r')
        """
        try:
            import serial

            # 将Seq转换为十六进制数（CSV中的Seq是字符串如"000", "001"）
            seq_int = int(seq)  # 将"000"转为0, "001"转为1

            # 计算校验和：Seq + 0x44，取最后两位
            checksum = (seq_int + 0x44) & 0xFF

            # 构建命令：\xA9\x9A\x03\x41\x{Seq}\x{checksum}\xED\n\r
            command_bytes = bytes([0xA9, 0x9A, 0x03, 0x41, seq_int, checksum, 0xED]) + b'\n\r'

            # 发送命令
            with serial.Serial(self.serial_port, self.serial_baudrate, timeout=1) as ser:
                ser.write(command_bytes)

                # 显示详细信息
                hex_str = ' '.join([f'{b:02X}' for b in command_bytes])
                print(f"   📡 发送舵机命令: Seq={seq}({seq_int}) -> {hex_str}")
                print(f"   🔧 命令解析: A9 9A 03 41 {seq_int:02X} {checksum:02X} ED 0A 0D")

        except ImportError:
            print("   ⚠️ pyserial未安装，无法发送串口命令")
        except ValueError as e:
            print(f"   ❌ 无效的Seq值: {seq} - {e}")
        except Exception as e:
            print(f"   ❌ 串口命令发送失败: {e}")

    def execute_single_action(self, action_label: str, mode: str = "simulate") -> bool:
        """执行单个舞蹈动作"""
        if self.is_dancing:
            print("⚠️ 机器人正在跳舞中，无法执行单个动作")
            return False

        if not self.music_selector:
            print("❌ 舞蹈选择器未初始化")
            return False

        try:
            # 获取动作数据
            action = self.music_selector.action_library.get_action_by_label(action_label)
            dance_data = self.music_selector.dance_mapping[action_label]

            duration_s = dance_data['time'] / 1000.0
            print(f"💃 执行单个动作: {action_label} (Seq: {dance_data['seq']}, {duration_s:.1f}秒)")

            # 执行动作
            self._execute_dance_action(dance_data, mode)

            print(f"✅ 动作执行完成")
            return True

        except ValueError:
            print(f"❌ 动作未找到: {action_label}")
            return False
        except Exception as e:
            print(f"❌ 动作执行失败: {e}")
            return False

    def list_available_actions(self):
        """列出所有可用的舞蹈动作"""
        if not self.music_selector:
            print("❌ 舞蹈选择器未初始化")
            return

        print("🎭 可用的舞蹈动作:")
        for action in self.music_selector.dance_actions:
            duration_s = action.time / 1000.0
            print(f"   {action.label} - {action.title} ({duration_s:.1f}秒)")

    def get_dance_status(self) -> dict:
        """获取舞蹈状态信息"""
        status = {
            "is_dancing": self.is_dancing,
            "serial_available": self.serial_available,
            "serial_port": self.serial_port,
            "music_analysis_enabled": self.music_analysis_enabled,
            "action_count": len(self.music_selector.dance_actions) if self.music_selector else 0
        }

        if self.music_selector:
            status["current_action"] = self.music_selector.current_action
            status["action_history"] = self.music_selector.action_history[-5:]  # 最近5个动作
            status["transition_stats"] = self.music_selector.get_transition_stats()

        return status

    def print_status(self):
        """打印详细状态信息"""
        status = self.get_dance_status()

        print(f"\n🤖 舞蹈机器人状态:")
        print(f"   跳舞状态: {'跳舞中' if status['is_dancing'] else '待机'}")
        print(f"   串口状态: {'可用' if status['serial_available'] else '不可用'}")
        if status['serial_available']:
            print(f"   串口路径: {status['serial_port']}")
        print(f"   音乐分析: {'启用' if status['music_analysis_enabled'] else '禁用'}")
        print(f"   动作库: {status['action_count']}个动作")

        if self.music_selector:
            print(f"   当前动作: {status.get('current_action', '无')}")
            if status.get('action_history'):
                print(f"   动作历史: {' → '.join(status['action_history'])}")

            # 显示马尔可夫状态
            self.music_selector.print_markov_status()

    def handle_voice_command(self, text: str) -> bool:
        """
        处理语音命令

        Args:
            text: 语音识别的文本（已转为小写）

        Returns:
            bool: True表示命令已处理，False表示不是舞蹈命令
        """
        # 定时跳舞命令
        if "跳舞" in text:
            # 提取时间
            import re
            time_match = re.search(r'(\d+)秒', text)
            if time_match:
                duration = int(time_match.group(1))

                # 判断模式
                if "真实" in text or "舵机" in text:
                    mode = "real"
                    print(f"🎭 收到真实跳舞命令: {duration}秒")
                else:
                    mode = "simulate"
                    print(f"🎭 收到模拟跳舞命令: {duration}秒")

                # 开始跳舞
                success = self.start_timed_dance(duration, mode)
                if not success:
                    print("⚠️ 跳舞启动失败")

                return True

        # 停止跳舞命令
        if "停止跳舞" in text or "停止舞蹈" in text:
            print("🛑 收到停止跳舞命令")
            self.stop_dance()
            return True

        # 执行单个动作命令
        if "执行动作" in text or "做动作" in text or "执行" in text:
            # 提取动作名称
            for action in (self.music_selector.dance_actions if self.music_selector else []):
                if action.label in text:
                    print(f"🎭 收到执行动作命令: {action.label}")

                    # 判断模式
                    if "真实" in text or "舵机" in text:
                        mode = "real"
                    else:
                        mode = "simulate"

                    success = self.execute_single_action(action.label, mode)
                    if not success:
                        print(f"⚠️ 动作执行失败: {action.label}")

                    return True

        # 舞蹈列表命令
        if "舞蹈列表" in text or "动作列表" in text or "有什么动作" in text:
            print("📋 显示舞蹈动作列表:")
            self.list_available_actions()
            return True

        # 舞蹈状态命令
        if "舞蹈状态" in text or "机器人状态" in text:
            print("🤖 显示舞蹈机器人状态:")
            self.print_status()
            return True

        return False
