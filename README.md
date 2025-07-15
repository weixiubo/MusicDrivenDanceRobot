# Intelligent Voice-Controlled Dance Robot

An intelligent dance robot system based on voice recognition and music analysis, supporting real-time voice control and music-driven dance performances.

## Features

- 🎤 **Intelligent Voice Recognition**: Based on Baidu Speech Recognition API, supports natural language conversation
- 🤖 **AI Conversation System**: Integrated with DeepSeek LLM for intelligent dialogue experience
- 💃 **Dance Control System**: Voice command control for robot to execute preset dance actions
- 🎵 **Music-Driven Dance**: Real-time analysis of music rhythm, energy and emotion for intelligent action selection
- 🔗 **Markov Chain Enhancement**: Action selection combines music matching and coherence for smoother and more natural dance
- 🔊 **Voice Synthesis**: Baidu TTS support for natural voice feedback
- 🎛️ **Intelligent VAD**: Adaptive voice activity detection, automatically recognizes speech start and end

## Quick Start

### Requirements

- Python 3.8+
- Orange Pi AI Pro (recommended) or other Linux systems
- Servo control board (optional, for real dance)
- Microphone and speakers

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Additional installation on Orange Pi
sudo apt-get install portaudio19-dev python3-dev
```

### API Configuration

Set environment variables:

```bash
export BAIDU_API_KEY="your_baidu_api_key"
export BAIDU_SECRET_KEY="your_baidu_secret_key"  
export DEEPSEEK_API_KEY="your_deepseek_api_key"
```

### Run

```bash
python main.py
```

## Usage

### Voice Commands

**Basic Conversation:**
- Speak directly to start conversation, system automatically detects speech start and end

**🎭 Dance Control Commands:**

#### Timed Dancing
- `"Real dance for 20 seconds"` - Start real servo dancing for 20 seconds
- `"Servo dance for 15 seconds"` - Start real servo dancing for 15 seconds  
- `"Simulate dance for 30 seconds"` - Start simulation dance mode for 30 seconds
- `"Dance for 10 seconds"` - Default simulation dance for 10 seconds

#### Single Action Execution
**Real Servo Mode (actual robot control):**
- `"Real execute action forward"` - Real execution of forward action
- `"Servo execute action stand"` - Real execution of stand action
- `"Real do action turn left"` - Real execution of left turn action

**Simulation Mode (command line output only):**
- `"Execute action forward"` - Simulate forward action
- `"Do action stand"` - Simulate stand action
- `"Execute action: turn left"` - Simulate left turn action

#### Dance System Query
- `"Dance list"` - View all available dance actions
- `"Action list"` - View all available dance actions
- `"Robot status"` - View detailed dance robot status

#### Dance Control
- `"Stop dancing"` - Stop current dance

**🎤 System Control Commands:**
- `"Volume to 5"` - Adjust voice playback volume (1-10 levels)
- `"Clear history"` - Clear conversation history
- `"Exit conversation"` - End program

**⚠️ Important Notes:**
- **Real Mode**: Commands containing "real" or "servo" keywords will send serial commands to control actual robot
- **Simulation Mode**: Default mode, only displays execution process in command line, does not control actual hardware
- **Action Names**: Must use label names defined in 动作库.csv (e.g., "stand", "forward", "turn left", etc.)

### Configuration

Main configuration file: `voice_assistant/config.py`

**Quick VAD sensitivity adjustment:**
```python
VAD_SENSITIVITY_PRESET = 2  # 1-4, smaller number = more sensitive
```

## Project Structure

```
Intelligent Voice Dance Robot/
├── main.py                 # 🚀 Main program entry
├── 动作库.csv              # 📊 Dance action mapping table
├── dance_system/           # 🎭 Dance system core
│   ├── action_library.py  #   Action library manager
│   ├── music_selector.py  #   Music-aware Markov chain selector
│   └── dance_robot.py     #   Dance robot controller
└── voice_assistant/        # 🎤 Voice interaction core
    ├── config.py          #   System configuration
    ├── audio/             #   Audio processing
    ├── speech/            #   Speech recognition & synthesis
    ├── chat/              #   AI conversation
    └── core/              #   Core control
```

**Core Features:**
- 🎯 **Dual-core Architecture**: Dance system + voice assistant independent modules
- 📦 **Zero Redundancy**: Streamlined file structure, each file has clear purpose
- 🔧 **Easy Maintenance**: Clear module division, convenient for expansion and debugging
