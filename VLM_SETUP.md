# Bật VLM thật cho 3D AI Stylist

## 1. Chế độ đang dùng

Backend có hai chế độ:

| Chế độ | Biến môi trường | Mục đích |
|---|---|---|
| Demo Mode | `AI_STYLIST_DEMO_MODE=1` | Khởi động nhanh, không tải model lớn, phù hợp UI smoke test và unit test |
| Real VLM | `AI_STYLIST_DEMO_MODE=0` | Dùng `SmolVLM-Instruct` để nhìn ảnh và `Qwen2.5-0.5B-Instruct` + LoRA để lập luận |

Nếu không đặt biến môi trường, project hiện mặc định về Demo Mode để tránh tải model ngoài ý muốn.

## 2. Cài môi trường backend

Nên dùng một virtual environment riêng và Python tương thích với PyTorch/Transformers trên máy. Từ PowerShell:

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install transformers peft accelerate safetensors
```

Đối với GPU NVIDIA, cài bản PyTorch có CUDA tương ứng với driver trước khi cài hoặc kiểm tra các package còn lại. Nếu máy không có CUDA, dùng bản PyTorch CPU và chấp nhận tốc độ inference thấp hơn.

## 3. Chuẩn bị model

Lần chạy real VLM đầu tiên sẽ tải hai model Hugging Face và lưu vào cache của user:

- Vision Agent: `HuggingFaceTB/SmolVLM-Instruct`.
- Master Stylist Agent: `Qwen/Qwen2.5-0.5B-Instruct`.
- LoRA adapter tùy chọn: thư mục `trained_ai_stylist` ở project root.

Không commit model cache, token hoặc các file checkpoint lớn vào Git. Nếu model yêu cầu xác thực, cấu hình `HF_TOKEN` trong environment của user hoặc đăng nhập Hugging Face bằng CLI trong đúng virtual environment.

## 4. Khởi động real VLM

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\backend'
.\..\.venv\Scripts\Activate.ps1
$env:AI_STYLIST_DEMO_MODE = '0'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Trong cửa sổ khác, khởi động frontend:

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\web'
npm run dev
```

Mở `http://127.0.0.1:3000`, tải ảnh lên, chọn ít nhất một tag và gửi yêu cầu. Backend cần có thời gian load model trước request đầu tiên.

## 5. Kiểm tra theo từng bước

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/stylist/tags
```

Sau đó gửi ảnh mẫu:

```powershell
curl.exe -X POST http://127.0.0.1:8000/stylist/recommend/ `
  -F "image=@..\data\images\outfit_0000.jpg" `
  -F "tags=Thanh lịch,Năng động" `
  -F "body_type=Dáng Đồng Hồ Cát" `
  -F "skin_tone=Trung tính (Neutral)" `
  -F "hair_type=Tóc dài thẳng" `
  -F "face_shape=Mặt trái xoan"
```

## 6. Xử lý lỗi thường gặp

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `CUDA out of memory` | Hai model cùng nằm trên GPU hoặc dtype không phù hợp | Dùng CPU/thiết bị phù hợp, giảm batch/kích thước, hoặc chạy demo mode |
| Lỗi tải model | Thiếu mạng, cache hỏng, model ID sai hoặc cần token | Xóa cache hỏng, kiểm tra mạng/HF token và chạy lại |
| `No module named transformers/peft` | Cài dependency vào Python khác với Python chạy Uvicorn | Kích hoạt đúng `.venv`, dùng `python -m pip` và `python -m uvicorn` |
| Model load quá lâu | Lần đầu tải weights và khởi tạo processor | Chờ lần đầu; các lần sau dùng cache |
| API trả “chưa sẵn sàng” | Một trong hai agent không load được | Đọc log Vision Agent và Master Stylist Agent, sửa nguyên nhân rồi restart |

Khi cần quay lại demo nhanh:

```powershell
$env:AI_STYLIST_DEMO_MODE = '1'
```

Unit test không được phụ thuộc vào model thật. Test dùng fake engine hoặc mock processor để chạy nhanh và ổn định.

## 7. Dùng Qwen2.5-VL-7B cho Vision Agent

Project đã có adapter tại `ai_training/qwen_vl_adapter.py`. Cài dependency tùy chọn:

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist'
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-vlm.txt
```

Bật Qwen cho Vision Agent và giữ Master Stylist text model hiện tại:

```powershell
$env:AI_STYLIST_DEMO_MODE = '0'
$env:VISION_MODEL_BACKEND = 'qwen25vl'
$env:QWEN_VL_MODEL_ID = 'Qwen/Qwen2.5-VL-7B-Instruct'
$env:QWEN_VL_DEVICE_MAP = 'auto'
$env:QWEN_VL_MIN_PIXELS = '200704'
$env:QWEN_VL_MAX_PIXELS = '1003520'
$env:QWEN_VL_MAX_NEW_TOKENS = '256'
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\backend'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`QWEN_VL_MIN_PIXELS` và `QWEN_VL_MAX_PIXELS` kiểm soát số pixel đầu vào sau resize, từ đó điều chỉnh chất lượng/thời gian/VRAM. Có thể giảm `MAX_PIXELS` khi gặp out-of-memory. `QWEN_VL_USE_FLASH_ATTN=1` chỉ bật sau khi cài được `flash-attn` tương thích CUDA/PyTorch.

Kiến trúc sau khi bật Qwen là:

```text
uploaded image -> Qwen2.5-VL-7B Vision Agent -> clothing JSON
                                             -> Master Stylist text model -> Vietnamese advice
```

Qwen2.5-VL không tự động làm cho quyết định thời trang trở thành sự thật khách quan. Cần ép output JSON, validate schema, giữ lại confidence/uncertainty và đánh giá trên bộ test có ground truth. Không dùng output tự do của model để trực tiếp thực hiện hành động nghiệp vụ.

Nguồn tham khảo chính thức: [Qwen2.5-VL-7B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) và [Transformers Qwen2.5-VL documentation](https://huggingface.co/docs/transformers/en/model_doc/qwen2_5_vl).
