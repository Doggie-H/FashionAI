import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Cấu hình UTF-8 cho Windows Terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Tự động tìm thư mục model
if os.path.exists("trained_ai_stylist"):
    MODEL_PATH = "trained_ai_stylist"
elif os.path.exists("ai_training/trained_ai_stylist"):
    MODEL_PATH = "ai_training/trained_ai_stylist"
else:
    MODEL_PATH = "trained_ai_stylist"

print("=============================================")
print("🤖 ĐANG TẢI AI STYLIST CỦA RIÊNG BẠN...")
print(f"[*] Thư mục model: {MODEL_PATH}")
print("=============================================")

# Kiểm tra thư mục model
if not os.path.exists(MODEL_PATH):
    print(f"[!] Lỗi: Không tìm thấy thư mục '{MODEL_PATH}'. Bạn đã huấn luyện AI chưa?")
    sys.exit(1)

# Tải Tokenizer và Model
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
except Exception:
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")

device_map = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if torch.cuda.is_available() else torch.float32

if os.path.exists(os.path.join(MODEL_PATH, "adapter_config.json")):
    from peft import PeftModel
    base_model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-0.5B-Instruct",
        device_map=device_map,
        torch_dtype=dtype
    )
    model = PeftModel.from_pretrained(base_model, MODEL_PATH)
else:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, 
        device_map=device_map,
        torch_dtype=dtype
    )

print("\n✅ AI STYLIST ĐÃ SẴN SÀNG!")
print("Hãy nhập câu hỏi về thời trang (Nhập 'thoát' để dừng).")
print("---------------------------------------------\n")

while True:
    try:
        user_input = input("\n👤 Bạn: ")
        if user_input.lower() in ["thoát", "exit", "quit"]:
            print("Tạm biệt!")
            break
            
        if not user_input.strip():
            continue
            
        # Đưa vào template của Qwen
        prompt = (
            "<|im_start|>system\nBạn là một Chuyên gia Thời trang (AI Stylist). "
            "Hãy lập luận cẩn thận trước khi tư vấn.<|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Sinh câu trả lời
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id
        )
        
        # Cắt bỏ phần prompt ra khỏi câu trả lời
        response_len = inputs["input_ids"].shape[1]
        response = tokenizer.decode(outputs[0][response_len:], skip_special_tokens=True)
        
        print(f"\n✨ AI Stylist: {response}")
        
    except KeyboardInterrupt:
        print("\nTạm biệt!")
        break
    except Exception as e:
        print(f"\n[!] Đã xảy ra lỗi: {str(e)}")
