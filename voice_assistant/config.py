#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 统一配置中心

🎛️ 快速调节VAD敏感度：
   修改第51行的 VAD_SENSITIVITY_PRESET 值：
   1 = 高敏感度 (安静环境，容易触发)
   2 = 中等敏感度 (一般环境，平衡)
   3 = 低敏感度 (嘈杂环境，不易触发) ← 当前设置
   4 = 超低敏感度 (很嘈杂环境，很难触发)

🔧 其他常用调节：
   - 第47行：AUDIO_SAMPLE_RATE (音频采样率，None=自动检测)
   - 第49行：AUDIO_MAX_RECORDING_DURATION (最大录音时长)
   - 第54行：TTS_DEFAULT_VOLUME (语音播放音量 1-10)


"""

import os


class Config:
    """配置类"""

    # API配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    BAIDU_API_KEY = os.getenv("BAIDU_API_KEY")
    BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")
    
    # DeepSeek API配置
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"
    DEEPSEEK_TEMPERATURE = 0.3
    DEEPSEEK_MAX_TOKENS = 200
    DEEPSEEK_TIMEOUT = 30
    
    # 百度API配置
    BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    BAIDU_ASR_URL = "https://vop.baidu.com/server_api"
    BAIDU_TTS_URL = "https://tsn.baidu.com/text2audio"
    BAIDU_ASR_SCOPE = "audio_voice_assistant_get"
    BAIDU_TTS_SCOPE = "audio_tts_post"
    
    # 音频配置 - 强制使用16000Hz以确保百度API兼容性
    AUDIO_FORMAT = 16  # pyaudio.paInt16
    AUDIO_CHANNELS = 1
    AUDIO_SAMPLE_RATE = 16000  # 强制使用16000Hz，与百度API完美兼容
    AUDIO_CHUNK_SIZE = 1024
    AUDIO_MAX_RECORDING_DURATION = 15.0  # 单次录音最大时长（秒）- 可随时调整

    # 拓展坞音频设备配置 - 直接指定ALSA设备
    AUDIO_INPUT_DEVICE_INDEX = None  # PyAudio设备索引，None=自动检测
    AUDIO_ALSA_DEVICE = None         # 暂时禁用ALSA直接访问，使用PyAudio

    # 音频设备自动检测
    @staticmethod
    def get_best_sample_rate():
        """自动检测最佳采样率"""
        try:
            import pyaudio
            audio = pyaudio.PyAudio()

            # 百度API支持的采样率，按优先级排序
            preferred_rates = [16000, 8000, 44100, 48000, 22050]

            try:
                # 获取默认输入设备
                default_device = audio.get_default_input_device_info()
                device_index = default_device['index']

                # 测试支持的采样率
                for rate in preferred_rates:
                    try:
                        if audio.is_format_supported(
                            rate=rate,
                            input_device=device_index,
                            input_channels=1,
                            input_format=pyaudio.paInt16
                        ):
                            print(f"🎤 自动检测到支持的采样率: {rate}Hz")
                            audio.terminate()
                            return rate
                    except:
                        continue

                # 如果都不支持，使用设备默认采样率
                default_rate = int(default_device['defaultSampleRate'])
                print(f"🎤 使用设备默认采样率: {default_rate}Hz")
                audio.terminate()
                return default_rate

            except Exception as e:
                print(f"⚠️ 音频设备检测失败: {e}")
                audio.terminate()
                return 44100  # fallback

        except ImportError:
            print("⚠️ pyaudio未安装，使用默认采样率44100Hz")
            return 44100

    @staticmethod
    def test_audio_devices():
        """测试音频设备 - 集成的诊断工具"""
        print("🔍 音频设备诊断工具")
        print("=" * 50)

        try:
            import pyaudio
            audio = pyaudio.PyAudio()

            print(f"📊 检测到 {audio.get_device_count()} 个音频设备:")

            input_devices = []
            for i in range(audio.get_device_count()):
                try:
                    info = audio.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        input_devices.append((i, info))
                        print(f"\n🎤 输入设备 {i}: {info['name']}")
                        print(f"   默认采样率: {info['defaultSampleRate']}Hz")
                        print(f"   最大输入通道: {info['maxInputChannels']}")

                        # 测试支持的采样率
                        print("   支持的采样率:")
                        for rate in [8000, 16000, 22050, 44100, 48000]:
                            try:
                                supported = audio.is_format_supported(
                                    rate=rate, input_device=i, input_channels=1, input_format=pyaudio.paInt16
                                )
                                print(f"     {rate}Hz: {'✅' if supported else '❌'}")
                            except:
                                print(f"     {rate}Hz: ❌")
                except Exception as e:
                    print(f"   ❌ 设备 {i} 信息获取失败: {e}")

            if not input_devices:
                print("\n❌ 没有找到可用的输入设备")
                print("💡 请检查:")
                print("   1. 麦克风是否正确连接")
                print("   2. 音频驱动是否正确安装")
                print("   3. 设备权限: ls -l /dev/snd/")
            else:
                print(f"\n✅ 找到 {len(input_devices)} 个输入设备")
                best_rate = Config.get_best_sample_rate()
                print(f"🎯 推荐采样率: {best_rate}Hz")
                print(f"\n💡 如需手动指定，修改config.py中的:")
                print(f"   AUDIO_SAMPLE_RATE = {best_rate}")

            audio.terminate()

        except ImportError:
            print("❌ pyaudio未安装")
            print("💡 请运行: pip install pyaudio")
        except Exception as e:
            print(f"❌ 音频系统检测失败: {e}")

        print("\n" + "=" * 50)

    @staticmethod
    def scan_serial_ports():
        """扫描可用的串口设备"""
        print("🔍 扫描串口设备:")
        common_ports = [
            '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
            '/dev/ttyAMA0', '/dev/ttyAMA1', '/dev/ttyAMA2',
            '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyS2'
        ]

        found_ports = []
        for port in common_ports:
            if os.path.exists(port):
                found_ports.append(port)
                print(f"   ✅ {port}")
            else:
                print(f"   ❌ {port}")

        if not found_ports:
            print("⚠️ 没有找到任何串口设备")
            print("💡 请检查USB转串口设备是否正确连接")
        else:
            print(f"✅ 找到 {len(found_ports)} 个串口设备")

        return found_ports

    @staticmethod
    def test_serial_port(port: str, baudrate: int = 115200) -> bool:
        """测试指定串口是否可用"""
        try:
            import serial
            with serial.Serial(port, baudrate, timeout=1) as ser:
                return True
        except ImportError:
            print("⚠️ pyserial模块未安装")
            return False
        except Exception:
            return False

    @staticmethod
    def auto_detect_serial_port():
        """自动检测可用的串口设备"""
        print("🔍 自动检测串口设备...")

        # 优先级顺序：USB转串口 > 硬件串口 > 标准串口
        priority_ports = [
            '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
            '/dev/ttyAMA0', '/dev/ttyAMA1', '/dev/ttyAMA2',
            '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyS2'
        ]

        for port in priority_ports:
            if os.path.exists(port) and Config.test_serial_port(port):
                print(f"✅ 自动检测到可用串口: {port}")
                return port

        print("❌ 未找到可用的串口设备")
        return None
    
    # TTS配置
    TTS_DEFAULT_VOLUME = 7  # 1-10
    TTS_TIMEOUT = 60.0  # 百度TTS上限60秒
    TTS_DEFAULT_VOICE = 5  # 度小娇
    
    # 语音识别配置
    ASR_MIN_FILE_SIZE = 1000  # 最小音频文件大小
    ASR_TIMEOUT = 30

    # ==================== VAD配置 - 可调节敏感度 ====================
    # 💡 快速调节敏感度：修改下面的 VAD_SENSITIVITY_PRESET 值
    # 1=高敏感(安静环境) 2=中等敏感(一般环境) 3=低敏感(嘈杂环境) 4=超低敏感(很嘈杂)
    VAD_SENSITIVITY_PRESET = 2  # 🎛️ 调整为中等敏感度，提高识别准确性

    # 预设配置 - 平衡长句识别和响应速度
    _VAD_PRESETS = {
        1: {  # 高敏感度 - 安静环境，容易触发但可能有杂音
            'volume_threshold': 25.0, 'webrtc_aggressiveness': 0, 'confidence_threshold': 0.15,
            'detection_frames': 2, 'confirmation_frames': 3, 'silence_frames_limit': 12, 'min_speech_duration': 0.8
        },
        2: {  # 中等敏感度 - 平衡设置，既支持长句又有合理响应速度
            'volume_threshold': 35.0, 'webrtc_aggressiveness': 1, 'confidence_threshold': 0.25,
            'detection_frames': 3, 'confirmation_frames': 4, 'silence_frames_limit': 15, 'min_speech_duration': 1.0
        },
        3: {  # 低敏感度 - 嘈杂环境，减少误触发
            'volume_threshold': 45.0, 'webrtc_aggressiveness': 2, 'confidence_threshold': 0.35,
            'detection_frames': 4, 'confirmation_frames': 5, 'silence_frames_limit': 18, 'min_speech_duration': 1.2
        },
        4: {  # 超低敏感度 - 很嘈杂环境，只响应明确的语音
            'volume_threshold': 60.0, 'webrtc_aggressiveness': 3, 'confidence_threshold': 0.45,
            'detection_frames': 5, 'confirmation_frames': 6, 'silence_frames_limit': 22, 'min_speech_duration': 1.5
        }
    }

    # 自动应用选定的预设
    _current_preset = _VAD_PRESETS.get(VAD_SENSITIVITY_PRESET, _VAD_PRESETS[3])
    VAD_BASE_VOLUME_THRESHOLD = _current_preset['volume_threshold']
    VAD_WEBRTC_AGGRESSIVENESS = _current_preset['webrtc_aggressiveness']
    VAD_CONFIDENCE_THRESHOLD = _current_preset['confidence_threshold']
    VAD_DETECTION_FRAMES = _current_preset['detection_frames']
    VAD_CONFIRMATION_FRAMES = _current_preset['confirmation_frames']
    VAD_SILENCE_FRAMES_LIMIT = _current_preset['silence_frames_limit']
    VAD_MIN_SPEECH_DURATION = _current_preset['min_speech_duration']
    VAD_MAX_SPEECH_DURATION = 20.0      # 最大单次语音时长（秒，支持长句）
    VAD_MAX_SILENCE_DURATION = 1.2      # 最大静音持续时间（秒，平衡长句支持和响应速度）

    # 置信度权重 - 平衡WebRTC和音量检测
    VAD_WEBRTC_WEIGHT = 0.6             # WebRTC权重（提高以利用专业算法）
    VAD_VOLUME_WEIGHT = 0.4             # 音量权重（降低以减少噪音影响）

    # 环境自适应 - 更智能的噪音处理
    VAD_ENABLE_NOISE_ADAPTATION = True  # 启用噪音自适应
    VAD_NOISE_ADAPTATION_FRAMES = 30    # 用于学习噪音基线的帧数（减少以更快适应）
    VAD_NOISE_MULTIPLIER = 3.5          # 噪音基线倍数（提高以减少环境噪音干扰）

    # 质量控制 - 新增参数
    VAD_ENABLE_QUALITY_CHECK = True     # 启用录音质量检查
    VAD_MIN_AUDIO_ENERGY = 100.0        # 最小音频能量阈值
    VAD_MAX_ZERO_CROSSING_RATE = 0.3    # 最大过零率（用于检测噪音）

    # 调试模式 - 用于诊断VAD问题
    VAD_ENABLE_DEBUG = False             # 启用VAD调试信息，帮助诊断等待问题

    # ==================== 音乐分析配置 ====================

    # 音乐分析功能开关
    MUSIC_ANALYSIS_ENABLED = True        # 启用真正的音乐分析功能
    MUSIC_ANALYSIS_SAMPLE_RATE = 22050   # 音乐分析采样率（较低以减少计算负担）
    MUSIC_ANALYSIS_CHUNK_SIZE = 1024     # 音频块大小
    MUSIC_ANALYSIS_WINDOW = 2.0          # 分析窗口时长（秒）

    # 音乐特征阈值
    MUSIC_TEMPO_FAST_THRESHOLD = 140     # 快节奏阈值 (BPM)
    MUSIC_TEMPO_SLOW_THRESHOLD = 80      # 慢节奏阈值 (BPM)
    MUSIC_ENERGY_HIGH_THRESHOLD = 0.5    # 高能量阈值
    MUSIC_ENERGY_LOW_THRESHOLD = 0.2     # 低能量阈值

    # 智能动作选择
    MUSIC_DRIVEN_SELECTION = True        # 启用基于音乐的动作选择
    MUSIC_ANALYSIS_DEBUG = False         # 音乐分析调试模式

    # 马尔可夫链舞蹈选择器配置
    MARKOV_CHAIN_ENABLED = True          # 启用马尔可夫链动作连贯性
    MARKOV_MUSIC_WEIGHT = 0.7            # 音乐匹配权重 (0.0-1.0)
    MARKOV_COHERENCE_WEIGHT = 0.3        # 动作连贯性权重 (0.0-1.0)
    MARKOV_TEMPERATURE = 0.8             # 选择随机性温度参数 (0.1-2.0)
    MARKOV_HISTORY_LENGTH = 10           # 动作历史记录长度

    # 音乐结构分析
    MUSIC_STRUCTURE_ANALYSIS = True      # 启用音乐结构分析
    MUSIC_STRUCTURE_DEBUG = False        # 结构分析调试模式
    MUSIC_SEGMENT_MIN_DURATION = 8.0     # 最小段落时长（秒）
    MUSIC_INTENSITY_HIGH_THRESHOLD = 0.7 # 高强度阈值
    MUSIC_INTENSITY_LOW_THRESHOLD = 0.3  # 低强度阈值



    # ==================== 录音文件管理 ====================
    AUDIO_AUTO_DELETE = True            # 录音文件用完立即删除
    AUDIO_CLEANUP_ON_START = True       # 启动时清理所有录音文件
    
    # 系统配置
    ALSA_PCM_CARD = '0'
    ALSA_PCM_DEVICE = '0'

    # 舵机控制串口配置
    SERVO_SERIAL_PORT = '/dev/ttyUSB0'  # 舵机控制板串口（USB转串口）
    SERVO_BAUDRATE = 115200             # 舵机控制板波特率
    
    # 语音识别配置
    ASR_MIN_FILE_SIZE = 5000  # 最小音频文件大小（增加到5KB，确保有足够内容）

    # 语音命令配置
    EXIT_COMMANDS = ['退出对话', '结束对话', 'exit', 'quit', '再见对话']
    MUTE_COMMANDS = ['关闭语音', '静音', '不要说话']
    UNMUTE_COMMANDS = ['开启语音', '打开语音', '开始说话', '取消静音']
    SKIP_COMMANDS = ['跳过', '下一个', '停止播放', '跳过播放']
    VOLUME_UP_COMMANDS = ['音量调高', '声音大一点', '音量增加', '调高音量']
    VOLUME_DOWN_COMMANDS = ['音量调低', '声音小一点', '音量减少', '调低音量']

    # 舞蹈命令
    DANCE_STOP_COMMANDS = ['停止跳舞', '不跳了', '停止舞蹈']
    DANCE_LIST_COMMANDS = ['舞蹈列表', '有什么舞蹈', '舞蹈文件']



    # 百度TTS语音选项
    TTS_VOICES = {
        0: "度小美", 1: "度小宇", 3: "度逍遥", 4: "度丫丫",
        5: "度小娇", 103: "度米朵", 106: "度博文", 110: "度小童", 111: "度小萌"
    }
    
    # AI系统提示
    AI_SYSTEM_PROMPT = (
        "你是一个语音助手，请用直截了当的方式回答问题。"
        "回答要点明确，避免过长的解释。每个回答控制在150字以内，"
        "除非用户明确要求详细解释。"
    )
    
    @classmethod
    def validate_api_keys(cls):
        """验证API密钥配置"""
        if not cls.DEEPSEEK_API_KEY:
            return False, "请设置DEEPSEEK_API_KEY环境变量"
        
        if not cls.BAIDU_API_KEY or not cls.BAIDU_SECRET_KEY:
            return False, "请设置BAIDU_API_KEY和BAIDU_SECRET_KEY环境变量"
        
        return True, "API密钥配置正确"
    
    @classmethod
    def setup_environment(cls):
        """设置环境变量"""
        os.environ['ALSA_PCM_CARD'] = cls.ALSA_PCM_CARD
        os.environ['ALSA_PCM_DEVICE'] = cls.ALSA_PCM_DEVICE
    
    @classmethod
    def get_voice_name(cls, voice_id: int) -> str:
        """获取语音名称"""
        return cls.TTS_VOICES.get(voice_id, f"语音{voice_id}")


# 全局配置实例
config = Config()
