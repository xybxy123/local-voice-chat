import edge_tts
import asyncio
import os
import shutil
import subprocess
import wave
from contextlib import contextmanager

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pyaudio


_SELECTED_OUTPUT_DEVICE_NAME = None
_SELECTED_OUTPUT_ALSA_HW = None
_SELECTED_OUTPUT_DEVICE_INDEX = None


@contextmanager
def suppress_stderr():
    old_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(old_fd, 2)
        os.close(devnull)
        os.close(old_fd)


def list_output_devices():
    with suppress_stderr():
        p = pyaudio.PyAudio()

    devices = []
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxOutputChannels", 0) > 0:
                name = info.get("name", "")
                alsa_hw = None
                if "hw:" in name:
                    idx = name.find("hw:")
                    alsa_hw = name[idx:].split()[0].strip("()[]{}")

                devices.append({"index": i, "name": name, "alsa_hw": alsa_hw})
    finally:
        p.terminate()

    return devices


def set_output_device(device_index=None, device_name=None, alsa_hw=None):
    global _SELECTED_OUTPUT_DEVICE_INDEX, _SELECTED_OUTPUT_DEVICE_NAME, _SELECTED_OUTPUT_ALSA_HW
    _SELECTED_OUTPUT_DEVICE_INDEX = device_index
    _SELECTED_OUTPUT_DEVICE_NAME = device_name
    _SELECTED_OUTPUT_ALSA_HW = alsa_hw


def _get_output_device_info(device_index):
    if device_index is None:
        return None

    with suppress_stderr():
        p = pyaudio.PyAudio()

    try:
        return p.get_device_info_by_index(device_index)
    finally:
        p.terminate()


def _convert_mp3_to_wav(mp3_path, wav_path, target_rate=None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("系统未安装 ffmpeg，无法将语音文件转换为 wav。")

    command = [ffmpeg, "-y", "-loglevel", "error", "-i", mp3_path]
    if target_rate:
        command.extend(["-ar", str(int(target_rate))])
    command.append(wav_path)

    subprocess.run(
        command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def _play_wav_with_pyaudio(wav_path, device_index=None):
    with wave.open(wav_path, "rb") as wf:
        with suppress_stderr():
            p = pyaudio.PyAudio()

        try:
            stream_kwargs = {
                "format": p.get_format_from_width(wf.getsampwidth()),
                "channels": wf.getnchannels(),
                "rate": wf.getframerate(),
                "output": True,
                "frames_per_buffer": 1024,
            }
            if device_index is not None:
                stream_kwargs["output_device_index"] = device_index

            stream = p.open(**stream_kwargs)
            try:
                chunk = wf.readframes(1024)
                while chunk:
                    stream.write(chunk)
                    chunk = wf.readframes(1024)
            finally:
                stream.stop_stream()
                stream.close()
        finally:
            p.terminate()


async def _text_to_speech_and_play(text, voice="zh-CN-XiaoxiaoNeural"):
    output_file = "reply_audio.mp3"
    wav_file = "reply_audio.wav"
    output_device_info = _get_output_device_info(_SELECTED_OUTPUT_DEVICE_INDEX)
    target_rate = None
    if output_device_info is not None:
        target_rate = int(output_device_info.get("defaultSampleRate", 0)) or None

    # 1. 调用边缘 TTS，生成 mp3
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

    try:
        _convert_mp3_to_wav(output_file, wav_file, target_rate=target_rate)
        _play_wav_with_pyaudio(wav_file, _SELECTED_OUTPUT_DEVICE_INDEX)
    finally:
        for path in (output_file, wav_file):
            try:
                os.remove(path)
            except Exception:
                pass


def play_text_as_speech(text):
    if not text.strip():
        return

    print("[*] 正在播放语音...")
    try:
        asyncio.run(_text_to_speech_and_play(text))
    except Exception as e:
        print(f"[-] 语音播放失败: {e}")


if __name__ == "__main__":
    play_text_as_speech("你好，我是来帮你解答问题的。")
