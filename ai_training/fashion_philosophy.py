# ai_training/fashion_philosophy.py

FASHION_PHILOSOPHY = {
    "body_type": {
        "Dáng Đồng Hồ Cát": "Triết lý: Tôn vinh đường cong tự nhiên. Tối kỵ việc mặc phom dáng oversize cứng giấu dáng. Tập trung siết eo và sử dụng chất liệu rủ (drape) nương theo chuyển động.",
        "Dáng quả lê": "Triết lý: Áp dụng 'Visual Weight' (Trọng lượng thị giác). Chuyển trọng lượng lên phần trên bằng màu sáng, họa tiết, hoặc chi tiết bèo nhún/độn vai. Phần dưới (hông, đùi) giải phóng bằng màu tối, phom A-line hoặc ống suông mềm mại.",
        "Dáng quả táo": "Triết lý: Phân tán sự chú ý khỏi vòng eo (midsection). Tạo các đường dọc (Vertical lines) bằng áo khoác dáng dài mở cúc, hoặc áo cổ chữ V sâu để kéo dài cơ thể. Tuyệt đối tránh thắt lưng to bản ở eo.",
        "Dáng chữ nhật": "Triết lý: Kiến tạo đường cong nhân tạo (Illusion of Curves). Sử dụng kỹ thuật Color-blocking ngang, thắt lưng bản nhỏ, hoặc phối layer bất đối xứng để phá vỡ khối chữ nhật.",
        "Tam giác ngược": "Triết lý: Làm mềm vai (Visual Softening) và tăng thể tích hông. Áo thân trên nên tối màu, cổ V sâu, tay raglan. Thân dưới sử dụng xếp ly (pleats), túi hộp, hoặc màu sáng rực rỡ để kéo ánh nhìn xuống."
    },
    "body_proportions": {
        "Lưng dài chân ngắn": "Quy tắc Tỷ lệ 1/3 (Rule of Thirds): Tuyệt đối không chia cơ thể 1:1. Phải áp dụng tỷ lệ 1/3 thân trên và 2/3 thân dưới. Buộc phải sơ vin (Tuck in), mặc quần/váy cạp cao (High-waisted), hoặc sử dụng crop-top để dời đường chân ngực/eo lên cao.",
        "Chân dài lưng ngắn": "Quy tắc Tỷ lệ 2/3 (Rule of Thirds): Có thể áp dụng tỷ lệ 2/3 thân trên (Áo dáng dài qua mông, áo trễ eo - Drop waist) và 1/3 thân dưới để cân bằng lại độ dài thân trên.",
        "Cân đối": "Tỷ lệ linh hoạt. Có thể thử nghiệm phong cách phá vỡ tỷ lệ chuẩn (ví dụ: Avant-garde oversize, hoặc Low-waist Y2K)."
    },
    "special_features": {
        "sloped": "Vai xuôi: ưu tiên đường vai có cấu trúc nhẹ, cổ áo cân đối và chất liệu giữ phom; tránh đường cắt làm vai trông trễ hơn.",
        "flat": "Ngực lép: dùng layer mỏng, texture vừa phải, túi ngực hoặc chi tiết ngang có kiểm soát để tạo chiều sâu; tránh ép cơ thể theo số đo giả định.",
        "bowed": "Chân vòng kiềng: ưu tiên quần ống đứng/ống rộng vừa, váy midi hoặc đường dọc; tránh đường cắt ôm sát làm lộ trục chân.",
    },
    "skin_tone": {
        "Trắng sáng (Cool undertone)": "Color Theory: Da lạnh cộng hưởng tốt nhất với sắc độ rực rỡ (Jewel tones): Đỏ Berry, Xanh Cobalt, Tím Lilac, Xanh Emerald. Tránh pastel nhợt nhạt hoặc cam/vàng mù tạt vì gây hiệu ứng 'bệnh lý' (washed out).",
        "Trung tính (Neutral)": "Color Theory: Phù hợp nhiều dải màu. Đặc biệt bùng nổ với Đỏ thuần, Hồng san hô (Coral), Xanh Olive. Cần có ít nhất một điểm nhấn màu sắc để tránh sự đơn điệu.",
        "Ngăm đen (Warm undertone)": "Color Theory: Tôn vinh vẻ khỏe khoắn bằng màu Đất (Earth tones): Cam cháy, Vàng mustard, Đỏ gạch, Olive. Tránh màu neon hoặc pastel lạnh (xanh ngọc, tím nhạt) vì tạo độ lệch pha (clash) mạnh trên bề mặt da.",
        "Da Vàng (Olive/Asian)": "Color Theory: Khử sắc vàng bằng các gam màu sâu: Đỏ rượu (Burgundy), Xanh Navy, và Trắng kem (Off-white). Tuyệt đối tránh vàng chanh (Lime green) hoặc nâu xỉn."
    }
}

SCIENTIFIC_HACKS = [
    "Quy Tắc 1/3 (Rule of Thirds): Cơ thể không bao giờ được chia cắt ở giữa (1:1). Cắt ngang ở 1/3 hoặc 2/3 chiều dài cơ thể luôn tạo cảm giác cao ráo và thời trang hơn.",
    "Trọng lượng thị giác (Visual Weight): Các màu tối, chất liệu thô/dày (da, denim rập), họa tiết to có xu hướng 'kéo' mắt người nhìn xuống và tạo cảm giác phình to. Phải dùng nó ở nơi cần tăng thể tích, không dùng ở nơi cần che giấu.",
    "Bất đối xứng (Asymmetry): Phá vỡ sự rập khuôn bằng cách xắn 1 bên tay áo, sơ-vin nửa vạt (French tuck), hoặc buông thõng 1 bên vai áo khoác. Nó tạo chuyển động (Movement) và tính 'Effortless' (đẹp không gắng gượng).",
    "Tương phản chất liệu (Texture Clash): Mix đồ lụa/voan mềm mại với da thô/denim xù xì. Sự mâu thuẫn này là định nghĩa của thời trang cao cấp (High fashion)."
]

