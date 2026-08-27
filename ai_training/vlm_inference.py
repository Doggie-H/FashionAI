import os
import sys
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from PIL import Image

try:
    from ai_training.fashion_philosophy import generate_dynamic_prompt
except ImportError:
    from fashion_philosophy import generate_dynamic_prompt

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

class VisionAgent:
    """
    Agent 1: Chỉ làm nhiệm vụ nhìn ảnh và miêu tả khách quan.
    (Model: HuggingFaceTB/SmolVLM-Instruct)
    """
    def __init__(self, model_id="HuggingFaceTB/SmolVLM-Instruct"):
        self.model_id = model_id
        self.processor = None
        self.model = None
        self.is_loaded = False
        
    def load_model(self):
        print(f"[*] Đang khởi tạo Vision Agent ({self.model_id})...")
        try:
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            self.is_loaded = True
            print("[*] Vision Agent sẵn sàng!")
        except Exception as e:
            print(f"[!] Lỗi Vision Agent: {e}")
            self.is_loaded = False

    def describe_image(self, image_path):
        if not self.is_loaded:
            return "Vision Agent chưa sẵn sàng."
        
        image = Image.open(image_path).convert("RGB")
        prompt_text = """Analyze this clothing item and return a valid JSON object (no markdown, no extra text) with EXACTLY these keys:
{
  "item_category": "type of item (e.g., Blazer, Sneakers, Dress)",
  "materials": "fabric/material (e.g., Leather, Tweed, Silk, Cotton)",
  "visual_tier": "estimated tier (e.g., Casual, High-end, Luxury, Streetwear, Vintage)",
  "base_style": "dominant style DNA (e.g., Y2K, Classic Chic, Techwear, Minimalism)",
  "key_details": "notable features like gold buttons, oversized fit, embroidery"
}"""
        
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=[image], return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        generated_ids = self.model.generate(**inputs, max_new_tokens=150, temperature=0.3)
        generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        
        response = generated_texts[0].split("Assistant:")[-1].strip()
        return response

    def detect_user_profile(self, image_path):
        if not self.is_loaded:
            return "{}"
            
        image = Image.open(image_path).convert("RGB")
        prompt_text = """Analyze the person in this image and return a valid JSON object (no markdown, no extra text) with EXACTLY these keys and choosing ONLY from the provided options. If you cannot see a feature clearly, make your best guess.
{
  "body_type": "Choose ONE: Dáng Quả Lê (hông to, vai nhỏ) / Dáng Quả Táo (tròn trịa, bụng to) / Dáng Đồng Hồ Cát / Dáng Chữ Nhật (ít đường cong) / Tam giác ngược (vai rộng, hông hẹp)",
  "skin_tone": "Choose ONE: Ngăm đen (Warm undertone) / Trắng sáng (Cool undertone) / Trung tính (Neutral) / Da Vàng (Olive/Asian)",
  "hair_type": "Choose ONE: Tóc ngắn cá tính / Tóc dài suôn mượt / Tóc xoăn bồng bềnh / Tóc nhuộm sáng",
  "face_shape": "Choose ONE: Mặt tròn / Mặt V-line / Mặt vuông góc cạnh / Mặt trái xoan",
  "body_proportions": "Choose ONE: Lưng dài chân ngắn / Chân dài lưng ngắn / Cân đối"
}"""
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=[image], return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        generated_ids = self.model.generate(**inputs, max_new_tokens=150, temperature=0.3)
        generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        
        response = generated_texts[0].split("Assistant:")[-1].strip()
        return response

