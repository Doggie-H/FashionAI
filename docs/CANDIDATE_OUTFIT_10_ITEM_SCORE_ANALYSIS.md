# Phân tích candidate outfit và điểm số — scenario 10 item

**Nguồn chạy:** `backend/reports/style_session_10_item_scenario.json`.  
**Chính sách:** `owned_only`; toàn bộ item candidate thuộc immutable wardrobe snapshot 10 item.

## Bối cảnh quyết định

| Tín hiệu | Giá trị |
|---|---|
| `occasion` | meeting |
| `preferred_styles` | ['quiet_luxury', 'preppy', 'business'] |
| `intent_tags` | ['professional_presence', 'confidence', 'weather_protection'] |
| `formality_target` | business |
| `style_intensity` | subtle |
| `season` | autumn |
| `weather` | mild |
| `mobility_need` | normal |
| `modesty_preference` | standard |
| `required_slots` | ['base_top', 'bottom'] |
| `optional_slots` | ['outerwear', 'footwear'] |
| `availability_policy` | owned_only |

## Tổng quan candidate

| Hạng | Candidate | Archetype | Điểm | Tổng evidence delta | Khớp total | Confidence |
|---:|---|---|---:|---:|---|---:|
| 1 | gar_beige_knit_polo, gar_cream_pleated_midi_skirt, gar_camel_trench_coat, gar_black_loafer | quiet_luxury, preppy, business | 326.0 | 326.0 | Có | 0.95 |
| 2 | gar_beige_knit_polo, gar_cream_pleated_midi_skirt, gar_camel_trench_coat, gar_white_minimal_sneaker | preppy, quiet_luxury | 303.0 | 303.0 | Có | 0.95 |
| 3 | gar_beige_knit_polo, gar_black_highwaist_trouser, gar_camel_trench_coat, gar_black_loafer | quiet_luxury, business, preppy | 294.0 | 294.0 | Có | 0.95 |

## Candidate 1: `out_beige_knit_polo_cream_pleated_midi_skirt_camel_trench_coat_black_loafer`

Bộ quiet luxury, preppy cho nhu cầu meeting, ưu tiên các item đang có trong kho đồ và các ràng buộc đã chọn.

**Garments:** gar_beige_knit_polo, gar_cream_pleated_midi_skirt, gar_camel_trench_coat, gar_black_loafer  
**Tổng điểm:** 326.0; **confidence:** 0.95; **evidence delta:** 326.0.

| Rule | Điểm gộp | Evidence rút gọn |
|---|---:|---|
| Occasion match (`occasion_match`) | +84.0 | Áo polo len beige phù hợp bối cảnh meeting. / Chân váy midi xếp ly cream phù hợp bối cảnh meeting. / Trench coat camel phù hợp bối cảnh meeting. |
| Season match (`season_match`) | +40.0 | Mùa sử dụng của garment phù hợp context. |
| Style match (`style_match`) | +40.0 | Khớp định hướng style: preppy, quiet luxury. / Khớp định hướng style: preppy. / Khớp định hướng style: quiet luxury. / Khớp định hướng style: chuyên nghiệp. |
| Skeleton contract (`skeleton_compatible`) | +32.0 | Asset có contract phù hợp skeleton avatar hiện tại. |
| Fit preference (`fit_preference`) | +20.0 | Fit intent khớp sở thích người dùng. |
| Formality (`formality_match`) | +18.0 | Mức độ chỉn chu khớp nhu cầu sử dụng. |
| Functional intent (`functional_intent_support`) | +16.0 | Garment hỗ trợ nhu cầu: confidence. / Garment hỗ trợ nhu cầu: professional_presence, weather_protection. / Garment hỗ trợ nhu cầu: professional_presence. |
| Mobility (`mobility_match`) | +16.0 | Mobility support đáp ứng nhu cầu di chuyển. |
| Coverage/modesty (`modesty_match`) | +16.0 | Mức độ coverage đáp ứng modesty preference. |
| Owned wardrobe (`owned_wardrobe_available`) | +12.0 | Garment thuộc kho đồ active của người dùng. |
| pairing_hint (`pairing_hint`) | +12.0 | Áo polo len beige có pairing hint phù hợp với outfit. / Chân váy midi xếp ly cream có pairing hint phù hợp với outfit. / Trench coat camel có pairing hint phù hợp với outfit. / Loafer da đen có pairing hint phù hợp với outfit. |
| Style coherence (`style_coherence`) | +12.0 | Các lớp chính cùng củng cố archetype quiet luxury. |
| Outfit intent coverage (`outfit_intent_coverage`) | +8.0 | Tổ hợp item bao phủ toàn bộ nhu cầu sử dụng đã chọn. |
| Style intensity (`style_intensity_match`) | +8.0 | Mức độ nổi bật của garment khớp lựa chọn người dùng. |
| Color harmony (`color_harmony`) | +6.0 | Outfit dùng nền màu trung tính ổn định để phối các lớp. |
| formality_near_match (`formality_near_match`) | +4.0 | Mức độ chỉn chu lệch một bậc so với mục tiêu. |
| occasion_mismatch (`occasion_mismatch`) | -18.0 | Loafer da đen không phải lựa chọn mặc định cho bối cảnh meeting. |