def generate_dynamic_prompt(user_profile, selected_tags):
    philosophy = []
    if user_profile:
        bt = user_profile.get('body_type', '')
        bp = user_profile.get('body_proportions', '')
        st = user_profile.get('skin_tone', '')
        shoulder_slope = user_profile.get('shoulder_slope', '')
        chest_profile = user_profile.get('chest_profile', '')
        leg_alignment = user_profile.get('leg_alignment', '')
        
        # Mapping to extract philosophy
        for key, val in FASHION_PHILOSOPHY['body_type'].items():
            if bt and (bt.lower() in key.lower() or key.lower() in bt.lower()):
                philosophy.append(f"- Hình thể ({bt}): {val}")
                break
                
        for key, val in FASHION_PHILOSOPHY['body_proportions'].items():
            if bp and (bp.lower() in key.lower() or key.lower() in bp.lower()):
                philosophy.append(f"- Tỷ lệ cơ thể ({bp}): {val}")
                break
                
        for field, value in [('shoulder_slope', shoulder_slope), ('chest_profile', chest_profile), ('leg_alignment', leg_alignment)]:
            if value in FASHION_PHILOSOPHY['special_features']:
                philosophy.append(f"- Đặc điểm {field} ({value}): {FASHION_PHILOSOPHY['special_features'][value]}")

        for key, val in FASHION_PHILOSOPHY['skin_tone'].items():
            if st and (st.lower() in key.lower() or key.lower() in st.lower()):
                philosophy.append(f"- Màu da ({st}): {val}")
                break
                
    philosophy_text = "\n".join(philosophy) if philosophy else "Khách hàng không cung cấp rõ thông số, hãy tự suy luận các nguyên tắc tỷ lệ."
    tags_text = ", ".join(selected_tags) if selected_tags else "Tự do sáng tạo"
    hacks_text = "\n".join([f"- {h}" for h in SCIENTIFIC_HACKS])
    
    prompt = f"""Bạn không phải là một cỗ máy AI rập khuôn. Bạn là Master Stylist hàng đầu - một bậc thầy về Khoa học Thời Trang (Tỷ lệ cơ thể, Trọng lượng thị giác, và Phân tích màu sắc). 
Đừng đưa ra lời khuyên chung chung. Mọi sự kết hợp của bạn phải dựa trên TỐÁN HỌC CỦA THỊ GIÁC và SỰ THẤU HIỂU CƠ THỂ con người.

[HỒ SƠ KHÁCH HÀNG]
{philosophy_text}

[TÌNH HUỐNG/PHONG CÁCH]
{tags_text}

[CÁC NGUYÊN TẮC KHOA HỌC THỜI TRANG CẦN ÁP DỤNG]
{hacks_text}

QUY TẮC HOẠT ĐỘNG (MUST FOLLOW):
1. Khách hàng sẽ cung cấp một [TỦ ĐỒ] (Wardrobe) gồm nhiều món đồ. 
2. Không tiết lộ chain-of-thought. Chỉ trình bày các bằng chứng ngắn gọn, có thể kiểm chứng: dữ liệu đầu vào, nguyên tắc đã áp dụng, lựa chọn phối đồ và độ không chắc chắn.
3. Không bao giờ chọn đồ ngẫu nhiên. Lập luận rõ TẠI SAO món áo A đi với quần B lại cứu vãn được "Lưng dài" hoặc "Da ngăm" dựa trên các nguyên tắc khoa học.
4. Nếu thiếu dữ liệu hoặc không chắc chắn, nói rõ "chưa đủ dữ liệu" thay vì tự bịa. Không đưa nhận định y khoa, giá trị con người hoặc body-shaming.
5. Trả lời bằng Tiếng Việt tự nhiên, sắc sảo, tự tin.

FORMAT TRẢ LỜI BẮT BUỘC:

### 1. PHÂN TÍCH BẢN THỂ (KHOA HỌC)
(Nhận xét trực diện về khung xương, tỷ lệ cơ thể và màu da của khách hàng. Chỉ ra ngay đâu là bài toán thị giác cần giải quyết - vd: "Cần kéo trọng lượng thị giác lên trên để giấu hông").

### 2. GIẢI PHÁP TỪ TỦ ĐỒ (MIX & MATCH)
(Bắt buộc CHỌN ĐÍCH DANH các món có trong danh sách TỦ ĐỒ mà khách hàng cung cấp. Nếu tủ đồ trống hoặc thiếu món, hãy dũng cảm tư vấn một kiểu dáng khác nên mua thêm. Phân tích rõ chiếc áo X và chiếc quần Y đã làm thay đổi Tỷ lệ cơ thể ra sao.)

### 3. ĐIỂM NHẤN "PHÁ LUẬT" (STYLING HACK)
(Hướng dẫn khách hàng một mẹo ứng dụng ngay lập tức: ví dụ xắn tay áo, sơ-vin một nửa, hoặc mở 2 cúc ngực... để trang phục không bị cứng đơ mà mang hơi thở thời trang cao cấp.)
"""
    return prompt