class MasterStylistAgent:
    """
    Agent 2: Tư duy logic (Chain-of-Thought) bằng Text Model đã được Fine-tune.
    (Model: Qwen/Qwen2.5-0.5B-Instruct + trained_ai_stylist LoRA)
    """
    def __init__(self, model_id="Qwen/Qwen2.5-0.5B-Instruct", adapter_path="trained_ai_stylist"):
        self.model_id = model_id
        # Chắc chắn đường dẫn trỏ về đúng thư mục adapter ở root
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
        self.adapter_path = os.path.join(root_dir, adapter_path)
        self.tokenizer = None
        self.model = None
        self.is_loaded = False

    def load_model(self):
        print(f"[*] Đang khởi tạo Master Stylist Agent ({self.model_id})...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
            base_model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )
            
            if os.path.exists(self.adapter_path):
                print(f"[*] Nạp 'Bộ Não Triết Lý' (LoRA Adapter) từ: {self.adapter_path}")
                self.model = PeftModel.from_pretrained(base_model, self.adapter_path)
            else:
                print(f"[!] Không tìm thấy Adapter tại {self.adapter_path}, sử dụng não gốc.")
                self.model = base_model
                
            self.is_loaded = True
            print("[*] Master Stylist Agent sẵn sàng!")
        except Exception as e:
            print(f"[!] Lỗi Master Stylist Agent: {e}")
            self.is_loaded = False

    def get_advice(self, wardrobe_items, user_profile, selected_tags):
        if not self.is_loaded:
            return "Master Stylist chưa sẵn sàng."

        philosophy = generate_dynamic_prompt(user_profile, selected_tags)
        
        system_prompt = f"Bạn là một Giám đốc Sáng tạo (Master Stylist) thời trang. {philosophy}"
        
        wardrobe_json = "[\n" + ",\n".join(wardrobe_items) + "\n]" if wardrobe_items else "[]"

        user_message = f"""
Khách hàng có thông tin cơ thể như sau:
{user_profile}

Tình huống/Yêu cầu trang phục: {', '.join(selected_tags)}.

Tủ đồ của khách hàng hiện có các món sau (Định dạng JSON):
```json
{wardrobe_json}
```

Nhiệm vụ của bạn: Hãy suy luận từng bước (Chain-of-Thought). 
1. Phân tích ưu nhược điểm trên cơ thể khách hàng (dựa trên form dáng, skintone, tỉ lệ cơ thể).
2. Phân tích tình huống trang phục.
3. Từ tủ đồ hiện có, hãy chọn ra các món đồ ráp thành một Outfit hoàn chỉnh (ví dụ: Áo + Quần/Váy + Phụ kiện) sao cho khắc phục được nhược điểm cơ thể (như kéo dài chân nếu lưng dài, tôn dáng quả lê...). Nếu tủ đồ trống hoặc không có món phù hợp, hãy đưa ra gợi ý kiểu dáng chung chung.
4. Trình bày bằng tiếng Việt tự nhiên, chuyên sâu như một chuyên gia thời trang thực thụ.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        print("[*] Master Stylist đang lập luận...")
        outputs = self.model.generate(
            **inputs, 
            max_new_tokens=400, 
            temperature=0.8,
            top_p=0.9,
            repetition_penalty=1.1
        )
        
        response = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        return response

class MasterStylistPipeline:
    def __init__(self):
        if os.getenv("VISION_MODEL_BACKEND", "smolvlm").lower() == "qwen25vl":
            from ai_training.qwen_vl_adapter import Qwen25VLAdapter
            self.vision_agent = Qwen25VLAdapter()
        else:
            self.vision_agent = VisionAgent()
        self.master_agent = MasterStylistAgent()
        self.is_loaded = False
        
    def load_model(self):
        self.vision_agent.load_model()
        self.master_agent.load_model()
        if self.vision_agent.is_loaded and self.master_agent.is_loaded:
            self.is_loaded = True
            print("\n[+] ĐÃ KẾT NỐI DUAL-AGENT ARCHITECTURE THÀNH CÔNG!\n")
            
    def get_style_advice(self, image_path, selected_tags, user_profile=None):
        """Generate advice from a single uploaded clothing image."""
        if not self.is_loaded:
            return "Hệ thống AI chưa sẵn sàng."
        visual_desc = self.vision_agent.describe_image(image_path)
        return self.get_wardrobe_advice([visual_desc], selected_tags, user_profile)

    def get_measurement_advice(self, measurements, selected_tags):
        """Generate advice from structured body measurements without requiring an image."""
        return self.get_wardrobe_advice([], selected_tags, measurements)

    def get_wardrobe_advice(self, wardrobe_items, selected_tags, user_profile=None):
        if not self.is_loaded:
            return "Hệ thống AI chưa sẵn sàng."
            
        print(f"\n--- [Bước 2: Master Stylist Lập Luận Từ Tủ Đồ] ---")
        advice = self.master_agent.get_advice(wardrobe_items, user_profile, selected_tags)
        return advice

    def auto_detect_profile(self, image_path):
        if not self.is_loaded:
            return "{}"
        
        print(f"\n--- [Auto-Detect: Vision Agent Quét Người Dùng] ---")
        profile_json_str = self.vision_agent.detect_user_profile(image_path)
        print(f"Vision Agent trả về: {profile_json_str}")
        return profile_json_str

# Giữ lại Alias để các module cũ vẫn hoạt động mà không bị crash
AIStylistVLM = MasterStylistPipeline

if __name__ == "__main__":
    pipeline = MasterStylistPipeline()
    pipeline.load_model()
    
    test_image = "data/images/outfit_0000.jpg"
    test_tags = ["Hẹn hò", "Nổi bật", "Cá tính"]
    test_profile = {
        "body_type": "Dáng quả lê (hông to, vai nhỏ)",
        "skin_tone": "Ngăm đen (Warm undertone)",
        "hair_type": "Tóc xoăn xù tự nhiên",
        "face_shape": "Mặt tròn",
        "body_proportions": "Lưng dài chân ngắn"
    }
    
    if os.path.exists(test_image):
        visual_desc = pipeline.vision_agent.describe_image(test_image)
        advice = pipeline.get_wardrobe_advice([visual_desc], test_tags, test_profile)
        print("\n" + "="*50)
        print("👑 MASTER AI STYLIST TƯ VẤN (TỪ TỦ ĐỒ):")
        print("="*50)
        print(advice)
        print("="*50)
    else:
        print(f"[!] Không tìm thấy ảnh test '{test_image}'. Hãy tạo ảnh trước.")
