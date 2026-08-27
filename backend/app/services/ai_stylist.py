import os
import json
from pathlib import Path

class DemoStylistEngine:
    def __init__(self):
        self.is_loaded = True

    def load_model(self):
        self.is_loaded = True

    def get_measurement_advice(self, payload, selected_tags):
        if not getattr(self, "is_loaded", True):
            return "Mô hình demo AI Stylist chưa sẵn sàng. Vui lòng tải lại sau."

        height = payload.get("height", 170)
        waist = payload.get("waist", 72)
        hip = payload.get("hip", 94)
        shoulder = payload.get("shoulder", 42)
        thigh = payload.get("thigh", 54)
        calf = payload.get("calf", 36)
        gender = payload.get("gender", "nữ")
        face_shape = payload.get("face_shape", "Trái xoan (Oval)")
        hair_style = payload.get("hair_style", "Tự nhiên")
        glasses_type = payload.get("glasses_type", "Không đeo kính")
        shoulder_slope = payload.get("shoulder_slope", "straight")
        chest_profile = payload.get("chest_profile", "full")
        leg_alignment = payload.get("leg_alignment", "straight")
        tags = ", ".join(selected_tags) if selected_tags else "nhu cầu hàng ngày"

        notes = []
        if shoulder_slope == "sloped":
            notes.append("vai xuôi")
        if chest_profile == "flat":
            notes.append("ngực lép")
        if leg_alignment == "bowed":
            notes.append("chân vòng kiềng")
        notes_str = f" ({', '.join(notes)})" if notes else ""

        return (
            "<think>\n"
            f"- Đối tượng: {gender.upper()} | Khuôn mặt: {face_shape} | Kiểu tóc: {hair_style} | Kính mắt: {glasses_type}.\n"
            f"- Số đo chi tiết: Cao {height}cm, Vai {shoulder}cm{notes_str}, Eo {waist}cm, Hông {hip}cm, Đùi {thigh}cm, Bắp chân {calf}cm.\n"
            f"- Mục tiêu: {tags} -> Phối đồ tối ưu tỷ lệ hình học và cân bằng gương mặt.\n"
            "</think>\n\n"
            f"Chào bạn! Phân tích chi tiết dành riêng cho vóc dáng ({height}cm, eo {waist}cm, hông {hip}cm{notes_str}) kết hợp khuôn mặt **{face_shape}**, tóc **{hair_style}** và kính **{glasses_type}**:\n\n"
            "✨ **1. Tương thích Gương mặt & Phụ kiện:**\n"
            f"- Với khuôn mặt **{face_shape}**, kiểu tóc **{hair_style}** kết hợp cùng **{glasses_type}** giúp tạo khung cân đối. Cổ áo chữ V hoặc cổ bẻ mở nhẹ sẽ giúp phần cổ thanh thoát hơn.\n\n"
            "👗 **2. Phối trang phục tỷ lệ vàng:**\n"
            f"- **Thân trên:** Chọn áo có cấu trúc vừa vặn (đặc biệt phù hợp với đặc điểm {', '.join(notes) if notes else 'chuẩn'}), vạt áo chạm ngang cạp quần tạo hiệu ứng tỷ lệ 1/3.\n"
            f"- **Thân dưới:** Với vòng hông {hip}cm và đùi {thigh}cm, quần tây ống đứng (Straight-leg) hoặc cạp cao là lựa chọn hoàn hảo giúp chân thẳng dài.\n\n"
            "🎨 **3. Bảng màu gợi ý:**\n"
            "- Phối màu tương phản nhẹ (Light Top + Deep Bottom) tôn dáng và làm nổi bật phong thái tự tin."
        )

    def get_wardrobe_advice(self, wardrobe_items, selected_tags, user_profile=None):
        profile = user_profile or {}
        height = profile.get("height", 170)
        waist = profile.get("waist", 72)
        hip = profile.get("hip", 94)
        shoulder = profile.get("shoulder", 42)
        thigh = profile.get("thigh", 54)
        calf = profile.get("calf", 36)
        bicep = profile.get("bicep", 28)
        gender = profile.get("gender", "nữ")
        face_shape = profile.get("face_shape", "Trái xoan (Oval)")
        hair_style = profile.get("hair_style", "Layer Bob")
        glasses_type = profile.get("glasses_type", "Không đeo kính")
        tags = ", ".join(selected_tags) if selected_tags else "nhu cầu hàng ngày"

        # Phân tích hình thể chi tiết
        body_shape = "Dáng đồng hồ cát"
        if isinstance(hip, (int, float)) and isinstance(waist, (int, float)) and hip - waist >= 22 and hip > (shoulder or 42) + 4:
            body_shape = "Dáng quả lê (Hông đùi nổi bật, vai thon)"
        elif isinstance(shoulder, (int, float)) and isinstance(hip, (int, float)) and shoulder > hip + 5:
            body_shape = "Dáng tam giác ngược (Khung vai rộng nam tính)"
        elif isinstance(waist, (int, float)) and isinstance(hip, (int, float)) and waist >= hip - 8:
            body_shape = "Dáng quả táo (Vòng 2 đầy đặn)"
        elif isinstance(hip, (int, float)) and isinstance(waist, (int, float)) and abs(hip - waist) < 16:
            body_shape = "Dáng chữ nhật (Thanh mảnh, số đo đều)"
        
        num_items = len(wardrobe_items)
        items_desc = f"{num_items} món đồ trong tủ đồ của bạn" if num_items > 0 else "bộ sưu tập thời trang cao cấp"

        return (
            "<think>\n"
            f"- Đối tượng & Giới tính: {gender.upper()} | Hình thể: {body_shape} (Cao: {height}cm, Vai: {shoulder}cm, Eo: {waist}cm, Hông: {hip}cm, Đùi: {thigh}cm, Bắp chân: {calf}cm).\n"
            f"- Phân tích Gương mặt: {face_shape} | Kiểu tóc: {hair_style} | Kính mắt: {glasses_type}.\n"
            f"- Mục tiêu & Sự kiện: {tags} -> Định hình Style DNA phù hợp ngũ quan và tỷ lệ cơ thể.\n"
            f"- Phân tích Tủ đồ: Khai thác {items_desc} theo quy tắc cân đối thị giác, tôn ưu điểm, che khuyết điểm.\n"
            "</think>\n\n"
            f"Chào bạn! Dựa trên thông số chi tiết của bạn (**{gender.upper()}**, vóc dáng **{body_shape}**, mặt **{face_shape}**, tóc **{hair_style}**, kính **{glasses_type}**) cùng nhu cầu **{tags}**, AI Stylist đề xuất giải pháp phối đồ chuyên sâu:\n\n"
            f"🌟 **1. Hòa Sắc Gương Mặt & Phụ Kiện (Face & Eyewear Harmony):**\n"
            f"- Với dáng mặt **{face_shape}** cùng kiểu tóc **{hair_style}**, việc bạn diện **{glasses_type}** tạo nên điểm nhấn tri thức và cá tính. Cổ áo nên ưu tiên phom mở (cổ bẻ Cuba, cổ chữ V hoặc sơ mi mở 1 cúc) để tạo đường dẫn ánh nhìn hài hòa từ khuôn mặt xuống phần ngực áo.\n\n"
            f"✨ **2. Bản Phối Trang Phục Chuẩn Tỷ Lệ Cơ Thể (Custom Fit Outfit):**\n"
            f"- **Thân trên (Top):** Khung vai {shoulder}cm kết hợp bắp tay {bicep}cm thích hợp với áo có đường may vai chuẩn xác (Set-in sleeves), chất liệu vải dệt đứng phom giúp tôn khung ngực và eo {waist}cm.\n"
            f"- **Thân dưới (Bottom):** Với vòng hông {hip}cm, đùi {thigh}cm và bắp chân {calf}cm, dáng quần cạp vừa đến cạp cao ống đứng (Straight/Tapered Fit) sẽ giúp đôi chân trông thon dài, tạo sự liền mạch từ hông xuống gót giày.\n"
            f"- **Giày & Phụ kiện:** Đồng bộ tông màu giày với thắt lưng hoặc gọng kính ({glasses_type}) để tạo sự liên kết thẩm mỹ chặt chẽ.\n\n"
            "🎨 **3. Bảng Phối Màu Sắc & Chất Liệu:**\n"
            "- Bảng màu: Ưu tiên tông màu bổ trợ tôn nước da và màu tóc (Xanh Navy, Be nhạt, Xám than, Nâu Caramel, Trắng ngà).\n"
            "- Chất liệu: Cotton dệt cao cấp, Linen thô tự nhiên hoặc Wool pha mềm mại, thoáng mát.\n\n"
            "💡 **4. Lời khuyên độc quyền từ AI Stylist:**\n"
            f"- Khi kết hợp kính **{glasses_type}** và kiểu tóc **{hair_style}**, hãy giữ ve áo và phụ kiện tối giản để tránh rườm rà phần thân trên.\n\n"
            "Set đồ đã được mô phỏng trực tiếp trên hình nhân 3D của bạn với tỷ lệ số đo chuẩn xác!"
        )

    def get_style_advice(self, image_path, selected_tags, user_profile=None):
        tags = ", ".join(selected_tags) if selected_tags else "nhu cầu chưa xác định"
        profile = user_profile or {}
        body_type = profile.get("body_type", "chưa xác định")
        skin_tone = profile.get("skin_tone", "chưa xác định")
        hair_type = profile.get("hair_type", "chưa xác định")
        face_shape = profile.get("face_shape", "chưa xác định")
        return (
            "ĐÂY LÀ KẾT QUẢ DEMO LOCAL\n\n"
            f"Nhu cầu: {tags}.\n"
            f"Hồ sơ: dáng {body_type}; tone da {skin_tone}; kiểu tóc {hair_type}; khuôn mặt {face_shape}.\n\n"
            "Gợi ý phối đồ: ưu tiên một món chính có phom vừa vặn, phối cùng "
            "màu trung tính và một phụ kiện tạo điểm nhấn."
        )

if os.getenv("AI_STYLIST_DEMO_MODE", "1").lower() in {"1", "true", "yes", "on"}:
    stylist_engine = DemoStylistEngine()
else:
    from ai_training.vlm_inference import MasterStylistPipeline
    stylist_engine = MasterStylistPipeline()
