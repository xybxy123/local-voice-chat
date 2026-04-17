import os
import logging

os.environ.setdefault("MODELSCOPE_LOG_LEVEL", "40")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.utils import logging as hf_logging
from modelscope import snapshot_download

MODEL_ID = "qwen/Qwen2.5-0.5B-Instruct"
QWEN_LOCAL_DIR = os.path.join(
    os.path.dirname(__file__), "models", "qwen2_5_0_5b_instruct"
)

logging.getLogger("modelscope").setLevel(logging.ERROR)
hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()

print(f"[*] 正在加载本地 AI 模型 (优先本地目录: {QWEN_LOCAL_DIR})...")
try:
    model_dir = (
        QWEN_LOCAL_DIR if os.path.isdir(QWEN_LOCAL_DIR) else snapshot_download(MODEL_ID)
    )

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        torch_dtype="auto",
        device_map="auto",
    )
    print("[*] 本地模型加载完成！")
except Exception as e:
    print(f"[-] 模型加载失败: {e}")
    tokenizer = None
    model = None


def chat_with_ai(prompt):
    if not prompt.strip():
        print("[-] 未检测到输入文字，跳过 AI 对话。")
        return ""
    if tokenizer is None or model is None:
        print("[-] AI模型未成功加载，无法生成回复。")
        return ""

    try:
        print("[*] 正在生成回复...")
        messages = [
            {
                "role": "system",
                "content": "你是一个非常有用的AI助手。请根据用户的输入做出简洁的中文回答。",
            },
            {"role": "user", "content": prompt},
        ]

        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )

        generated_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        reply = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        print("\n================ 本地 AI 回复 ================")
        print(reply)
        print("=============================================\n")
        return reply

    except Exception as e:
        print(f"[-] 本地 AI 生成回复失败: {e}")
        return str(e)


if __name__ == "__main__":
    pass
