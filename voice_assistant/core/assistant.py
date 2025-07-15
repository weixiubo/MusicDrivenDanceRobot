#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音助手核心模块
主要业务逻辑和对话控制
"""

import os
import re
import tempfile
import time
import threading
from typing import Optional

from ..config import config
from ..audio.recorder import AudioRecorder, is_audio_available, RecordingMode, record_audio
from ..audio.tts import create_tts_manager
from ..speech.baidu_asr import create_baidu_asr
from ..chat.deepseek import create_deepseek_chat


class VoiceAssistant:
    """语音助手主类"""

    def __init__(self,
                 use_baidu_tts: bool = False,
                 initial_volume: int = None,
                 voice_person: int = None,
                 recording_mode: str = "smart_vad"):
        """
        初始化语音助手

        Args:
            use_baidu_tts: 是否使用百度TTS
            initial_volume: 初始音量
            voice_person: 语音人物
            recording_mode: 录音模式 (smart_vad, enter_key, fixed_duration)
        """
        # 初始化各个组件
        self.chat = create_deepseek_chat()
        self.recorder = AudioRecorder() if is_audio_available() else None
        self.speech_recognizer = create_baidu_asr()
        self.tts = create_tts_manager(
            use_baidu=use_baidu_tts,
            voice_person=voice_person,
            initial_volume=initial_volume
        )

        # 录音模式设置
        self.recording_mode = recording_mode

        # 舞蹈命令处理器
        self.dance_handler = None
        self._validate_recording_mode()



        # 语音对话控制
        self.voice_chat_active = True

        # 跳舞模式控制
        self.in_dance_mode = False
        self.dance_paused = False  # 跳舞时暂停语音识别

        if not self.chat:
            raise RuntimeError("无法初始化DeepSeek聊天客户端")

        if not self.speech_recognizer:
            raise RuntimeError("无法初始化百度语音识别")

        if not self.recorder:
            raise RuntimeError("无法初始化录音器")

        # 启动时清理旧录音文件
        self._startup_cleanup()

    def set_dance_handler(self, handler):
        """设置舞蹈命令处理器"""
        self.dance_handler = handler

    def _validate_recording_mode(self):
        """验证录音模式"""
        valid_modes = ["smart_vad", "enter_key", "fixed_duration"]
        if self.recording_mode not in valid_modes:
            print(f"⚠️ 无效的录音模式: {self.recording_mode}")
            print(f"   支持的模式: {valid_modes}")
            print("   使用默认模式: smart_vad")
            self.recording_mode = "smart_vad"
    
    def run_voice_chat(self):
        """运行语音对话"""
        if not is_audio_available():
            print("❌ 音频功能不可用")
            return
        
        self._print_welcome_message()
        
        conversation_count = 0
        
        try:
            while self.voice_chat_active:
                # 检查是否在跳舞模式下暂停
                if self.dance_paused:
                    time.sleep(0.5)  # 暂停期间短暂休眠
                    continue

                conversation_count += 1
                print(f"\n[第{conversation_count}轮对话]")

                # 录音 - 使用更安全的临时文件管理
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, dir='/tmp') as temp_file:
                    temp_filename = temp_file.name
                
                try:
                    # 根据录音模式选择录音方法
                    recording_success = self._record_audio(temp_filename)

                    if recording_success:
                        file_size = os.path.getsize(temp_filename)
                        if file_size < config.ASR_MIN_FILE_SIZE:
                            print("🔇 未检测到声音")
                            continue
                        
                        # 语音识别
                        text = self.speech_recognizer.recognize_audio_file(temp_filename)

                        # 立即删除录音文件
                        self._delete_audio_file(temp_filename)

                        if not text:
                            print("❌ 语音识别失败")
                            continue
                        
                        print(f"👤 你说: {text}")

                        # 处理语音命令
                        if self._handle_voice_commands(text):
                            continue
                        
                        # 获取AI回复
                        response = self.chat.get_response(text)
                        if response:
                            print(f"🤖 AI: {response}")
                            # 语音播放AI回复
                            self.tts.speak(response)
                            # 等待播放完成再进入下一轮对话
                            self.tts.wait_for_speech_complete()
                        else:
                            print("❌ AI回复失败")
                    
                    else:
                        print("❌ 录音失败")
                
                finally:
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
        
        except KeyboardInterrupt:
            print("\n👋 对话被中断")
        except Exception as e:
            print(f"\n❌ 出错: {e}")
        
        print(f"\n📊 共进行了 {conversation_count-1} 轮对话")

    def _record_audio(self, filename: str) -> bool:
        """根据录音模式录音"""
        if self.recording_mode == "smart_vad":
            return self.recorder.record_with_smart_vad(filename)
        elif self.recording_mode == "enter_key":
            print("🎤 按键控制录音模式")
            return self.recorder.record_with_enter_control(filename)
        elif self.recording_mode == "fixed_duration":
            print("🎤 固定时长录音模式 (4秒)")
            return self.recorder.record_for_duration(4.0, filename)
        else:
            print(f"❌ 未知录音模式: {self.recording_mode}")
            return False

    def _print_welcome_message(self):
        """打印欢迎信息"""
        print("\n🎤 智能语音舞蹈机器人")
        print("🔧 百度语音识别 + DeepSeek AI + 百度TTS")
        print("\n💡 语音控制命令:")
        print("   🗣️  基础对话: 直接说话即可与AI对话")
        print("   💃 舞蹈控制: '真实跳舞X秒' / '模拟跳舞X秒' / '停止跳舞'")
        print("   🎭 单个动作: '执行动作：立正' / '执行动作：大创前进' / '动作列表'")
        print("   🔊 音量控制: '音量调高' / '音量调低' / '音量设置为X'")
        print("   🔇 语音控制: '静音' / '取消静音' / '跳过播放'")
        print("   🔄 系统控制: '清空历史' / '退出对话'")
        print("\n🎤 录音模式: 智能VAD - 说话即可开始录音，停止说话自动结束")
        print(f"🔊 当前音量: {self.tts.volume_level}/10")
        print("-" * 50)
    
    def _handle_voice_commands(self, text: str) -> bool:
        """处理语音命令，返回True表示命令已处理，跳过AI对话"""
        text_lower = text.lower()

        # 舞蹈命令处理（优先级最高）
        if self.dance_handler:
            if self.dance_handler.handle_voice_command(text_lower):
                return True

        # 退出命令
        if any(keyword in text_lower for keyword in config.EXIT_COMMANDS):
            print("👋 对话结束！")
            raise KeyboardInterrupt()
        
        # 静音命令
        if any(keyword in text_lower for keyword in config.MUTE_COMMANDS):
            self.tts.toggle_mute()
            return True
        
        # 取消静音命令
        if any(keyword in text_lower for keyword in config.UNMUTE_COMMANDS):
            if self.tts.muted:
                self.tts.toggle_mute()
            else:
                self.tts.enabled = True
                print("🔊 AI语音已开启")
            self.tts.speak("语音功能已开启")
            return True
        
        # 跳过播放命令
        if any(keyword in text_lower for keyword in config.SKIP_COMMANDS):
            if self.tts.is_speaking:
                print("⏭️ 跳过当前AI语音播放")
                self.tts.stop_current_speech()
                print("✅ 已跳过，进入下一轮对话")
            else:
                print("💡 当前没有AI语音播放")
            return True
        
        # 音量调高命令
        if any(keyword in text_lower for keyword in config.VOLUME_UP_COMMANDS):
            self.tts.volume_up()
            self.tts.speak(f"音量已调高到{self.tts.volume_level}")
            return True
        
        # 音量调低命令
        if any(keyword in text_lower for keyword in config.VOLUME_DOWN_COMMANDS):
            self.tts.volume_down()
            self.tts.speak(f"音量已调低到{self.tts.volume_level}")
            return True
        
        # 音量设置命令
        volume_match = re.search(r'音量设置为(\d+)', text)
        if volume_match:
            volume = int(volume_match.group(1))
            if 1 <= volume <= 10:
                self.tts.set_volume(volume)
                self.tts.speak(f"音量已设置为{volume}")
            else:
                self.tts.speak("音量范围是1到10")
            return True
        
        # 清空历史命令
        if any(keyword in text_lower for keyword in ['清空历史', '重新开始', '清除历史', '新对话']):
            self.chat.clear_history()
            self.tts.speak("对话历史已清空，我们重新开始吧")
            return True



        return False



    def stop_voice_chat(self):
        """停止语音对话"""
        self.voice_chat_active = False
        print("🛑 语音对话已停止")

    def start_voice_chat_flag(self):
        """启动语音对话标志"""
        self.voice_chat_active = True
        print("🎤 语音对话已启动")

    def set_dance_mode(self, enabled: bool):
        """设置跳舞模式状态"""
        self.in_dance_mode = enabled
        self.dance_paused = enabled  # 跳舞时暂停语音识别

        # 控制录音器暂停/恢复
        if self.recorder and hasattr(self.recorder, '_smart_recorder') and self.recorder._smart_recorder:
            if enabled:
                self.recorder._smart_recorder.pause_recording()
            else:
                self.recorder._smart_recorder.resume_recording()

        if enabled:
            print("🔇 跳舞模式：语音识别和录音已完全暂停")
        else:
            print("🎤 跳舞结束：语音识别和录音已恢复")



    def _delete_audio_file(self, filename: str):
        """删除录音文件"""
        try:
            if getattr(config, 'AUDIO_AUTO_DELETE', True) and os.path.exists(filename):
                os.unlink(filename)
                print(f"🗑️ 已删除录音文件")

                # 额外清理：删除/tmp目录下的其他临时录音文件
                import glob
                temp_files = glob.glob("/tmp/tmp*.wav")
                for temp_file in temp_files:
                    try:
                        # 只删除超过5分钟的临时文件，避免删除正在使用的文件
                        import time
                        if time.time() - os.path.getmtime(temp_file) > 300:
                            os.unlink(temp_file)
                    except:
                        pass
        except Exception:
            # 删除失败不影响主流程
            pass

    def _startup_cleanup(self):
        """启动时清理所有录音文件"""
        try:
            if not getattr(config, 'AUDIO_CLEANUP_ON_START', True):
                return

            from pathlib import Path
            import glob

            # 查找并删除所有录音文件（包括/tmp目录）
            audio_patterns = ["*.wav", "*.mp3", "temp_*.wav", "recording_*.wav", "user_audio_*.wav"]
            search_dirs = [".", "/tmp"]
            deleted_count = 0

            for search_dir in search_dirs:
                for pattern in audio_patterns:
                    try:
                        if search_dir == "/tmp":
                            # 在/tmp目录中查找临时录音文件
                            files = glob.glob(f"/tmp/tmp*.wav")
                        else:
                            files = list(Path(search_dir).glob(pattern))

                        for file_path in files:
                            try:
                                if isinstance(file_path, str):
                                    os.unlink(file_path)
                                else:
                                    file_path.unlink()
                                deleted_count += 1
                            except:
                                pass
                    except:
                        pass

            if deleted_count > 0:
                print(f"🗑️ 启动清理: 删除了 {deleted_count} 个录音文件")

        except Exception:
            # 清理失败不影响启动
            pass

    def cleanup(self):
        """清理资源"""
        if self.recorder:
            self.recorder.cleanup()
        print("🧹 资源清理完成")


def create_voice_assistant(use_baidu_tts: bool = False,
                          initial_volume: int = None,
                          voice_person: int = None,
                          recording_mode: str = "smart_vad") -> VoiceAssistant:
    """
    创建语音助手实例

    Args:
        use_baidu_tts: 是否使用百度TTS
        initial_volume: 初始音量
        voice_person: 语音人物
        recording_mode: 录音模式 (smart_vad, enter_key, fixed_duration)
    """
    return VoiceAssistant(use_baidu_tts, initial_volume, voice_person, recording_mode)
