import json
import random
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 1. PHONG CÁCH VÀ STYLE DNA
STYLES = {
    "Old Money / Quiet Luxury": {
        "desc": "Sang trọng kín đáo, chất liệu cao cấp, không logo phô trương.",
        "materials": ["Cashmere", "Lụa tơ tằm", "Len Merino", "Cotton Ai Cập"],
        "palette": ["Trắng kem (Off-white)", "Xanh Navy", "Beige cát", "Nâu Chocolate"],
        "mix_rules": "Ưu tiên trang phục vừa vặn (Tailored fit), kết hợp Áo polo len/Sơ mi cổ đứng với Quần tây cạp cao và Giày Loafer. Phụ kiện da tối giản.",
        "avoid": ["Áo in hình sặc sỡ", "Quần rách bụi bặm", "Giày thể thao chunky hầm hố"]
    },
    "Streetwear / Urban Chic": {
        "desc": "Phóng khoáng, đường phố, nhiều layer và phom dáng rộng rãi.",
        "materials": ["Heavyweight Cotton", "Denim cứng", "Nỉ bông (Fleece)", "Nylon dù"],
        "palette": ["Đen tuyền", "Xám khói", "Xanh Rêu", "Cam Neon điểm nhấn"],
        "mix_rules": "Mix áo Hoodie/T-shirt Oversize với Quần Cargo hoặc Jeans ống thụng. Hoàn thiện bằng Sneaker retro/chunky và Túi đeo chéo.",
        "avoid": ["Giày da tây bóng", "Áo sơ mi ôm sát chiết eo", "Quần âu may đo cứng"]
    },
    "Dark Academia / Preppy": {
        "desc": "Phong cách học thuật cổ điển Châu Âu, lịch thiệp và sâu lắng.",
        "materials": ["Vải Tweed", "Len dệt vặn thừng", "Dạ mịn", "Vải Caro Tartan"],
        "palette": ["Nâu đất", "Xanh rêu đậm", "Đỏ Burgundy", "Vàng mù tạt"],
        "mix_rules": "Phối 3 lớp kinh điển: Sơ mi trắng + Áo gile len dệt + Blazer dạ/tweed. Thân dưới mix Quần âu xếp ly hoặc Chân váy midi xếp ly.",
        "avoid": ["Chất liệu bóng/phản quang", "Đồ thể thao athleisure", "Màu neon chói"]
    },
    "Minimalist / Modern Chic": {
        "desc": "Tối giản hiện đại, chú trọng phom dáng kiến trúc và đường cắt sắc sảo.",
        "materials": ["Poplin cao cấp", "Vải đũi/linen", "Len mỏng", "Tencel mềm"],
        "palette": ["Đen", "Trắng", "Xám xi măng", "Xanh đá"],
        "mix_rules": "Sử dụng nguyên tắc phối màu Monochrome (đơn sắc). Kết hợp Áo sơ mi cấu trúc phẳng với Quần ống suông cạp cao và Giày da mũi vuông.",
        "avoid": ["Bèo nhún rườm rà", "Họa tiết hoa to bản", "Phụ kiện kim loại quá khổ"]
    },
    "Y2K / Creative Rebel": {
        "desc": "Nổi loạn, sắc màu tươi sáng, pha trộn giữa hoài niệm 2000 và tương lai.",
        "materials": ["Da bóng (Vinyl)", "Denim bạc màu", "Vải nhung tuyết (Velour)", "Lưới mỏng"],
        "palette": ["Hồng fuchsia", "Bạc ánh kim (Metallic)", "Xanh dương baby", "Xanh cốm"],
        "mix_rules": "Mix Croptop/Baby tee với Quần cạp trễ (Low-rise) hoặc Chân váy ngắn. Điểm xuyết kính mát gọng nhỏ và túi kẹp nách.",
        "avoid": ["Trang phục công sở cứng nhắc", "Đồ tối màu toàn bộ không điểm nhấn"]
    },
    "Athleisure / Active Luxury": {
        "desc": "Năng động, thể thao thoải mái nhưng vẫn chỉn chu và thời thượng.",
        "materials": ["Spandex co giãn 4 chiều", "Vải dù gió", "Thun dệt vi sợi"],
        "palette": ["Xanh Navy", "Đen", "Trắng", "Xám tiêu"],
        "mix_rules": "Mix Áo khoác zip thể thao/Hoodie với Quần Jogger kỹ thuật hoặc Quần Legging dày dặn. Đi kèm Sneaker chạy bộ cao cấp.",
        "avoid": ["Giày gót nhọn", "Váy dạ hội", "Áo sơ mi vải đũi nhăn"]
    }
}

