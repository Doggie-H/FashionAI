import gradio as gr
import json
import os
import sys

# Đảm bảo có thể import ai_training
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.services.ai_stylist import stylist_engine

# Tải Taxonomy
def load_taxonomy():
    taxonomy_path = "data/fashion_taxonomy.json"
    if not os.path.exists(taxonomy_path):
        return {}
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        return json.load(f)

taxonomy_db = load_taxonomy()

# Trích xuất tags theo từng danh mục
daily_tags = taxonomy_db.get("tags", {}).get("daily_activities", [])
weather_tags = taxonomy_db.get("tags", {}).get("weather", [])
vibe_tags = taxonomy_db.get("tags", {}).get("vibe", [])
integration_tags = taxonomy_db.get("tags", {}).get("wardrobe_integration", [])

# Đảm bảo model đã load khi Gradio bắt đầu
print("Bắt đầu nạp AI Model...")
stylist_engine.load_model()
print("Hoàn tất nạp AI Model.")

def predict(image, act_tags, wea_tags, vibe_tags, int_tags, body_type, skin_tone, hair_type, face_shape):
    if image is None:
        return "Vui lòng tải lên một bức ảnh thời trang."
    
    # Gom tất cả tags lại
    selected_tags = []
    for tag_list in [act_tags, wea_tags, vibe_tags, int_tags]:
        if tag_list:
            selected_tags.extend(tag_list)
            
    if not selected_tags:
        selected_tags = ["Tự do sáng tạo"] # Fallback nếu không chọn gì
    
    # Gom thông tin User Profile
    user_profile = {
        "body_type": body_type,
        "skin_tone": skin_tone,
        "hair_type": hair_type,
        "face_shape": face_shape
    }
    
    # Lưu ảnh tạm thời
    tmp_path = "temp_gradio_upload.jpg"
    image.save(tmp_path)
    
    # Gọi AI Stylist (Cấp Master)
    response = stylist_engine.get_style_advice(tmp_path, selected_tags, user_profile)
    return response

def auto_detect_fn(image):
    if image is None:
        gr.Warning("Vui lòng tải ảnh lên trước khi bấm tự động nhận diện.")
        return gr.update(), gr.update(), gr.update(), gr.update()
        
    tmp_path = "temp_detect.jpg"
    image.save(tmp_path)
    
    json_str = stylist_engine.auto_detect_profile(tmp_path)
    
    # Cố gắng bóc tách JSON
    try:
        # Trong trường hợp model trả về chuỗi JSON có gạch chéo ```json ... ```
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].strip()
            
        data = json.loads(json_str)
        
        # Mặc định giữ giá trị cũ nếu JSON thiếu field
        body = data.get("body_type", "Dáng Đồng Hồ Cát")
        skin = data.get("skin_tone", "Trung tính (Neutral)")
        hair = data.get("hair_type", "Tóc dài suôn mượt")
        face = data.get("face_shape", "Mặt trái xoan")
        
        gr.Info("Đã nhận diện thành công qua Ảnh!")
        return body, skin, hair, face
    except Exception as e:
        print("Lỗi parse JSON Auto-Detect:", e)
        print("Raw output:", json_str)
        gr.Warning("AI không thể nhận diện rõ các đặc điểm, vui lòng thử ảnh khác.")
        return gr.update(), gr.update(), gr.update(), gr.update()

def update_3d_avatar(body_type):
    model_map = {
        "Dáng Quả Lê (hông to, vai nhỏ)": "data/models/pear_body.obj",
        "Dáng Quả Táo (tròn trịa, bụng to)": "data/models/apple_body.obj",
        "Dáng Đồng Hồ Cát": "data/models/hourglass_body.obj",
        "Dáng Chữ Nhật (ít đường cong)": "data/models/rectangle_body.obj",
        "Tam giác ngược (vai rộng, hông hẹp)": "data/models/inverted_triangle_body.obj"
    }
    path = model_map.get(body_type, "data/models/hourglass_body.obj")
    if not os.path.exists(path):
        return None
    return path

