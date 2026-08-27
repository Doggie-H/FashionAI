import os
import sys

# FIX CUDA MISMATCH for bitsandbytes
os.environ["BNB_CUDA_VERSION"] = "130"

# FIX: Import datasets before torch to prevent silent DLL crash on Windows
from datasets import Dataset
import torch
import json
# Cấu hình UTF-8 cho Windows Terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig

# Cấu hình đường dẫn
DATA_PATHS = [
    "data/master_fashion_dataset.json",
    "data/creative_context_dataset.json",
    "data/ultimate_context_dataset.json"
]
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"  # Model nhỏ chạy được trên Local để test
OUTPUT_DIR = "trained_ai_stylist"

def load_and_prep_data():
    """Tải dữ liệu huấn luyện từ JSON và chuyển thành chuẩn HuggingFace Dataset"""
    all_items = []
    for path in DATA_PATHS:
        if os.path.exists(path):
            print(f"[*] Đang đọc dữ liệu từ: {path}...")
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
                all_items.extend(items)
                print(f"    -> Đã đọc {len(items)} mẫu.")
    
    if not all_items:
        raise FileNotFoundError("Không tìm thấy file dataset nào trong thư mục data/")

    # Định dạng lại dữ liệu thành các đoạn Chat (ChatML format)
    formatted_data = {"text": []}
    for item in all_items:
        # Prompt chuẩn để dạy AI đóng vai Stylist
        text = (
            "<|im_start|>system\nBạn là một Chuyên gia Thời trang (AI Stylist). "
            "Hãy lập luận cẩn thận trước khi tư vấn.<|im_end|>\n"
            f"<|im_start|>user\n{item['instruction']}<|im_end|>\n"
            f"<|im_start|>assistant\n{item['output']}<|im_end|>"
        )
        formatted_data["text"].append(text)
        
    dataset = Dataset.from_dict(formatted_data)
    print(f"[*] Đã tải thành công tổng cộng {len(dataset)} mẫu huấn luyện.")
    return dataset

def train_model(epochs=2):
    print(f"[*] Đang tải Tokenizer và Model: {MODEL_NAME}...")
    # Tải Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device_map = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Thiết bị huấn luyện (Device): {device_map.upper()}")
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map=device_map,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    model.config.use_cache = False

    # 1. Cấu hình LoRA sâu rộng
    print("[*] Áp dụng kỹ thuật LoRA (Low-Rank Adaptation)...")
    lora_config = LoraConfig(
        r=16, 
        lora_alpha=32, 
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], # Học toàn bộ Attention Projection
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters() # In ra số lượng tham số thực tế cần học

    # 2. Chuẩn bị Dữ liệu
    dataset = load_and_prep_data()
    # Tách tập train (95%) và eval (5%)
    split_dataset = dataset.train_test_split(test_size=0.05)

    # 3. Cấu hình Training chuyên sâu
    print("[*] Cấu hình SFTConfig...")
    training_args = SFTConfig(
        dataset_text_field="text",
        max_length=512,
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.01,
        num_train_epochs=epochs,
        logging_steps=20,
        save_strategy="epoch",
        eval_strategy="no",
        use_cpu=not torch.cuda.is_available(),
        bf16=False,
        fp16=torch.cuda.is_available(),
        optim="adamw_torch",
        report_to="none"
    )

    # 4. Khởi tạo SFTTrainer
    print("[*] BẮT ĐẦU HUẤN LUYỆN AI (TRAINING)...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=split_dataset["train"],
        eval_dataset=split_dataset["test"],
        processing_class=tokenizer,
        args=training_args,
    )

    # 5. Chạy Train
    trainer.train()

    # 6. Lưu Model hoàn thiện
    print(f"[*] Đang lưu Model vào thư mục {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("[*] HOÀN TẤT! BẠN ĐÃ HUẤN LUYỆN XONG AI STYLIST CỦA RIÊNG MÌNH.")

if __name__ == "__main__":
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    train_model(epochs=epochs)