BODY_RULES = {
    "Dáng quả lê (Mông đùi to, vai nhỏ)": {
        "focus": "Tăng trọng lượng thị giác lên vai và ngực, giải phóng phần đùi và hông.",
        "top_pick": "Áo cổ V sâu, Áo có đệm vai nhẹ, Áo sơ mi cổ bẻ màu sáng, Áo có bèo nhún thân trên.",
        "bottom_pick": "Quần tây ống đứng/ống suông tối màu, Váy chữ A dài qua gối, Quần cạp cao."
    },
    "Dáng quả táo (Vòng 2 đầy đặn, chân thon)": {
        "focus": "Chuyển điểm nhìn khỏi vòng eo, khoe đôi chân thon thả.",
        "top_pick": "Áo dáng suông vừa, Áo khoác Blazer phom rộng mở cúc tạo đường dọc, Áo cổ chữ V.",
        "bottom_pick": "Chân váy ngắn chữ A, Quần slim-fit tôn chân, Quần tây xếp ly mềm."
    },
    "Dáng đồng hồ cát (Ngực hông nở, eo thon)": {
        "focus": "Tôn vinh đường cong tự nhiên và nhấn mạnh eo.",
        "top_pick": "Áo ôm vừa vặn (Body-skimming), Áo quấn (Wrap top), Áo cổ thuyền.",
        "bottom_pick": "Quần cạp cao ôm eo, Chân váy bút chì, Quần ống loe nhẹ."
    },
    "Dáng chữ nhật (Thẳng đuột, ít đường cong)": {
        "focus": "Tạo ảo giác đường cong bằng chi tiết và phân tầng màu sắc.",
        "top_pick": "Áo tay phồng, Áo phối layer nhiều lớp, Áo Croptop có điểm nhấn eo.",
        "bottom_pick": "Quần ống rộng xếp ly phồng hông, Chân váy xòe, Thắt lưng bản nhỏ tạo eo."
    },
    "Thấp bé (Petite - dưới 1m58)": {
        "focus": "Kéo dài tỷ lệ cơ thể theo quy tắc 1/3 thân trên và 2/3 thân dưới.",
        "top_pick": "Áo Croptop hoặc sơ vin (Tuck-in) toàn bộ, Áo cổ chữ V giúp thanh thoát.",
        "bottom_pick": "Quần cạp cao (High-waisted) dài chạm mu bàn chân kết hợp giày độn/gót, Váy ngắn trên gối."
    }
}

OCCASIONS = [
    {"event": "Đi làm công sở / Họp đối tác", "vibe": "Chuyên nghiệp, chỉn chu, quyền lực nhưng thoải mái."},
    {"event": "Hẹn hò lãng mạn buổi tối", "vibe": "Quyến rũ, tinh tế, có điểm nhấn ấn tượng."},
    {"event": "Dạo phố cuối tuần / Cafe với bạn bè", "vibe": "Trẻ trung, năng động, bắt mắt và thoải mái."},
    {"event": "Dự tiệc cưới / Sự kiện trang trọng", "vibe": "Lịch sự, nổi bật có chừng mực, sang trọng."},
    {"event": "Du lịch nghỉ dưỡng / Đi biển", "vibe": "Bay bổng, thoáng mát, màu sắc phóng khoáng."}
]

WEATHERS = [
    {"condition": "Nắng nóng mùa hè 35 độ", "material_note": "Ưu tiên chất liệu Linen, Cotton mỏng, Tơ lụa thoáng khí."},
    {"condition": "Se lạnh mùa thu 20 độ", "material_note": "Lý tưởng cho phối layer nhẹ: Len mỏng, Blazer, Cardigan."},
    {"condition": "Rét đậm mùa đông dưới 15 độ", "material_note": "Cần giữ ấm thông minh: Áo khoác dạ dài (Trench coat), Len cổ lọ, Áo phao gọn gàng."},
    {"condition": "Mưa gió ẩm ướt", "material_note": "Tránh trang phục quét đất, ưu tiên chất liệu chống nước hoặc khô nhanh."}
]

