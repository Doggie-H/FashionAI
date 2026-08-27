import sys
import json
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def generate_taxonomy_db(output_path="data/fashion_taxonomy.json"):
    print("[*] Bắt đầu khởi tạo cơ sở dữ liệu Taxonomy cho 30 Phong cách...")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    styles = [
        "Casual", "Smart Casual", "Minimalist", "Normcore", "Monochrome", "Athleisure",
        "Classic", "Chic", "Old Money", "Preppy", "Business Professional",
        "Streetwear", "Y2K", "Techwear", "Gorpcore", "Grunge", "Skater",
        "Vintage", "Retro", "Bohemian", "Romantic", "Artsy", "Dark Academia", "Light Academia",
        "K-Fashion", "J-Fashion", "Resort Wear", "Soft Boy/Girl", "Edgy", "Eclectic"
    ]
    
    types = [
        "Hoạt động Thường ngày", "Công việc & Học tập", "Giải trí & Giao tiếp",
        "Sự kiện Đặc biệt", "Thể thao & Sức khỏe", "Du lịch & Nghỉ dưỡng"
    ]
    
    tags = {
        "daily_activities": [
            "Đi học đại học/đến trường", "Đi làm công sở hàng ngày", "Làm việc tự do/Ngồi quán Cafe",
            "Đi siêu thị/Mua sắm", "Đi dạo phố/Gặp bạn bè", "Ở nhà thư giãn/Làm việc từ xa",
            "Đi phỏng vấn xin việc", "Gặp gỡ gia đình/Họ hàng", "Đón con/Đi dạo công viên",
            "Tập thể dục buổi sáng", "Trang phục đi xe máy", "Trang phục chống nắng"
        ],
        "weather": [
            "Mùa Xuân/Mát mẻ", "Mùa Hè/Nóng bức", "Mùa Thu/Se lạnh", "Mùa Đông/Lạnh giá", "Trời mưa/Ẩm ướt"
        ],
        "vibe": [
            "Thoải mái (Oversize)", "Tôn dáng (Slim-fit)", "Thanh lịch", "Năng động", 
            "Hack chiều cao", "Giấu khuyết điểm", "Trưởng thành", "Trẻ trung"
        ],
        "wardrobe_integration": [
            "Ưu tiên Đồ Mới Mua", "Đồ Lâu Chưa Mặc", "Tận dụng Áo Thun", 
            "Kết hợp Quần Jean", "Chỉ dùng đồ Đen/Trắng", "Sử dụng Phụ kiện nổi bật"
        ]
    }
    
    taxonomy_db = {
        "styles": [{"id": f"style_{i+1:02d}", "name": name} for i, name in enumerate(styles)],
        "types": [{"id": f"type_{i+1:02d}", "name": name} for i, name in enumerate(types)],
        "tags": tags
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy_db, f, ensure_ascii=False, indent=4)
        
    print(f"[*] HOÀN TẤT! Đã lưu CSDL Taxonomy tại: {output_path}")

if __name__ == "__main__":
    generate_taxonomy_db()