**Functional highlights:** Hỗ trợ nhu cầu confidence, Hỗ trợ nhu cầu professional presence, Hỗ trợ nhu cầu weather protection.

**Trade-offs:** Garment chưa có weather suitability đã chuẩn hóa.; Loafer da đen không phải lựa chọn mặc định cho bối cảnh meeting.; Mức độ chỉn chu lệch một bậc so với mục tiêu..

**Cần xác nhận:** Avatar dùng calibration heuristic; cần xác nhận độ ôm thực tế khi có 3D fitting..

## Candidate 2: `out_beige_knit_polo_cream_pleated_midi_skirt_camel_trench_coat_white_minimal_sneaker`

Bộ preppy, quiet luxury cho nhu cầu meeting, ưu tiên các item đang có trong kho đồ và các ràng buộc đã chọn.

**Garments:** gar_beige_knit_polo, gar_cream_pleated_midi_skirt, gar_camel_trench_coat, gar_white_minimal_sneaker  
**Tổng điểm:** 303.0; **confidence:** 0.95; **evidence delta:** 303.0.

| Rule | Điểm gộp | Evidence rút gọn |
|---|---:|---|
| Occasion match (`occasion_match`) | +84.0 | Áo polo len beige phù hợp bối cảnh meeting. / Chân váy midi xếp ly cream phù hợp bối cảnh meeting. / Trench coat camel phù hợp bối cảnh meeting. |
| Season match (`season_match`) | +40.0 | Mùa sử dụng của garment phù hợp context. |
| Style match (`style_match`) | +40.0 | Khớp định hướng style: preppy, quiet luxury. / Khớp định hướng style: preppy. / Khớp định hướng style: quiet luxury. |
| Skeleton contract (`skeleton_compatible`) | +32.0 | Asset có contract phù hợp skeleton avatar hiện tại. |
| Fit preference (`fit_preference`) | +20.0 | Fit intent khớp sở thích người dùng. |
| Mobility (`mobility_match`) | +16.0 | Mobility support đáp ứng nhu cầu di chuyển. |
| Coverage/modesty (`modesty_match`) | +16.0 | Mức độ coverage đáp ứng modesty preference. |
| Functional intent (`functional_intent_support`) | +12.0 | Garment hỗ trợ nhu cầu: confidence. / Garment hỗ trợ nhu cầu: professional_presence, weather_protection. |
| Owned wardrobe (`owned_wardrobe_available`) | +12.0 | Garment thuộc kho đồ active của người dùng. |
| pairing_hint (`pairing_hint`) | +12.0 | Áo polo len beige có pairing hint phù hợp với outfit. / Chân váy midi xếp ly cream có pairing hint phù hợp với outfit. / Trench coat camel có pairing hint phù hợp với outfit. / Sneaker trắng tối giản có pairing hint phù hợp với outfit. |
| Style coherence (`style_coherence`) | +12.0 | Các lớp chính cùng củng cố archetype preppy. |
| Formality (`formality_match`) | +9.0 | Mức độ chỉn chu khớp nhu cầu sử dụng. |
| Outfit intent coverage (`outfit_intent_coverage`) | +8.0 | Tổ hợp item bao phủ toàn bộ nhu cầu sử dụng đã chọn. |
| Style intensity (`style_intensity_match`) | +8.0 | Mức độ nổi bật của garment khớp lựa chọn người dùng. |
| Color harmony (`color_harmony`) | +6.0 | Outfit dùng nền màu trung tính ổn định để phối các lớp. |
| formality_near_match (`formality_near_match`) | +4.0 | Mức độ chỉn chu lệch một bậc so với mục tiêu. |
| formality_mismatch (`formality_mismatch`) | -10.0 | Mức độ chỉn chu lệch đáng kể so với mục tiêu. |
| occasion_mismatch (`occasion_mismatch`) | -18.0 | Sneaker trắng tối giản không phải lựa chọn mặc định cho bối cảnh meeting. |

**Functional highlights:** Hỗ trợ nhu cầu confidence, Hỗ trợ nhu cầu professional presence, Hỗ trợ nhu cầu weather protection.

**Trade-offs:** Garment chưa có weather suitability đã chuẩn hóa.; Mức độ chỉn chu lệch một bậc so với mục tiêu.; Mức độ chỉn chu lệch đáng kể so với mục tiêu.; Sneaker trắng tối giản không phải lựa chọn mặc định cho bối cảnh meeting..

