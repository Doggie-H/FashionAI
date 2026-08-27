import os
import sys
import json
import requests
from duckduckgo_search import DDGS
from PIL import Image
from io import BytesIO

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def download_fashion_images_ddg(num_samples=20, output_dir="data/images", metadata_path="data/fashion_metadata.json"):
    print(f"[*] Khởi tạo quá trình cào {num_samples} ảnh thời trang từ DuckDuckGo...")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    metadata = []
    
    # Từ khóa tìm kiếm
    queries = ["fashion outfit full body men", "fashion outfit full body women", "casual street style outfit"]
    
    count = 0
    with DDGS() as ddgs:
        for query in queries:
            if count >= num_samples:
                break
                
            print(f"[*] Tìm kiếm từ khóa: '{query}'...")
            try:
                results = ddgs.images(query, max_results=15)
                for r in results:
                    if count >= num_samples:
                        break
                        
                    image_url = r.get("image")
                    title = r.get("title", "")
                    
                    try:
                        # Tải ảnh
                        img_data = requests.get(image_url, timeout=5).content
                        img = Image.open(BytesIO(img_data))
                        
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                            
                        img_filename = f"outfit_{count:04d}.jpg"
                        img_path = os.path.join(output_dir, img_filename)
                        
                        # Resize ảnh để giảm VRAM lúc train VLM (ví dụ: tối đa 512x512)
                        img.thumbnail((512, 512))
                        img.save(img_path, format="JPEG", quality=85)
                        
                        metadata.append({
                            "id": f"outfit_{count:04d}",
                            "image_path": img_path,
                            "productDisplayName": title[:50],
                            "gender": "Men" if "men" in query else "Women",
                            "season": "All Seasons",
                            "usage": "Casual",
                            "baseColour": "Multicolor"
                        })
                        
                        count += 1
                        print(f"  -> Đã tải thành công: {img_filename}")
                        
                    except Exception as e:
                        print(f"  [!] Bỏ qua ảnh lỗi: {e}")
            except Exception as search_e:
                print(f"[!] Lỗi tìm kiếm: {search_e}")
                
    # Lưu metadata
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    print(f"\n[*] HOÀN TẤT! Đã cào và tải về {count} bức ảnh tại '{output_dir}'.")
    print(f"[*] Dữ liệu nhãn đã lưu tại '{metadata_path}'.")

if __name__ == "__main__":
    download_fashion_images_ddg(num_samples=20)
