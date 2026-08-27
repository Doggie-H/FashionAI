import sys
import json
import os
import random

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def generate_vlm_dialogue(metadata):
    """Sinh ra đoạn hội thoại tư vấn thời trang dựa trên metadata của ảnh"""
    
    # Metadata gồm: gender, masterCategory, subCategory, articleType, baseColour, season, usage, productDisplayName
    
    # Lấy thông tin thuộc tính đóng vai trò là "Tags" người dùng chọn
    season_tag = metadata.get("season", "All Seasons")
    usage_tag = metadata.get("usage", "Casual")
    gender_tag = metadata.get("gender", "Unisex")
    color_tag = metadata.get("baseColour", "Multicolor")
    
    # Ở phần mềm (UI), user sẽ click các button Tags.
    # Ta sẽ ghép nó thành một Prompt có cấu trúc dưới nền cho AI.
    selected_tags = f"[{season_tag}], [{usage_tag}], [{gender_tag}], [{color_tag}]"
    
    system_prompt = f"<image>\nNgười dùng đã chọn các Tags nhu cầu sau: {selected_tags}. Dựa vào hình ảnh món đồ này, hãy đánh giá sự phù hợp và tư vấn phong cách."
    
    name = metadata.get("productDisplayName", "Sản phẩm")
    answer = f"Dựa trên các tags bạn đã chọn ({selected_tags}), món đồ **{name}** trong ảnh cực kỳ phù hợp."
    answer += f" Thiết kế mang phong cách {usage_tag.lower()} dành cho {gender_tag.lower()}, kết hợp với tone màu {color_tag.lower()}."
    answer += f" Đặc biệt nó được thiết kế tối ưu cho mùa {season_tag.lower()}."
    answer += " Lời khuyên: Bạn có thể phối thêm phụ kiện đơn giản để tôn lên phong cách tổng thể."
    
    return {
        "id": metadata["id"],
        "image": metadata["image_path"],
        "conversations": [
            {
                "from": "user",
                "value": system_prompt
            },
            {
                "from": "assistant",
                "value": answer
            }
        ]
    }

def build_dataset(metadata_path="data/fashion_metadata.json", output_path="data/vlm_training_data.json"):
    print(f"[*] Bắt đầu xử lý dán nhãn tự động từ file metadata: {metadata_path}...")
    
    if not os.path.exists(metadata_path):
        print(f"[!] Không tìm thấy file {metadata_path}")
        return
        
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)
        
    vlm_dataset = []
    for item in metadata_list:
        dialogue = generate_vlm_dialogue(item)
        vlm_dataset.append(dialogue)
        
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vlm_dataset, f, ensure_ascii=False, indent=4)
        
    print(f"[*] HOÀN TẤT! Đã tạo thành công {len(vlm_dataset)} mẫu dữ liệu VLM tại '{output_path}'.")

if __name__ == "__main__":
    build_dataset()
