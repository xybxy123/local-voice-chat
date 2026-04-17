from file1_audio_capture import list_input_devices, record_audio
from file2_speech_to_text import audio_to_text
from file3_ai_chat import chat_with_ai
from file4_text_to_speech import (
    list_output_devices,
    set_output_device,
    play_text_as_speech,
)
import os


def main():
    print("===== AI 语音对话项目 =====")

    print("\n[步骤 0: 选择语音输出设备]")
    out_devices = list_output_devices()
    print("可用播放设备列表:")
    for dev in out_devices:
        alsa = f" | {dev['alsa_hw']}" if dev.get("alsa_hw") else ""
        print(f"  [{dev['index']}] {dev['name']}{alsa}")

    output_idx_input = input("\n请选择播放设备序号 (直接回车将使用系统默认设备): ")
    if output_idx_input.isdigit():
        target_index = int(output_idx_input)
        selected = next((d for d in out_devices if d["index"] == target_index), None)
        if selected:
            set_output_device(
                selected["index"], selected["name"], selected.get("alsa_hw")
            )
            extra = f" ({selected['alsa_hw']})" if selected.get("alsa_hw") else ""
            print(f"[*] 已选择播放设备: {selected['name']}{extra}")
        else:
            print("[-] 播放设备序号无效，将使用默认设备。")

    print("\n[步骤 1: 声音采集]")
    devices = list_input_devices()
    print("可用录音设备列表:")
    for dev in devices:
        print(f"  [{dev['index']}] {dev['name']}")

    device_idx_input = input("\n请选择输入设备序号 (直接回车将使用系统默认设备): ")
    device_idx = int(device_idx_input) if device_idx_input.isdigit() else None

    while True:
        audio_file = "temp_record.wav"
        record_audio(output_filename=audio_file, device_index=device_idx, duration=5)

        if not os.path.exists(audio_file):
            print("[-] 录音失败未能生成文件，程序退出。")
            return

        print("\n[步骤 2: 音频解码与文字识别]")
        text = audio_to_text(audio_file)

        print("\n[步骤 3: 请求 AI 大模型]")
        if text:
            if text.strip().lower() in {"退出", "结束", "停止", "quit", "exit", "q"}:
                print("[*] 检测到退出指令，结束对话。")
                break
            reply = chat_with_ai(text)
            if reply:
                play_text_as_speech(reply)
        else:
            print("[-] 语音转文字为空，无法发送对话。")

        user_choice = input("\n继续对话请回车，输入 q 退出: ").strip().lower()
        if user_choice in {"q", "quit", "exit", "n", "no"}:
            print("[*] 对话已结束。")
            break


if __name__ == "__main__":
    main()
