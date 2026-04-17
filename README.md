# AI 语音对话项目

一个本地语音对话 Demo：
- 麦克风录音
- 本地 ASR 语音识别（SenseVoiceSmall）
- 本地大模型回复（Qwen2.5-0.5B-Instruct）
- TTS 语音播报回复（Edge TTS + PyAudio）

## 目录结构

- main.py: 项目入口
- file1_audio_capture.py: 录音与输入设备枚举
- file2_speech_to_text.py: 语音转文字
- file3_ai_chat.py: 大模型对话
- file4_text_to_speech.py: 文本转语音与播放
- models/asr_sensevoice_small: 本地 ASR 模型目录
- models/qwen2_5_0_5b_instruct: 本地 LLM 模型目录

## 环境要求

- Linux
- Python 3.10+
- 系统工具: ffmpeg
- 音频库依赖: PortAudio（PyAudio 依赖）

Ubuntu 可参考：

```bash
sudo apt update
sudo apt install -y ffmpeg portaudio19-dev
```

## 安装依赖

在 cy 目录执行：

```bash
pip install -r requirements.txt
```

## 运行项目

在 cy 目录执行：

```bash
python main.py
```

运行后按提示：
1. 选择语音输出设备
2. 选择录音输入设备
3. 说话进行识别与对话
4. 输入 q 退出
