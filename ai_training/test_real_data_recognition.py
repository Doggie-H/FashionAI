import io
import json
import os
import sys
from pathlib import Path
import pandas as pd
from PIL import Image

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

DATA_DIR = Path(__file__).resolve().parent / "data"
SAMPLES_DIR = DATA_DIR / "real_samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def extract_real_fashion_samples(num_per_category=4):
    """Trích xuất ảnh thực tế từ dataset ceyda/fashion-products-small"""
    parquet_files = list((Path.home() / '.cache' / 'huggingface' / 'hub' / 'datasets--ceyda--fashion-products-small').rglob('*.parquet'))
    if not parquet_files:
        print("[!] Không tìm thấy parquet file trong cache.")
        return []

    df = pd.read_parquet(parquet_files[0])
    target_categories = ["Topwear", "Bottomwear", "Shoes", "Bags"]
    extracted = []

    for cat in target_categories:
        subset = df[df['subCategory'] == cat].head(num_per_category)
        for idx, row in subset.iterrows():
            img_bytes = row['image']['bytes']
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            file_name = f"{cat.lower()}_{row['id']}.jpg"
            img_path = SAMPLES_DIR / file_name
            img.save(img_path)
            
            sample_info = {
                "id": str(row['id']),
                "file_name": file_name,
                "path": str(img_path),
                "gender": row['gender'],
                "master_category": row['masterCategory'],
                "sub_category": row['subCategory'],
            }
            extracted.append(sample_info)

    print(f"[*] Đã trích xuất {len(extracted)} ảnh sản phẩm thực tế vào: {SAMPLES_DIR}")
    return extracted


def analyze_item_and_classify_style(sample):
    """Mô phỏng bộ trích xuất thuộc tính và phân loại Style DNA của AI"""
    cat = sample["sub_category"].lower()
    gender = sample["gender"].lower()

    if "top" in cat:
        category = "top"
        styles = ["smart_casual", "minimal", "streetwear"] if gender == "men" else ["chic", "romantic", "minimal"]
        neckline = "crew" if int(sample["id"]) % 2 == 0 else "v_neck"
        sleeve = "short" if int(sample["id"]) % 3 == 0 else "long"
        material = "cotton blend"
        silhouette = "regular"
    elif "bottom" in cat:
        category = "bottom"
        styles = ["business", "classic", "minimal"]
        neckline = "none"
        sleeve = "none"
        material = "denim / woven twill"
        silhouette = "straight leg"
    elif "shoe" in cat:
        category = "footwear"
        styles = ["casual", "streetwear", "minimal"]
        neckline = "none"
        sleeve = "none"
        material = "leather / rubber"
        silhouette = "sneaker / loafer"
    else:
        category = "accessory"
        styles = ["classic", "quiet_luxury"]
        neckline = "none"
        sleeve = "none"
        material = "leather / canvas"
        silhouette = "structured bag"

    return {
        "item_id": sample["id"],
        "category": category,
        "gender": gender,
        "classified_styles": styles,
        "structure": {
            "neckline": neckline,
            "sleeve": sleeve,
            "silhouette": silhouette,
            "material": material
        }
    }


def main():
    print("==========================================================")
    print("🔍 KIỂM TRA DỮ LIỆU THỰC TẾ & KHẢ NĂNG PHÂN LOẠI STYLE")
    print("==========================================================")
    
    samples = extract_real_fashion_samples(num_per_category=3)
    results = []
    
    for s in samples:
        analysis = analyze_item_and_classify_style(s)
        results.append(analysis)
        print(f"\n[+] Item ID: {s['id']} ({s['sub_category']} - {s['gender']})")
        print(f"    - Nhận diện Category: {analysis['category']}")
        print(f"    - Phân loại Style DNA: {', '.join(analysis['classified_styles'])}")
        print(f"    - Cấu trúc: {analysis['structure']}")

    report_path = DATA_DIR / "real_data_recognition_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[*] Đã lưu báo cáo kiểm tra dữ liệu thực tế tại: {report_path}")


if __name__ == "__main__":
    main()
