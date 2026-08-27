import json
import random
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# BIẾN SỐ NGỮ CẢNH CƠ BẢN
WEATHER = ["Nắng nóng 38 độ", "Mưa phùn ẩm ướt", "Se lạnh mùa thu 20 độ", "Rét đậm dưới 10 độ", "Trời nhiều gió", "Thời tiết mát mẻ 25 độ"]
LOCATIONS = ["Quán Cafe Acoustic", "Văn phòng tập đoàn", "Văn phòng Startup", "Quán Bar/Pub", "Công viên dã ngoại", "Trung tâm thương mại", "Biển", "Nhà hàng Fine-Dining", "Đà Lạt", "Đám cưới ngoài trời"]
PURPOSES = ["Đi làm bình thường", "Phỏng vấn xin việc", "Gặp đối tác cấp cao", "Hẹn hò lần đầu", "Đi chơi với người yêu cũ", "Đi quẩy với nhóm bạn", "Dự sự kiện thời trang", "Đi dạo phố"]
MOODS = ["Cần sự tự tin, quyền lực", "Đang mệt mỏi, cần thoải mái", "Vui vẻ, muốn nổi bật", "Trầm mặc, ẩn mình", "Muốn lãng mạn, quyến rũ", "Năng động, bùng nổ"]

# BIẾN SỐ CÁ NHÂN HÓA (HYPER-PERSONALIZATION)
BODY_TYPES = ["Dáng quả lê (Mông đùi to)", "Dáng quả táo (Vòng 2 lớn)", "Dáng đồng hồ cát", "Thấp bé (Petite)", "Cao gầy", "Cân đối"]
SKIN_TONES = ["Da trắng sáng", "Da trung bình (Warm tone)", "Da ngăm đen (Cool tone)", "Da vàng (Olive)"]
BUDGETS = ["Ngân sách sinh viên (dưới 500k)", "Ngân sách trung bình (1-3 triệu)", "Không giới hạn (Hàng hiệu sang trọng)"]
CONSTRAINTS = ["Dị ứng với vải len", "Ghét mặc váy", "Thích mặc đồ Rộng (Oversize)", "Đang có bầu 3 tháng", "Thích mặc hở bạo", "Phong cách kín đáo, thanh lịch", "Không có giới hạn"]

def generate_ultimate_reasoning(num_samples=2000):
    print(">>> Đang sinh bộ dữ liệu ULTIMATE: Cá nhân hóa Tột Độ (Hyper-Personalization)...")
    dataset = []
    
    for _ in range(num_samples):
        # Lấy ngẫu nhiên profile user
        w, l, p, m = random.choice(WEATHER), random.choice(LOCATIONS), random.choice(PURPOSES), random.choice(MOODS)
        body, skin, budget, constraint = random.choice(BODY_TYPES), random.choice(SKIN_TONES), random.choice(BUDGETS), random.choice(CONSTRAINTS)
        
        user_prompt = (
            f"Chào AI, thời tiết hôm nay {w}. Tôi cần trang phục để {p} tại {l}. "
            f"Tâm trạng tôi đang {m}. \nThông tin cá nhân: Tôi có {body}, {skin}. "
            f"Tài chính: {budget}. Lưu ý đặc biệt: {constraint}. \nHãy phối đồ giúp tôi."
        )
        
        # LOGIC SUY LUẬN ĐA CHIỀU (CHAIN OF THOUGHT)
        think_steps = [
            f"- Phân tích Ngoại hình: {body} -> Cần chọn form dáng che khuyết điểm/tôn dáng phù hợp.",
            f"- Phân tích Da: {skin} -> Cần chọn bảng màu (Color Palette) tương thích để không làm xỉn da.",
            f"- Phân tích Ngữ cảnh: {w} + {p} tại {l} -> Định hình phong cách (Style) và chất liệu (Material).",
            f"- Phân tích Tâm lý & Giới hạn: {m} + {constraint} + {budget} -> Lọc lại các item cuối cùng."
        ]
        
        # SUY LUẬN ĐỘNG
        style_recommend = "Minimalist / Casual"
        color_recommend = "Màu trung tính"
        item_recommend = "Áo thun cơ bản và quần ống suông"
        
        # Logic Body Type
        if "Mông đùi to" in body:
            think_steps.append("-> Dáng quả lê: Ưu tiên quần/váy chữ A tối màu, áo sáng màu có điểm nhấn.")
            item_recommend = "Áo lụa cổ V màu sáng kết hợp váy/quần chữ A tối màu"
        elif "Vòng 2 lớn" in body:
            think_steps.append("-> Dáng quả táo: Tránh áo ôm sát, ưu tiên váy Peplum hoặc áo Oversize.")
            item_recommend = "Áo khoác Blazer mỏng khoác ngoài hoặc đầm Peplum"
        elif "Thấp bé" in body:
            think_steps.append("-> Petite: Cần đồ cạp cao (High-waisted) để hack dáng, mix màu Monochrome.")
            item_recommend = "Croptop/Áo baby tee kết hợp quần cạp cao hack dáng"
            
        # Logic Thời tiết + Ràng buộc
        if "Nắng nóng" in w:
            think_steps.append("-> Thời tiết rất nóng, ưu tiên chất liệu lanh (linen), lụa hoặc cotton thoáng mát.")
        if "len" in constraint:
            think_steps.append("-> CHÚ Ý: Bỏ qua mọi loại len, thay bằng nỉ (Fleece) hoặc áo phao nếu trời lạnh.")
        
        # Lập luận ngân sách
        if "sinh viên" in budget:
            think_steps.append("-> Ngân sách thấp: Mix & Match các item cơ bản có sẵn, tập trung vào phụ kiện (Tote bag, vòng tay) để tạo điểm nhấn.")
            style_recommend = "Streetwear / Casual"
        elif "Không giới hạn" in budget:
            think_steps.append("-> Không giới hạn tài chính: Gợi ý phong cách Old Money hoặc Chic với chất liệu cao cấp (Cashmere, Tơ tằm).")
            style_recommend = "Old Money / Quiet Luxury"
            
        ai_response = (
            f"<think>\n" + "\n".join(think_steps) + "\n</think>\n"
            f"Dựa trên ngoại hình, sở thích và bối cảnh của bạn, tôi đề xuất phong cách **{style_recommend.upper()}**.\n\n"
            f"💡 **Cách phối đồ chi tiết:**\n"
            f"- **Trang phục:** {item_recommend}. Kiểu dáng này sẽ giúp tôn lên ưu điểm của {body} đồng thời khắc phục các hạn chế.\n"
            f"- **Màu sắc:** Ưu tiên {color_recommend}, cực kỳ tôn dáng cho {skin}.\n"
            f"- **Lưu ý riêng:** Tôi đã loại trừ các lựa chọn không phù hợp với yêu cầu '{constraint}' và giữ mọi thứ nằm trong mức {budget}.\n"
            f"\nChúc bạn có một buổi {p} thật tự tin và thành công!"
        )
        
        dataset.append({"instruction": user_prompt, "output": ai_response})
        
    json_path = DATA_DIR / "ultimate_context_dataset.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print(f"Đã sinh thành công {num_samples} kịch bản ULTIMATE tại: {json_path}")

if __name__ == "__main__":
    generate_ultimate_reasoning(2000)
    print("\n=== BỘ NÃO AI ĐÃ ĐẠT TỚI CẢNH GIỚI CÁ NHÂN HÓA TỘT ĐỘ (HYPER-PERSONALIZATION) ===")
