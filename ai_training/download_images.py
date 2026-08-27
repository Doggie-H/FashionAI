import os
import sys
import json
from datasets import load_dataset
from PIL import Image

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def download_fashion_images(num_samples=50, output_dir="data/images", metadata_path="data/fashion_metadata.json"):
    print(f"[*] Khởi tạo quá trình tải {num_samples} ảnh thời trang...")
    
    # Tạo thư mục
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    print("[*] Đang kết nối tới HuggingFace Dataset 'ceyda/fashion-products-small'...")
    try:
        # Load dataset nhỏ
        ds = load_dataset("ceyda/fashion-products-small", split="train")
    except Exception as e:
        print(f"[!] Lỗi kết nối HuggingFace: {e}")
        return

    metadata = []
    
    print(f"[*] Bắt đầu tải và lưu {num_samples} bức ảnh đầu tiên...")
    
    for i, item in enumerate(ds):
        if i >= num_samples:
            break
            
        try:
            image = item["image"]
            # Lưu ảnh
            img_filename = f"outfit_{i:04d}.jpg"
            img_path = os.path.join(output_dir, img_filename)
            
            # Đảm bảo ảnh ở hệ màu RGB và lưu
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(img_path)
            
            # Trích xuất metadata
            info = {
                "id": f"outfit_{i:04d}",
                "image_path": img_path,
                "gender": item.get("gender", ""),
                "masterCategory": item.get("masterCategory", ""),
                "subCategory": item.get("subCategory", ""),
                "articleType": item.get("articleType", ""),
                "baseColour": item.get("baseColour", ""),
                "season": item.get("season", ""),
                "usage": item.get("usage", ""),
                "productDisplayName": item.get("productDisplayName", "")
            }
            metadata.append(info)
            
            if (i+1) % 10 == 0:
                print(f"  -> Đã tải {i+1}/{num_samples} ảnh.")
                
        except Exception as e:
            print(f"[!] Lỗi khi xử lý ảnh thứ {i}: {e}")
            
    # Lưu metadata
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    print(f"[*] HOÀN TẤT! Đã lưu {len(metadata)} bức ảnh tại '{output_dir}'")
    print(f"[*] Dữ liệu nhãn (metadata) lưu tại '{metadata_path}'")

if __name__ == "__main__":
    download_fashion_images(num_samples=50)
