import json
import os

# Định dạng chuẩn bị Dataset cho VLM (như LLaVA)
# Dữ liệu cần có hình ảnh đầu vào và chuỗi hội thoại (hỏi-đáp) bao gồm lập luận của AI.

def generate_sample_dataset():
    dataset = [
        {
            "id": "outfit_001",
            "image": "images/outfit_001.jpg", # Ảnh bao gồm cái áo và cái quần được phối chung
            "conversations": [
                {
                    "from": "human",
                    "value": "<image>\nTôi sắp đi dự tiệc cưới vào mùa đông, nhiệt độ khoảng 15 độ. Hãy gợi ý cho tôi từ những món đồ trong ảnh này."
                },
                {
                    "from": "gpt",
                    "value": "Dựa trên hoàn cảnh đi tiệc cưới (yêu cầu sự trang trọng) và thời tiết 15 độ (khá lạnh), tôi chọn kết hợp **Áo len cổ lọ màu trắng** và **Áo khoác dáng dài màu Be (Trench Coat)** để giữ ấm nhưng vẫn thanh lịch. Ở phần dưới, **Quần âu đen** sẽ làm bộ đồ trông nghiêm túc hơn. Sự kết hợp màu sắc Trắng - Be - Đen là xu hướng (trending) mang đậm phong cách Minimalist."
                }
            ]
        }
    ]
    
    os.makedirs("data", exist_ok=True)
    with open("data/fashion_vlm_dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print("Đã tạo mẫu Dataset đa phương thức tại: data/fashion_vlm_dataset.json")

if __name__ == "__main__":
    generate_sample_dataset()
    print("LƯU Ý: Trong thực tế, bạn cần khoảng vài ngàn đến hàng chục ngàn mẫu dữ liệu như thế này để AI học cách 'suy nghĩ'.")