def generate_master_dataset(num_samples=3000):
    print(f"[*] Đang sinh {num_samples} kịch bản Huấn Luyện AI Chuyên Sâu (Master Dataset)...")
    dataset = []

    for i in range(num_samples):
        # Chọn ngẫu nhiên thuộc tính
        style_name, style_data = random.choice(list(STYLES.items()))
        body_name, body_data = random.choice(list(BODY_RULES.items()))
        occ = random.choice(OCCASIONS)
        weather = random.choice(WEATHERS)
        skin = random.choice(["Da trắng sáng (Cool tone)", "Da trung bình (Warm tone)", "Da ngăm khỏe khoắn", "Da vàng Châu Á"])
        is_rule_breaker = random.random() < 0.25  # 25% kịch bản phá cách

        prompt = (
            f"Tư vấn phối đồ giúp tôi:\n"
            f"- Mục đích: {occ['event']} ({occ['vibe']})\n"
            f"- Thời tiết: {weather['condition']}\n"
            f"- Ngoại hình: {body_name}, {skin}\n"
            f"- Phong cách mong muốn: {style_name}\n"
            f"- Yêu cầu đặc biệt: {'Muốn phá cách, tạo dấu ấn độc lạ không nhàm chán!' if is_rule_breaker else 'Phối đồ chuẩn mực, thanh lịch và tôn dáng nhất.'}"
        )

        # Logic Chain-of-Thought
        think = [
            f"- Phân tích Bối cảnh: {occ['event']} + {weather['condition']} -> Yêu cầu phom dáng {occ['vibe']}, {weather['material_note']}",
            f"- Phân tích Cơ thể: {body_name} -> {body_data['focus']}",
            f"- Phân tích Màu sắc: {skin} -> Chọn bảng màu trong dải: {', '.join(style_data['palette'])}",
            f"- Phân tích Phong cách: {style_name} -> DNA: {style_data['desc']}"
        ]

        if is_rule_breaker:
            think.append(f"- Tư duy Sáng tạo (Rule-breaker): Áp dụng kỹ thuật High-Low Mix hoặc Color-blocking để tạo điểm nhấn tương phản bất ngờ.")
            mix_details = f"Chúng ta sẽ kết hợp phong cách **{style_name}** với một nét chấm phá bất đối xứng: Sử dụng {body_data['top_pick']} phối cùng {body_data['bottom_pick']}, hoàn thiện với phụ kiện điểm nhấn nổi bật."
        else:
            think.append(f"- Tư duy Phối đồ (Classic Rules): Tuân thủ triệt để ma trận phối đồ và nguyên tắc tỷ lệ vàng 1/3 - 2/3.")
            mix_details = f"Áp dụng nguyên tắc phối đồ chuẩn của **{style_name}**: {style_data['mix_rules']}\n+ Thân trên: {body_data['top_pick']}\n+ Thân dưới: {body_data['bottom_pick']}"

        response = (
            f"<think>\n" + "\n".join(think) + "\n</think>\n"
            f"Chào bạn! Dưới đây là set đồ được thiết kế riêng cho bạn theo phong cách **{style_name.upper()}**:\n\n"
            f"✨ **1. Bản phối trang phục (Outfit Mix):**\n"
            f"{mix_details}\n\n"
            f"🎨 **2. Bảng màu & Chất liệu:**\n"
            f"- Bảng màu tối ưu: {', '.join(style_data['palette'][:3])} (tôn sắc da {skin.split(' ')[0]}).\n"
            f"- Chất liệu khuyên dùng: {', '.join(style_data['materials'][:2])} ({weather['material_note']}).\n\n"
            f"⚠️ **3. Lưu ý tránh lỗi phối đồ:**\n"
            f"- Tránh: {', '.join(style_data['avoid'])}.\n\n"
            f"Bộ trang phục này sẽ giúp bạn hoàn toàn tự tin, tôn vinh vóc dáng và làm chủ buổi {occ['event'].lower()}!"
        )

        dataset.append({"instruction": prompt, "output": response})

    out_path = DATA_DIR / "master_fashion_dataset.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"[*] Đã sinh thành công {len(dataset)} mẫu kịch bản Master tại: {out_path}")

if __name__ == "__main__":
    generate_master_dataset(3000)
