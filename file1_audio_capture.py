import os
import audioop
import time
from collections import deque
from contextlib import contextmanager

os.environ.setdefault("JACK_NO_START_SERVER", "1")

import pyaudio
import wave

from ctypes import *

try:
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

    def py_error_handler(filename, line, function, err, fmt):
        pass

    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = cdll.LoadLibrary("libasound.so.2")
    asound.snd_lib_error_set_handler(c_error_handler)
except Exception:
    pass


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


def list_input_devices():
    with suppress_stderr():
        p = pyaudio.PyAudio()

    info = p.get_host_api_info_by_index(0)
    numdevices = info.get("deviceCount")

    devices = []
    for i in range(0, numdevices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        if device_info.get("maxInputChannels") > 0:
            devices.append({"index": i, "name": device_info.get("name")})
    p.terminate()
    return devices


def record_audio(
    output_filename="output.wav",
    device_index=None,
    duration=None,
    rate=16000,
    chunk=1024,
    volume_threshold=700,
    silence_duration=1.0,
    max_duration=15.0,
    print_volume=True,
    volume_print_interval=0.08,
):
    with suppress_stderr():
        p = pyaudio.PyAudio()

    format = pyaudio.paInt16
    channels = 1

    stream = None
    actual_rate = rate
    for r in [rate, 44100, 48000]:
        try:
            with suppress_stderr():
                stream = p.open(
                    format=format,
                    channels=channels,
                    rate=r,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=chunk,
                )
            actual_rate = r
            break
        except Exception:
            continue

    if stream is None:
        print("[-] 录音失败: 无法打开音频流，此设备可能不支持标准采样率。")
        p.terminate()
        return None

    chunk_seconds = chunk / actual_rate
    print(
        f"[*] 开始录音... (阈值模式, threshold={volume_threshold}, 最大 {max_duration} 秒, {actual_rate}Hz)"
    )

    frames = []

    if duration is not None:
        for _ in range(0, int(actual_rate / chunk * duration)):
            try:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
            except OSError as e:
                print(f"[-] 读取音频帧时略过错误: {e}")
    else:
        pre_roll = deque(maxlen=max(1, int(0.2 / chunk_seconds)))
        silence_chunks_limit = max(1, int(silence_duration / chunk_seconds))
        max_chunks = max(1, int(max_duration / chunk_seconds))

        started = False
        silence_chunks = 0
        last_print_time = 0.0

        for _ in range(max_chunks):
            try:
                data = stream.read(chunk, exception_on_overflow=False)
            except OSError as e:
                print(f"[-] 读取音频帧时略过错误: {e}")
                continue

            rms = audioop.rms(data, 2)

            if print_volume:
                now = time.monotonic()
                if now - last_print_time >= volume_print_interval:
                    level = min(50, int(rms / 70))
                    bar = "#" * level + "-" * (50 - level)
                    state = "REC" if started else "WAIT"
                    mark = "*" if rms >= volume_threshold else " "
                    print(
                        f"\r[音量监控] {state} RMS={rms:4d} 阈值={volume_threshold:4d}{mark} [{bar}]",
                        end="",
                        flush=True,
                    )
                    last_print_time = now

            if not started:
                pre_roll.append(data)
                if rms >= volume_threshold:
                    started = True
                    frames.extend(pre_roll)
                    silence_chunks = 0
                continue

            frames.append(data)

            if rms < volume_threshold:
                silence_chunks += 1
                if silence_chunks >= silence_chunks_limit:
                    break
            else:
                silence_chunks = 0

        if not started:
            if print_volume:
                print()
            print("[-] 未检测到达到阈值的语音，跳过本轮录音。")
            stream.stop_stream()
            stream.close()
            p.terminate()
            return None

    if print_volume:
        print()

    print("[*] 录音结束.")
    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(output_filename, "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(format))
    wf.setframerate(actual_rate)
    wf.writeframes(b"".join(frames))
    wf.close()

    return output_filename


if __name__ == "__main__":
    devs = list_input_devices()
    for d in devs:
        print(f"Index {d['index']}: {d['name']}")
