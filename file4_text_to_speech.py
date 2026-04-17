import edge_tts
import asyncio
import os
import re
import shutil
import subprocess
import time
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


def _split_text_for_tts(text, max_len=80):
    normalized = " ".join(text.split())
    if not normalized:
        return []

    parts = re.split(r"(?<=[。！？!?；;，,])", normalized)
    parts = [p.strip() for p in parts if p and p.strip()]

    chunks = []
    buffer = ""
    for part in parts:
        if len(part) > max_len:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            start = 0
            while start < len(part):
                chunks.append(part[start : start + max_len])
                start += max_len
            continue

        if not buffer:
            buffer = part
            continue

        if len(buffer) + len(part) <= max_len:
            buffer += part
        else:
            chunks.append(buffer)
            buffer = part

    if buffer:
        chunks.append(buffer)

    return chunks


async def _synthesize_to_mp3(text, voice, rate, output_file):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_file)


async def _synthesize_to_mp3_with_retry(
    text, voice, rate, output_file, retries=3, base_delay=0.5
):
    last_error = None
    for attempt in range(retries):
        try:
            await _synthesize_to_mp3(text, voice, rate, output_file)
            return
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                await asyncio.sleep(base_delay * (2**attempt))
    raise last_error


def _play_text_with_espeak(text):
    cmd = shutil.which("espeak-ng") or shutil.which("espeak")
    if not cmd:
        raise RuntimeError("未找到 espeak-ng/espeak，无法使用离线语音兜底。")

    subprocess.run(
        [cmd, "-v", "zh", "-s", "210", text],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _resolve_preferred_rate(device_index):
    with suppress_stderr():
        p = pyaudio.PyAudio()

    try:
        if device_index is not None:
            info = p.get_device_info_by_index(device_index)
            return int(info.get("defaultSampleRate", 0)) or None

        info = p.get_default_output_device_info()
        return int(info.get("defaultSampleRate", 0)) or None
    except Exception:
        return None
    finally:
        p.terminate()


def _iter_candidate_rates(preferred_rate):
    rates = [preferred_rate, 48000, 44100, 24000, 22050, 16000]
    seen = set()
    for rate in rates:
        if not rate or rate in seen:
            continue
        seen.add(rate)
        yield int(rate)


def _play_mp3_with_ffmpeg_stream(mp3_path, device_index=None, preferred_rate=None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("系统未安装 ffmpeg，无法播放语音。")

    last_error = None
    for sample_rate in _iter_candidate_rates(preferred_rate):
        process = None
        stream = None
        p = None
        try:
            with suppress_stderr():
                p = pyaudio.PyAudio()

            stream_kwargs = {
                "format": pyaudio.paInt16,
                "channels": 1,
                "rate": sample_rate,
                "output": True,
                "frames_per_buffer": 4096,
            }
            if device_index is not None:
                stream_kwargs["output_device_index"] = device_index

            stream = p.open(**stream_kwargs)

            command = [
                ffmpeg,
                "-loglevel",
                "error",
                "-i",
                mp3_path,
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-",
            ]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                stream.write(chunk)

            process.wait()
            if process.returncode != 0:
                raise RuntimeError("ffmpeg 解码失败")

            return
        except Exception as e:
            last_error = e
            continue
        finally:
            if process and process.poll() is None:
                process.kill()
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p is not None:
                p.terminate()

    if last_error is not None:
        raise last_error
    raise RuntimeError("未找到可用采样率，语音播放失败")


async def _text_to_speech_and_play(text, voice="zh-CN-XiaoxiaoNeural", rate="+35%"):
    chunks = _split_text_for_tts(text, max_len=80)
    if not chunks:
        return

    preferred_rate = _resolve_preferred_rate(_SELECTED_OUTPUT_DEVICE_INDEX)
    temp_files = []
    temp_prefix = f"reply_audio_{os.getpid()}_{int(time.time() * 1000)}"

    current_path = f"/tmp/{temp_prefix}_0.mp3"
    temp_files.append(current_path)
    await _synthesize_to_mp3_with_retry(chunks[0], voice, rate, current_path)

    next_task = None
    next_path = None

    if len(chunks) > 1:
        next_path = f"/tmp/{temp_prefix}_1.mp3"
        temp_files.append(next_path)
        next_task = asyncio.create_task(
            _synthesize_to_mp3_with_retry(chunks[1], voice, rate, next_path)
        )

    try:
        for i in range(len(chunks)):
            await asyncio.to_thread(
                _play_mp3_with_ffmpeg_stream,
                current_path,
                _SELECTED_OUTPUT_DEVICE_INDEX,
                preferred_rate,
            )

            if next_task is None:
                continue

            await next_task
            current_path = next_path

            if i + 2 < len(chunks):
                next_path = f"/tmp/{temp_prefix}_{i + 2}.mp3"
                temp_files.append(next_path)
                next_task = asyncio.create_task(
                    _synthesize_to_mp3_with_retry(chunks[i + 2], voice, rate, next_path)
                )
            else:
                next_task = None
                next_path = None
    finally:
        for path in temp_files:
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
        print(f"[-] 在线语音失败，尝试离线语音: {e}")
        try:
            _play_text_with_espeak(text)
        except Exception as offline_err:
            print(f"[-] 语音播放失败: {offline_err}")


if __name__ == "__main__":
    play_text_as_speech("你好，我是来帮你解答问题的。")
