import sys
import os
import json
from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def generate_synthetic_images(output_dir="data/images", metadata_path="data/fashion_metadata.json"):
    print("[*] Tạo dữ liệu ảnh thời trang mẫu để test hệ thống...")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    items = [
        {"name": "Áo thun trắng Oversize", "color": "white", "rgb": (240, 240, 240)},
        {"name": "Quần Jean xanh dương", "color": "blue", "rgb": (50, 100, 200)},
        {"name": "Áo khoác Blazer đen", "color": "black", "rgb": (40, 40, 40)},
        {"name": "Váy hoa mùa hè", "color": "yellow", "rgb": (255, 230, 150)},
        {"name": "Giày Sneaker thể thao", "color": "red", "rgb": (220, 60, 60)}
    ] * 2  # Nhân đôi để có 10 ảnh
    
    metadata = []
    
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()

    for i, item in enumerate(items):
        img_filename = f"outfit_{i:04d}.jpg"
        img_path = os.path.join(output_dir, img_filename)
        
        # Tạo ảnh nền màu tương ứng
        img = Image.new("RGB", (400, 400), color=item["rgb"])
        draw = ImageDraw.Draw(img)
        
        # Thêm text vào giữa ảnh
        text = item["name"]
        text_color = "black" if item["color"] in ["white", "yellow"] else "white"
        
        # Vẽ một số họa tiết để AI phân biệt được các pixel
        draw.rectangle([50, 50, 350, 350], outline=text_color, width=10)
        draw.text((100, 180), text, fill=text_color, font=font)
        
        img.save(img_path)
        
        metadata.append({
            "id": f"outfit_{i:04d}",
            "image_path": img_path,
            "productDisplayName": item["name"],
            "baseColour": item["color"],
            "gender": "Unisex",
            "season": "All Seasons",
            "usage": "Casual"
        })
        print(f"  -> Đã tạo: {img_filename}")
        
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    print(f"[*] HOÀN TẤT! Đã tạo {len(metadata)} bức ảnh tại '{output_dir}'.")

if __name__ == "__main__":
    generate_synthetic_images()
