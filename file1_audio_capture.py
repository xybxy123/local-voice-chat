import os
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
    output_filename="output.wav", device_index=None, duration=5, rate=16000, chunk=1024
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

    print(f"[*] 开始录音... (大约 {duration} 秒, {actual_rate}Hz)")
    frames = []
    for _ in range(0, int(actual_rate / chunk * duration)):
        try:
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)
        except OSError as e:
            print(f"[-] 读取音频帧时略过错误: {e}")

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