**Cần xác nhận:** Avatar dùng calibration heuristic; cần xác nhận độ ôm thực tế khi có 3D fitting..

## Candidate 3: `out_beige_knit_polo_black_highwaist_trouser_camel_trench_coat_black_loafer`

Bộ quiet luxury, chuyên nghiệp cho nhu cầu meeting, ưu tiên các item đang có trong kho đồ và các ràng buộc đã chọn.

**Garments:** gar_beige_knit_polo, gar_black_highwaist_trouser, gar_camel_trench_coat, gar_black_loafer  
**Tổng điểm:** 294.0; **confidence:** 0.95; **evidence delta:** 294.0.

| Rule | Điểm gộp | Evidence rút gọn |
|---|---:|---|
| Occasion match (`occasion_match`) | +56.0 | Áo polo len beige phù hợp bối cảnh meeting. / Trench coat camel phù hợp bối cảnh meeting. |
| Season match (`season_match`) | +40.0 | Mùa sử dụng của garment phù hợp context. |
| Style match (`style_match`) | +40.0 | Khớp định hướng style: preppy, quiet luxury. / Khớp định hướng style: chuyên nghiệp. / Khớp định hướng style: quiet luxury. |
| Skeleton contract (`skeleton_compatible`) | +32.0 | Asset có contract phù hợp skeleton avatar hiện tại. |
| Formality (`formality_match`) | +27.0 | Mức độ chỉn chu khớp nhu cầu sử dụng. |
| Functional intent (`functional_intent_support`) | +24.0 | Garment hỗ trợ nhu cầu: confidence. / Garment hỗ trợ nhu cầu: confidence, professional_presence. / Garment hỗ trợ nhu cầu: professional_presence, weather_protection. / Garment hỗ trợ nhu cầu: professional_presence. |
| Mobility (`mobility_match`) | +16.0 | Mobility support đáp ứng nhu cầu di chuyển. |
| Coverage/modesty (`modesty_match`) | +16.0 | Mức độ coverage đáp ứng modesty preference. |
| Fit preference (`fit_preference`) | +15.0 | Fit intent khớp sở thích người dùng. |
| Owned wardrobe (`owned_wardrobe_available`) | +12.0 | Garment thuộc kho đồ active của người dùng. |
| pairing_hint (`pairing_hint`) | +12.0 | Áo polo len beige có pairing hint phù hợp với outfit. / Quần tây đen cạp cao ống đứng có pairing hint phù hợp với outfit. / Trench coat camel có pairing hint phù hợp với outfit. / Loafer da đen có pairing hint phù hợp với outfit. |
| Style coherence (`style_coherence`) | +12.0 | Các lớp chính cùng củng cố archetype quiet luxury. |
| Style intensity (`style_intensity_match`) | +12.0 | Mức độ nổi bật của garment khớp lựa chọn người dùng. |
| Outfit intent coverage (`outfit_intent_coverage`) | +8.0 | Tổ hợp item bao phủ toàn bộ nhu cầu sử dụng đã chọn. |
| Color harmony (`color_harmony`) | +6.0 | Outfit dùng nền màu trung tính ổn định để phối các lớp. |
| formality_near_match (`formality_near_match`) | +2.0 | Mức độ chỉn chu lệch một bậc so với mục tiêu. |
| occasion_mismatch (`occasion_mismatch`) | -36.0 | Quần tây đen cạp cao ống đứng không phải lựa chọn mặc định cho bối cảnh meeting. / Loafer da đen không phải lựa chọn mặc định cho bối cảnh meeting. |

**Functional highlights:** Hỗ trợ nhu cầu confidence, Hỗ trợ nhu cầu professional presence, Hỗ trợ nhu cầu weather protection.

**Trade-offs:** Garment chưa có weather suitability đã chuẩn hóa.; Loafer da đen không phải lựa chọn mặc định cho bối cảnh meeting.; Mức độ chỉn chu lệch một bậc so với mục tiêu.; Quần tây đen cạp cao ống đứng không phải lựa chọn mặc định cho bối cảnh meeting..

**Cần xác nhận:** Avatar dùng calibration heuristic; cần xác nhận độ ôm thực tế khi có 3D fitting..

## Cách đọc điểm

Điểm là tổng evidence của deterministic policy phiên bản hiện tại, không phải xác suất vật lý hoặc điểm tuyệt đối về gu thẩm mỹ. Confidence phản ánh tính đầy đủ/nhất quán của policy evidence; nó không chứng minh fit thật, chất liệu thật hay sự hài lòng của người dùng. Trade-off phải được hiển thị cho người dùng và là đầu vào cho feedback/reviewer workflow.

> Scenario này là kiểm chứng workflow với kho đồ mô phỏng. Nó không thay thế bộ đánh giá có reviewer, ảnh thật, trang phục thật hoặc dữ liệu preference được cấp quyền.
