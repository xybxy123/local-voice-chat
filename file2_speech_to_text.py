import os
import logging
import re
from contextlib import contextmanager

os.environ.setdefault("MODELSCOPE_LOG_LEVEL", "40")
os.environ.setdefault("FUNASR_DISABLE_UPDATE", "True")

from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks


@contextmanager
def suppress_stderr_stdout():
    old_err = os.dup(2)
    old_out = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        os.dup2(devnull, 1)
        yield
    finally:
        os.dup2(old_err, 2)
        os.dup2(old_out, 1)
        os.close(devnull)
        os.close(old_err)
        os.close(old_out)


ASR_MODEL_ID = "iic/SenseVoiceSmall"
ASR_LOCAL_DIR = os.path.join(
    os.path.dirname(__file__), "models", "asr_sensevoice_small"
)

logging.getLogger("modelscope").setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

print(f"[*] 正在加载 ASR 模型 (优先本地目录: {ASR_LOCAL_DIR})...")
try:
    asr_model_source = ASR_LOCAL_DIR if os.path.isdir(ASR_LOCAL_DIR) else ASR_MODEL_ID
    with suppress_stderr_stdout():
        asr_pipeline = pipeline(
            task=Tasks.auto_speech_recognition,
            model=asr_model_source,
        )
    print("[*] 本地 ASR 模型加载完成！")
except Exception as e:
    print(f"[-] 本地 ASR 模型加载失败: {e}")
    asr_pipeline = None


def audio_to_text(audio_file_path):
    if asr_pipeline is None:
        print("[-] ASR 模型未成功加载，无法进行语音识别。")
        return ""

    try:
        print("[*] 正在调用本地 ASR 模型转写...")
        with suppress_stderr_stdout():
            result = asr_pipeline(audio_file_path)
        text = ""
        if isinstance(result, dict):
            text = str(result.get("text", "")).strip()
        elif isinstance(result, list) and len(result) > 0:
            first = result[0]
            if isinstance(first, dict):
                text = str(first.get("text", "")).strip()
        elif isinstance(result, str):
            text = result.strip()

        text = re.sub(r"<\|[^|]+\|>", "", text).strip()

        if text:
            print(f"[+] 识别结果: {text}")
            return text

        print("[-] 未识别到有效文字。")
        return ""
    except Exception as e:
        print(f"[-] 本地 ASR 识别失败: {e}")
        return ""


if __name__ == "__main__":
    pass
