import os
import sys
import json
import requests
from pathlib import Path

# Cấu hình UTF-8 cho Windows Terminal
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path("data")

# TỪ ĐIỂN 20 PHONG CÁCH THỜI TRANG ĐÌNH ĐÁM
FASHION_STYLES = {
    "vintage": "Phong cách cổ điển, hoài niệm.",
    "streetwear": "Phong cách đường phố, bụi bặm, phá cách.",
    "office": "Thanh lịch, công sở.",
    "casual": "Trang phục hàng ngày, thoải mái.",
    "minimalist": "Tối giản, ít họa tiết, màu sắc trung tính.",
    "y2k": "Phong cách đầu thập niên 2000, rực rỡ, phá cách.",
    "dark_academia": "Cổ điển Châu Âu, học thuật, tone màu tối (nâu, đen, rêu).",
    "light_academia": "Tương tự Dark Academia nhưng tone màu sáng (be, trắng, kem).",
    "techwear": "Thời trang công nghệ, cyberpunk, chất liệu chống nước, nhiều túi.",
    "bohemian": "Tự do, phóng khoáng, họa tiết thổ cẩm, tua rua.",
    "preppy": "Học sinh nhà giàu Mỹ, áo vest, caro, thanh lịch.",
    "grunge": "Nổi loạn thập niên 90, áo khoác da, flannel sờn rách.",
    "old_money": "Sang trọng ngầm (Quiet Luxury), không logo, chất liệu cao cấp (lụa, cashmere).",
    "athleisure": "Thể thao pha lẫn mặc hàng ngày, năng động (Legging, Hoodie, Sneaker).",
    "goth": "Hắc ám, đen tuyền, ren, phụ kiện kim loại.",
    "coquette": "Nữ tính, lãng mạn, nơ, ren, màu pastel.",
    "normcore": "Bình thường đến mức đặc biệt, không chạy theo xu hướng.",
    "harajuku": "Nhật Bản, đầy màu sắc, phối đồ nhiều layer kỳ dị.",
    "chic": "Sang chảnh, thời thượng, sành điệu.",
    "avant_garde": "Thời trang tiên phong, dị biệt, mang tính trình diễn nghệ thuật."
}

def create_folders():
    for style in FASHION_STYLES.keys():
        os.makedirs(DATA_DIR / style, exist_ok=True)
    print(f"Đã tạo xong {len(FASHION_STYLES)} thư mục phân loại thời trang chuyên sâu.")

def generate_mixing_rules():
    print("\n>>> Đang sinh Ma trận Luật Phối đồ (Mixing Matrix) cho AI...")
    
    dataset = []
    
    # Sinh dữ liệu rule mixing chéo (Cross-Style Mixing)
    for style, desc in FASHION_STYLES.items():
        reason = f"Định nghĩa: {desc} "
        
        # Logic Dạy AI "Luật Bất Thành Văn" trong thời trang
        if style in ["minimalist", "old_money", "office"]:
            reason += "LUẬT MIXING: Chỉ kết hợp với các item cùng nhóm thanh lịch hoặc Casual. TUYỆT ĐỐI TRÁNH xa các item rườm rà của Y2K, Harajuku hay Bohemian. Ưu tiên nguyên tắc phối màu Monochrome (đơn sắc) hoặc Analogue (tương đồng)."
        elif style in ["streetwear", "techwear", "grunge"]:
            reason += "LUẬT MIXING: Khuyến khích phối layer (nhiều lớp). Có thể mix áo Oversize với quần Cargo. KHÔNG mix với đồ Office (áo sơ mi đóng thùng ôm sát). Giày đi kèm bắt buộc là Sneaker hoặc Boots hầm hố."
        elif style in ["dark_academia", "light_academia", "preppy"]:
            reason += "LUẬT MIXING: Tuân thủ quy tắc Layering học thuật (Áo sơ mi + Áo gile + Blazer). Màu sắc phải xoay quanh Earth-tone (Nâu, Be, Xanh rêu). Có thể mix chéo với Old Money. Không mix với đồ thể thao (Athleisure)."
        elif style in ["bohemian", "coquette"]:
            reason += "LUẬT MIXING: Đặc trưng bởi sự mềm mại. Hợp với chất liệu lanh, voan, ren. Tránh mix với các chất liệu quá cứng cáp hoặc hiện đại như Techwear (chống nước, phản quang)."
        elif style in ["y2k", "harajuku", "avant_garde"]:
            reason += "LUẬT MIXING: Không có giới hạn về màu sắc. Cho phép Color-blocking (phối các màu đối lập). Y2K hợp với quần cạp trễ, áo croptop. Harajuku cần phụ kiện sặc sỡ."
        else:
            reason += "LUẬT MIXING: Phong cách linh hoạt. Dùng làm item nền (Base layer) để tôn lên các món đồ họa tiết của phong cách khác."

        dataset.append({
            "category": style,
            "ai_mixing_reasoning": reason
        })
        
    json_path = DATA_DIR / "advanced_mixing_rules.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print(f"Đã tạo Ma trận Luật Mixing cho {len(FASHION_STYLES)} phong cách tại: {json_path}")

if __name__ == "__main__":
    print("=== BẮT ĐẦU KHỞI TẠO SIÊU DỮ LIỆU FASHION ===")
    create_folders()
    generate_mixing_rules()
    print("\n=== HOÀN TẤT ===")
    print("AI đã được trang bị kiến thức của hàng chục phong cách thời trang thịnh hành nhất!")