# Xây dựng giao diện Gradio
with gr.Blocks(theme=gr.themes.Soft(), css="""
    .container { max-width: 1200px; margin: auto; }
    .header-text { text-align: center; margin-bottom: 20px; }
""") as demo:
    
    gr.Markdown("# 👗 3D AI Master Stylist", elem_classes="header-text")
    gr.Markdown("Hệ thống tư vấn thời trang AI với triết lý thiết kế chuyên sâu, phân tích tỷ lệ cơ thể và quy tắc màu sắc chuẩn mực.", elem_classes="header-text")
    
    with gr.Tabs() as tabs:
        
        # BƯỚC 1: HỒ SƠ CÁ NHÂN & AVATAR 3D
        with gr.TabItem("👤 Bước 1: Hồ Sơ Cá Nhân & 3D Avatar", id=0):
            gr.Markdown("### Thiết lập Đặc điểm Cơ thể & Xem trước Hình nhân 3D")
            gr.Markdown("Thông tin này giúp AI hiểu rõ hình thể của bạn để đưa ra lời khuyên tôn dáng nhất.")
            
            with gr.Row():
                # Cột trái: Nhập liệu
                with gr.Column(scale=4):
                    gr.Markdown("#### 📸 Tự Động Nhận Diện bằng Camera / Ảnh")
                    user_photo = gr.Image(type="pil", label="Tải ảnh chân dung hoặc toàn thân", sources=["upload", "webcam"])
                    detect_btn = gr.Button("🔍 AI Tự Động Nhận Diện", variant="secondary")
                    
                    gr.Markdown("#### ✍️ Hoặc Chọn Thủ Công")
                    body_input = gr.Dropdown(choices=["Dáng Quả Lê (hông to, vai nhỏ)", "Dáng Quả Táo (tròn trịa, bụng to)", "Dáng Đồng Hồ Cát", "Dáng Chữ Nhật (ít đường cong)", "Tam giác ngược (vai rộng, hông hẹp)"], label="Dáng người (Body Type)", value="Dáng Đồng Hồ Cát")
                    skin_input = gr.Dropdown(choices=["Ngăm đen (Warm undertone)", "Trắng sáng (Cool undertone)", "Trung tính (Neutral)", "Da Vàng (Olive/Asian)"], label="Tone da (Skin Tone)", value="Trung tính (Neutral)")
                    hair_input = gr.Dropdown(choices=["Tóc ngắn cá tính", "Tóc dài suôn mượt", "Tóc xoăn bồng bềnh", "Tóc nhuộm sáng"], label="Kiểu tóc (Hair Type)", value="Tóc dài suôn mượt")
                    face_input = gr.Dropdown(choices=["Mặt tròn", "Mặt V-line", "Mặt vuông góc cạnh", "Mặt trái xoan"], label="Khuôn mặt (Face Shape)", value="Mặt trái xoan")
                    
                    next_btn = gr.Button("💾 Lưu Hồ Sơ & Cập Nhật", variant="primary")
                    
                # Cột phải: 3D Avatar (Real-time)
                with gr.Column(scale=6):
                    gr.Markdown("#### 🧍‍♀️ Hình Nhân 3D Mô Phỏng Cơ Thể Bạn (Live Preview)")
                    avatar_3d = gr.Model3D(value="data/models/hourglass_body.obj", clear_color=[0.95, 0.95, 0.95, 1.0], label="Xoay 360 độ để xem form dáng")
            
        # BƯỚC 2: TƯ VẤN PHỐI ĐỒ
        with gr.TabItem("📸 Bước 2: Tư Vấn Phối Đồ", id=1):
            with gr.Row():
                # Cột trái: Input
                with gr.Column(scale=4):
                    image_input = gr.Image(type="pil", label="Hình ảnh quần áo / Outfit")
                    
                    gr.Markdown("### 📍 Bối cảnh & Nhu cầu (Context)")
                    with gr.Accordion("Bối cảnh sử dụng (Click để chọn)", open=False):
                        act_input = gr.CheckboxGroup(choices=daily_tags, label="Hoạt động")
                        wea_input = gr.CheckboxGroup(choices=weather_tags, label="Thời tiết")
                    with gr.Accordion("Định hướng Phong cách & Tủ đồ (Click để chọn)", open=False):
                        vibe_input = gr.CheckboxGroup(choices=vibe_tags, label="Phong cách (Vibe)")
                        int_input = gr.CheckboxGroup(choices=integration_tags, label="Tích hợp tủ đồ")
                        
                    submit_btn = gr.Button("✨ Phân Tích Bởi AI Master", variant="primary", size="lg")
                
                # Cột phải: Output
                with gr.Column(scale=6):
                    output_text = gr.Textbox(label="💡 Trí tuệ AI Master Stylist", lines=35)
                    
        # BƯỚC 3: TỦ ĐỒ SỐ
        with gr.TabItem("🧥 Bước 3: Tủ Đồ Số (Wardrobe)", id=2):
            gr.Markdown("### Quản lý Kho trang phục cá nhân")
            gr.Markdown("Tải lên hình ảnh quần áo có sẵn trong tủ đồ của bạn để AI có thể tự động mix & match. (Tính năng AI Auto-Match tủ đồ đang trong quá trình thử nghiệm).")
            with gr.Row():
                with gr.Column(scale=3):
                    wardrobe_upload = gr.File(file_count="multiple", file_types=["image"], label="Tải ảnh quần áo")
                with gr.Column(scale=7):
                    wardrobe_gallery = gr.Gallery(label="Tủ đồ của bạn", columns=5, height="auto")
            
            def update_gallery(files):
                if not files: return []
                return [f.name for f in files]
            
            wardrobe_upload.upload(update_gallery, inputs=[wardrobe_upload], outputs=[wardrobe_gallery])

    # Sự kiện thay đổi Sliders -> Đổi 3D Realtime
    body_input.change(fn=update_3d_avatar, inputs=[body_input], outputs=[avatar_3d])

    # Sự kiện
    def save_profile():
        gr.Info("Hồ sơ cá nhân đã được ghi nhận! Xin mời chuyển sang Tab 'Tư Vấn Phối Đồ' để tiếp tục.")
    
    next_btn.click(fn=save_profile, inputs=None, outputs=None)
    
    # Sự kiện Auto-Detect
    detect_btn.click(
        fn=auto_detect_fn,
        inputs=[user_photo],
        outputs=[body_input, skin_input, hair_input, face_input]
    )
    
    # Sự kiện phân tích AI
    submit_btn.click(
        fn=predict, 
        inputs=[image_input, act_input, wea_input, vibe_input, int_input, body_input, skin_input, hair_input, face_input], 
        outputs=[output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
