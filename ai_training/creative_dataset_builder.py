import json
import random
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# CÁC BIẾN SỐ NHƯ CŨ
WEATHER = ["Nắng ấm", "Mưa nhỏ", "Se lạnh"]
PURPOSES = ["Đi làm", "Hẹn hò", "Dạo phố"]
BODY_TYPES = ["Cao gầy", "Petite", "Đậm người"]

# BIẾN SỐ MỚI: TƯ DUY SÁNG TẠO (FASHION RISK & INNOVATION)
# Dạy AI cách phá vỡ quy tắc để tạo ra sự "Đổi mới mỗi ngày"
CREATIVE_LEVELS = [
    {"level": "Safe (An toàn)", "instruction": "Cần một bộ đồ an toàn, chuẩn mực."},
    {"level": "Trendy (Bắt trend)", "instruction": "Muốn bắt kịp xu hướng mới nhất, có điểm nhấn."},
    {"level": "Rule-breaking (Phá vỡ quy tắc)", "instruction": "Hôm nay tôi muốn phá cách, thoát khỏi vùng an toàn, không muốn giống ai!"}
]

# THỦ THUẬT PHÁ CÁCH CỦA AI STYLIST
HACKS = [
    "Color-blocking (Phối các màu đối lập mạnh như Cam - Xanh biển).",
    "Unexpected Layering (Mặc váy bên ngoài quần dài - xu hướng Y2K).",
    "Gender-fluid (Sử dụng cà vạt nam cho váy nữ hoặc mặc áo blazer nam quá khổ).",
    "High-Low Mix (Mix áo khoác dạ Tweed sang trọng với quần Jeans rách bụi bặm).",
    "Sneaker Suit (Mặc Suit công sở nhưng đi giày Sneaker hầm hố thay vì giày da)."
]

def generate_creative_reasoning(num_samples=1500):
    print(">>> Đang sinh bộ dữ liệu CREATIVE: Dạy AI tư duy Sáng tạo & Phá vỡ quy tắc...")
    dataset = []
    
    for _ in range(num_samples):
        w, p, b = random.choice(WEATHER), random.choice(PURPOSES), random.choice(BODY_TYPES)
        creativity = random.choice(CREATIVE_LEVELS)
        
        user_prompt = (
            f"Thời tiết {w}, tôi đi {p}, dáng {b}. \n"
            f"Yêu cầu đặc biệt: {creativity['instruction']} Hãy mix đồ cho tôi."
        )
        
        think_steps = [
            f"- Phân tích cơ bản: {w}, {p}, {b} -> Khung trang phục (Base outfit) đã được định hình."
        ]
        
        if creativity["level"] == "Safe (An toàn)":
            think_steps.append("- Tư duy Sáng tạo: User muốn an toàn -> Áp dụng đúng chuẩn mực kinh điển (Classic rules). Không rủi ro.")
            conclusion = "Phong cách Minimalist / Office chuẩn mực. Quần âu và Áo sơ mi tone màu trung tính."
            
        elif creativity["level"] == "Trendy (Bắt trend)":
            think_steps.append("- Tư duy Sáng tạo: User muốn điểm nhấn -> Giữ 80% an toàn, thêm 20% phụ kiện Trendy (Vòng cổ chokers, túi xách màu nổi).")
            conclusion = "Base outfit tối giản nhưng kết hợp với một chiếc túi xách màu Đỏ Cherry (màu hot trend) để làm bừng sáng tổng thể."
            
        else: # Rule-breaking
            hack = random.choice(HACKS)
            think_steps.append(f"- Tư duy Sáng tạo: User MUỐN PHÁ CÁCH! Gạt bỏ các luật lệ thông thường.")
            think_steps.append(f"- Quyết định bẻ lái (Plot twist): Thay vì đi {p} mặc đồ nhàm chán, ta sẽ áp dụng kỹ thuật '{hack}'.")
            conclusion = f"Hôm nay chúng ta sẽ chơi trội bằng kỹ thuật: **{hack}**. Sự bất cân xứng này chính là đỉnh cao của thời trang!"

        ai_response = (
            f"<think>\n" + "\n".join(think_steps) + "\n</think>\n"
            f"Đã nhận yêu cầu! Dưới đây là gợi ý từ Stylist của bạn:\n\n"
            f"🔥 **Ý tưởng Mix & Match:** {conclusion}\n"
            f"Thời trang là không giới hạn. Bộ trang phục này sẽ đảm bảo bạn luôn mới mẻ và không bao giờ bị lặp lại ngày hôm qua!"
        )
        
        dataset.append({"instruction": user_prompt, "output": ai_response})
        
    json_path = DATA_DIR / "creative_context_dataset.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print(f"Đã sinh thành công {num_samples} kịch bản CREATIVE tại: {json_path}")

if __name__ == "__main__":
    generate_creative_reasoning(1500)
    print("\n=== AI ĐÃ HỌC ĐƯỢC CÁCH TRỞ THÀNH MỘT NGHỆ SĨ THỜI TRANG (RULE-BREAKER) ===")
