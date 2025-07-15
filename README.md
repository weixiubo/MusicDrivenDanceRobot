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

## Hardware Connection

### Servo Control Board Connection

1. Connect the servo control board to the device via USB-to-serial
2. Confirm the serial device path (usually `/dev/ttyUSB0`)
3. Set the correct serial path in the configuration file:

```python
SERVO_SERIAL_PORT = '/dev/ttyUSB0'
SERVO_BAUDRATE = 115200
```

### ⚠️ **Important: Servo Action Pre-configuration**

**Before using the real dance function, you must complete the following steps:**

1. **Download actions to the servo control board**:
   - All dance actions must be pre-loaded to the servo control board
   - Each action corresponds to a Seq number (e.g., 000, 001, 002, etc.)
   - The servo control board internally stores the specific servo angle sequences for these actions

2. **Action Library Mapping Table**:
   - The `动作库.csv` file serves as an action mapping table, defining:
     - `Seq`: Action number in the servo control board
     - `title`: Action name
     - `label`: Voice recognition label
     - `time`: Action execution duration (milliseconds)

3. **Working Principle**:
   ```
   Voice Command → Intelligent Selection Algorithm → Look up 动作库.csv → Send Seq Command → Servo Board Executes Pre-stored Action
   ```

4. **Configuration Example**:
   ```csv
   Seq,title,label,time
   000,Initialize,wave,4000
   001,Stand,stand,1000
   002,Forward,forward,7500
   ```

**Note**: If the servo control board does not have the corresponding Seq action pre-stored, the robot will not respond when the command is sent.

### 🎯 **Mode Selection**

The system supports two execution modes:

**🤖 Real Mode**:
- Trigger: Voice commands containing "real" or "servo" keywords
- Function: Sends serial commands to the servo control board, controlling the actual robot movement
- Example: `"Real dance for 10 seconds"`, `"Servo execute action stand"`
- Output: Displays the sent hexadecimal serial command

**💻 Simulation Mode**:
- Trigger: Default mode, without "real" or "servo" keywords
- Function: Only displays the dance choreography process in the command line, does not control hardware
- Example: `"Dance for 10 seconds"`, `"Execute action stand"`
- Purpose: Testing algorithms, debugging choreography logic, demonstrating system functionality

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

## Technical Features

### 🎭 **Intelligent Dance System**
- **Music-Aware Selector**: Multi-dimensional music feature analysis (rhythm, energy, emotion, music structure)
- **Markov Chain Enhancement**: Intelligent action coherence optimization for more natural and smooth dance
- **Automatic Action Analysis**: Action library automatic feature extraction and classification
- **Modular Architecture**: Clear dance system module division, easy to expand

### 🎤 **Voice Interaction System**
- **Adaptive VAD**: Intelligent voice activity detection, automatically adapts to environmental noise
- **Multi-mode Recording**: Supports intelligent VAD, key control, fixed duration and other recording modes
- **Baidu API Integration**: High-precision speech recognition and natural speech synthesis

### 🔧 **System Design**
- **Modular Design**: Clear module division, easy to expand and maintain
- **Error Recovery**: Comprehensive error handling and automatic recovery mechanisms
- **Hardware Adaptation**: Automatic serial port detection and servo control board adaptation
- **Layered Control Architecture**: Intelligent algorithm layer + action mapping layer + hardware control layer
- **Action Library Management**: CSV mapping table manages servo control board pre-stored actions

## Troubleshooting

1. **Voice recognition inaccurate**
   - Adjust VAD sensitivity in configuration file
   - Check microphone connection and permissions
   - Ensure quiet environment for testing

2. **Servo not moving**
   - **Confirm using real mode commands**: Say "real execute action stand" instead of "execute action stand"
   - Check serial connection and permissions
   - Confirm servo control board is powered
   - Verify serial device path
   - **Check if actions are downloaded to servo control board**
   - **Confirm Seq numbers in 动作库.csv correspond to actions in control board**
   - First try "simulate dance for 5 seconds" to test if algorithm is normal

3. **Audio playback issues**
   - Check speaker connection
   - Adjust system volume settings
   - Verify audio device permissions

## Version Information

### v1.0 - First Release

**🎯 Core Functions:**
- 🎭 **Intelligent Dance System**: Modular architecture with integrated Markov chain intelligent selector
- 🎵 **Music-Driven Choreography**: Multi-dimensional feature analysis (rhythm, energy, emotion, structure)
- 🤖 **Action Library Management**: Automatic feature extraction and classification system
- 🎤 **Voice Interaction**: High-precision speech recognition and synthesis with Baidu API integration
- 🔧 **Hardware Control**: Servo control board serial communication and automatic detection

**🚀 Technical Highlights:**
- Music matching weight 70% + action coherence weight 30% fusion algorithm
- Support for real servo control and simulation test dual modes
- Adaptive VAD voice detection, supports complex environments

## License

This project is open source under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

If you have any questions or suggestions, please create an issue or contact the project maintainer.
