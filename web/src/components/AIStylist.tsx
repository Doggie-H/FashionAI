'use client';

import { useEffect, useMemo, useState } from 'react';
import BodyAvatar3D, { BodyMeasurements, FaceShapeType, GenderType, LightingFilter, TryOnGarmentBinding, ViewPreset } from './BodyAvatar3D';

const API_URL = 'http://127.0.0.1:8000';

const initialMeasurements: BodyMeasurements = {
  height: 170, shoulder: 42, bust: 88, waist: 72, hip: 94,
  thigh: 54, calf: 36, bicep: 28, neck: 36, inseam: 78,
  shoulder_slope: 'straight', chest_profile: 'full', leg_alignment: 'straight',
};

type NumericMeasurementKey = 'height' | 'shoulder' | 'bust' | 'waist' | 'hip' | 'thigh' | 'calf' | 'bicep' | 'neck' | 'inseam';

type WardrobeItem = {
  id: string;
  import_id: string;
  category: 'top' | 'bottom' | 'dress' | 'outerwear' | 'footwear' | 'belt' | 'accessory';
  name: string;
  image_url?: string;
  styles?: string[];
  color_family?: string;
  material?: string;
  silhouette?: string;
  is_wearing: boolean;
  binding?: TryOnGarmentBinding;
};

const numericFields: NumericMeasurementKey[] = [
  'height', 'shoulder', 'bust', 'waist', 'hip', 'thigh', 'calf', 'bicep', 'neck', 'inseam'
];

const fieldLabels: Record<NumericMeasurementKey, string> = {
  height: 'Chiều cao',
  shoulder: 'Rộng vai',
  bust: 'Vòng ngực',
  waist: 'Vòng eo',
  hip: 'Vòng hông / Mông',
  thigh: 'Vòng bắp đùi',
  calf: 'Vòng bắp chân',
  bicep: 'Vòng bắp tay',
  neck: 'Vòng cổ',
  inseam: 'Dài chân (Inseam)',
};

const fieldUnits: Record<NumericMeasurementKey, string> = {
  height: 'cm', shoulder: 'cm', bust: 'cm', waist: 'cm', hip: 'cm',
  thigh: 'cm', calf: 'cm', bicep: 'cm', neck: 'cm', inseam: 'cm',
};

const fieldRanges: Record<NumericMeasurementKey, { min: number; max: number; step: number }> = {
  height: { min: 145, max: 205, step: 0.5 },
  shoulder: { min: 32, max: 56, step: 0.5 },
  bust: { min: 65, max: 125, step: 0.5 },
  waist: { min: 50, max: 115, step: 0.5 },
  hip: { min: 70, max: 135, step: 0.5 },
  thigh: { min: 40, max: 80, step: 0.5 },
  calf: { min: 26, max: 52, step: 0.5 },
  bicep: { min: 20, max: 48, step: 0.5 },
  neck: { min: 28, max: 50, step: 0.5 },
  inseam: { min: 60, max: 98, step: 0.5 },
};

// 20 MẪU TÓC NAM THỊNH HÀNH
export const MEN_HAIRSTYLES = [
  'Side Part 7/3 Hiện Đại',
  'Two Block Hàn Quốc',
  'Undercut Vuốt Ngược',
  'Textured Crop Trẻ Trung',
  'Pompadour Cổ Điển',
  'Buzz Cut / Đầu Đinh Nam Tính',
  'Mullet Modern Cá Tính',
  'French Crop Ngắn Gọn',
  'Ivy League Quý Ông',
  'Wolf Cut Nam Phóng Khoáng',
  'Short Quiff Năng Động',
  'Layer Hàn Quốc Rủ Nhẹ',
  'Curly Fade Uốn Xoăn',
  'Man Bun Tóc Búi Nghệ Sĩ',
  'Comma Hair (Tóc Dấu Phẩy)',
  'Top Knot Hiện Đại',
  'Taper Fade Chuẩn Barber',
  'Caesar Cut Gai Góc',
  'Dreadlocks Ngắn Phố Thị',
  'Slicked Back Wall Street',
];

// 20 MẪU TÓC NỮ THỊNH HÀNH
export const WOMEN_HAIRSTYLES = [
  'Layer Bob Ngang Vai',
  'Wolf Cut Nữ Cá Tính',
  'Hime Cut Nhật Bản',
  'Butterfly Cut Bồng Bềnh',
  'Pixie Cut Táo Bạo',
  'Curtain Bangs Mái Bay',
  'Long Wavy Sóng Nước Dài',
  'Sleek Straight Thẳng Tự Nhiên',
  'Bob Cụp Cổ Điển',
  'Shag Hair Thập Niên 70s',
  'French Bob Kiểu Pháp',
  'U-Shape Layer Dịu Dàng',
  'Mullet Nữ Layer Nổi Bật',
  'Tóc Ngắn Uốn Xoăn Sóng Lơi',
  'Tóc Mái Thưa Ngọt Ngào',
  'Tóc Mái Bằng Dày Style',
  'Tóc Đuôi Ngựa High Ponytail',
  'Tóc Búi Lơi Messy Bun',
  'Tóc Tết Kiểu Pháp',
  'Tóc Tép Baby Braids Y2K',
];

// 20 MẪU KÍNH CẬN THỊNH HÀNH
export const PRESCRIPTION_GLASSES = [
  'Không đeo kính',
  'Gọng Tròn Kim Loại Hàn Quốc',
  'Gọng Vuông Nhựa Acetate Đen',
  'Gọng Browline / Clubmaster',
  'Gọng Đa Giác (Hexagon) Mảnh',
  'Gọng Mắt Mèo Cat-Eye Trẻ Trung',
  'Gọng Chữ Nhật Cổ Điển',
  'Gọng Trong Suốt Minimalist Clear',
  'Gọng Bầu Dục Nhẹ Nhàng Oval',
  'Gọng Aviator Kim Loại Cận',
  'Gọng Không Viền Rimless Tinh Tế',
  'Gọng Nửa Viền Semi-Rimless',
  'Gọng Bát Giác Octagon Phá Cách',
  'Gọng Titan Siêu Nhẹ Titanium',
  'Gọng Đồi Mồi Tortoiseshell',
  'Gọng Vuông Dày Chunky Y2K',
  'Gọng Vuông Bầu Soft Square',
  'Gọng Oversized Hàn Quốc',
  'Gọng Kim Loại Mạ Vàng Cổ Điển',
  'Gọng Tròn Nhựa Dẻo Thời Trang',
  'Gọng Kim Loại Matte Black',
];

// 20 MẪU KÍNH RÂM & KÍNH KIỂU
export const SUNGLASSES_STYLES = [
  'Wayfarer Đen Cổ Điển',
  'Aviator Phi Công Giọt Nước',
  'Kính Râm Mắt Mèo Cat-Eye Đen Bóng',
  'Kính Râm Chữ Nhật Y2K Bản Hẹp',
  'Kính Râm Tròn Retro John Lennon',
  'Kính Râm Shield Thể Thao Tương Lai',
  'Kính Râm Gradient Nâu Trà',
  'Kính Râm Tráng Gương Bạc Sành Điệu',
  'Kính Râm Oversized Vuông Diva',
  'Kính Râm Oval Vintage Thập Niên 90s',
  'Kính Râm Đa Giác Geometric Viền Kim Loại',
  'Kính Râm Không Viền Phong Cách Matrix',
  'Kính Râm Gọng Đồi Mồi Cao Cấp',
  'Kính Râm Tròng Vàng Vintage Night-Vision',
  'Kính Râm Clip-on Tiện Lợi Tháo Rời',
  'Kính Râm Clubmaster Cổ Điển Retro',
  'Kính Râm Tiny Glasses Thời Thượng',
  'Kính Râm Cánh Bướm Butterfly',
  'Kính Râm Flat-Top Đương Đại',
  'Kính Râm Gọng Trắng Nổi Bật Siêu Hot',
];

// 7 DÁNG KHUÔN MẶT
export const FACE_SHAPES: { id: FaceShapeType; name: string; desc: string; icon: string }[] = [
  { id: 'oval', name: 'Trái Xoan (Oval)', desc: 'Tỷ lệ cân đối lý tưởng, hợp mọi phong cách', icon: '🥚' },
  { id: 'round', name: 'Mặt Tròn (Round)', desc: 'Gò má đầy, cằm tròn mềm mại đáng yêu', icon: '⚪' },
  { id: 'square', name: 'Mặt Vuông (Square)', desc: 'Xương hàm sắc nét, góc cạnh quyền lực', icon: '⬜' },
  { id: 'heart', name: 'Trái Tim (Heart)', desc: 'Trán rộng, cằm nhọn V-line thanh tú', icon: '💖' },
  { id: 'diamond', name: 'Kim Cương (Diamond)', desc: 'Gò má cao nổi bật, trán & cằm thon', icon: '💎' },
  { id: 'oblong', name: 'Mặt Dài (Oblong)', desc: 'Chiều dài nổi bật, đường nét quý phái', icon: '📐' },
  { id: 'triangle', name: 'Tam Giác (Triangle)', desc: 'Quai hàm rộng, thu nhỏ dần về trán', icon: '🔺' },
];

const BODY_PRESETS_FEMALE: { name: string; desc: string; values: Partial<BodyMeasurements> }[] = [
  {
    name: 'Dáng Quả Lê',
    desc: 'Hông đùi nở nang, vai nhỏ',
    values: { height: 162, shoulder: 38, bust: 84, waist: 68, hip: 100, thigh: 58, calf: 37, inseam: 74, shoulder_slope: 'sloped' },
  },
  {
    name: 'Đồng Hồ Cát',
    desc: 'Ngực hông nở, eo thon quyến rũ',
    values: { height: 166, shoulder: 41, bust: 92, waist: 62, hip: 94, thigh: 53, calf: 35, inseam: 77, chest_profile: 'full' },
  },
  {
    name: 'Dáng Quả Táo',
    desc: 'Vòng 2 đầy đặn, ngực nở',
    values: { height: 164, shoulder: 41, bust: 94, waist: 84, hip: 90, thigh: 51, calf: 34, inseam: 76, chest_profile: 'full' },
  },
  {
    name: 'Dáng Chữ Nhật',
    desc: 'Thanh mảnh, số đo đều đặn',
    values: { height: 168, shoulder: 39, bust: 82, waist: 72, hip: 86, thigh: 49, calf: 33, inseam: 79, chest_profile: 'flat' },
  },
  {
    name: 'Tam Giác Ngược',
    desc: 'Khung vai rộng, hông thon gọn',
    values: { height: 172, shoulder: 45, bust: 90, waist: 70, hip: 88, thigh: 50, calf: 34, inseam: 80, shoulder_slope: 'straight' },
  },
  {
    name: 'Dáng Thấp Bé (Petite)',
    desc: 'Dưới 1m58, cần tôn tỷ lệ chân',
    values: { height: 154, shoulder: 36, bust: 80, waist: 62, hip: 86, thigh: 48, calf: 32, inseam: 68, shoulder_slope: 'sloped' },
  },
];

const BODY_PRESETS_MALE: { name: string; desc: string; values: Partial<BodyMeasurements> }[] = [
  {
    name: 'Tam Giác Ngược V-Taper',
    desc: 'Vai ngực vạm vỡ, eo thon',
    values: { height: 178, shoulder: 48, bust: 98, waist: 74, hip: 92, thigh: 56, calf: 38, bicep: 34, inseam: 82, shoulder_slope: 'straight' },
  },
  {
    name: 'Dáng Hình Chữ Nhật',
    desc: 'Thân hình thanh mảnh cân đối',
    values: { height: 175, shoulder: 43, bust: 90, waist: 76, hip: 90, thigh: 52, calf: 36, bicep: 30, inseam: 80, chest_profile: 'flat' },
  },
  {
    name: 'Dáng Quả Táo / Bụng Bia',
    desc: 'Vòng eo đậm, vai ngực rộng',
    values: { height: 174, shoulder: 45, bust: 96, waist: 88, hip: 94, thigh: 55, calf: 37, bicep: 32, inseam: 78, chest_profile: 'full' },
  },
  {
    name: 'Dáng Quả Lê Nam',
    desc: 'Phần đùi hông dày dặn',
    values: { height: 172, shoulder: 41, bust: 88, waist: 78, hip: 98, thigh: 60, calf: 39, bicep: 29, inseam: 77, shoulder_slope: 'sloped' },
  },
];

export default function AIStylist() {
  const [gender, setGender] = useState<GenderType>('female');
  const [faceShape, setFaceShape] = useState<FaceShapeType>('oval');
  const [hairStyle, setHairStyle] = useState<string>('Layer Bob Ngang Vai');
  const [glassesType, setGlassesType] = useState<string>('Không đeo kính');

  const [measurements, setMeasurements] = useState<BodyMeasurements>(initialMeasurements);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [animationEnabled, setAnimationEnabled] = useState(false);
  const [outfitStyle, setOutfitStyle] = useState<'neutral' | 'navy' | 'burgundy' | 'emerald'>('neutral');
  const [lightingFilter, setLightingFilter] = useState<LightingFilter>('studio');
  const [viewPreset, setViewPreset] = useState<ViewPreset>('front');
  
  // Tủ đồ cá nhân (Wardrobe)
  const [wardrobe, setWardrobe] = useState<WardrobeItem[]>([]);
  const [importingGarment, setImportingGarment] = useState(false);
  const [activeTab, setActiveTab] = useState<'appearance' | 'body' | 'wardrobe' | 'goals'>('appearance');
  
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/stylist/tags`)
      .then((response) => response.json())
      .then((data) => setTags(data.tags || []))
      .catch(() => setError('Không tải được danh sách nhu cầu từ backend.'));
  }, []);

  const bodyPresets = gender === 'male' ? BODY_PRESETS_MALE : BODY_PRESETS_FEMALE;
  const currentHairstyles = gender === 'male' ? MEN_HAIRSTYLES : WOMEN_HAIRSTYLES;

  const handleGenderChange = (g: GenderType) => {
    setGender(g);
    if (g === 'male') {
      setHairStyle('Side Part 7/3 Hiện Đại');
      setMeasurements((cur) => ({
        ...cur,
        shoulder: 46, bust: 94, waist: 78, hip: 92, thigh: 55, calf: 37, bicep: 32, neck: 38,
      }));
    } else {
      setHairStyle('Layer Bob Ngang Vai');
      setMeasurements((cur) => ({
        ...cur,
        shoulder: 40, bust: 88, waist: 68, hip: 94, thigh: 53, calf: 35, bicep: 26, neck: 34,
      }));
    }
  };

  const bodyShapeHint = useMemo(() => {
    const { shoulder, bust, waist, hip } = measurements;
    if (hip - waist >= 22 && hip > shoulder + 4) return 'Dáng quả lê (Hông đùi nở)';
    if (shoulder > hip + 5) return 'Dáng tam giác ngược (Vai rộng)';
    if (waist >= hip - 8) return 'Dáng quả táo (Vòng 2 đầy)';
    if (bust - waist >= 20 && hip - waist >= 20) return 'Dáng đồng hồ cát (Cân đối)';
    return 'Dáng chữ nhật / Thanh mảnh';
  }, [measurements]);

  const activeBindings = useMemo(() => {
    return wardrobe.filter((item) => item.is_wearing && item.binding).map((item) => item.binding!);
  }, [wardrobe]);

  const updateMeasurement = (field: keyof BodyMeasurements, value: string) => {
    if (field === 'shoulder_slope' || field === 'chest_profile' || field === 'leg_alignment') {
      setMeasurements((current) => ({ ...current, [field]: value }));
      return;
    }
    const next = Number(value);
    if (!Number.isNaN(next)) setMeasurements((current) => ({ ...current, [field]: next }));
  };

  const applyPreset = (preset: typeof BODY_PRESETS_FEMALE[0]) => {
    setMeasurements((current) => ({ ...current, ...preset.values }));
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]);
  };

  const handleGarmentImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImportingGarment(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const importResponse = await fetch(`${API_URL}/phase-b/garment-imports`, { method: 'POST', body: form });
      const importData = await importResponse.json();
      if (!importResponse.ok) throw new Error(importData.detail || 'Không thể import garment.');
      
      const importId = importData.manifest.import_id;
      
      let taggingMeta: any = null;
      try {
        const taggingResponse = await fetch(`${API_URL}/phase-b/garment-imports/${importId}/semantic-tags`, { method: 'POST' });
        const taggingData = await taggingResponse.json();
        taggingMeta = taggingData.manifest?.analysis?.semantic_tagging?.candidate_metadata;
      } catch (err) {
        console.warn('Semantic tagger fallback:', err);
      }

      const bindingsResponse = await fetch(`${API_URL}/phase-b/try-on-bindings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ import_ids: [importId] }),
      });
      const bindings = await bindingsResponse.json();
      const bindingObj: TryOnGarmentBinding = bindingsResponse.ok && bindings[0] ? (bindings[0] as TryOnGarmentBinding) : {
        import_id: importId,
        category: 'top',
        render_mode: 'canonical_proxy',
        quality_status: 'approved',
      };

      const newItem: WardrobeItem = {
        id: `item-${Date.now()}`,
        import_id: importId,
        category: bindingObj.category,
        name: file.name.replace(/\.[^/.]+$/, ''),
        image_url: URL.createObjectURL(file),
        styles: taggingMeta?.styles || ['Casual', 'Modern'],
        color_family: taggingMeta?.color_family || 'Neutral',
        material: taggingMeta?.material || 'Vải hỗn hợp',
        silhouette: taggingMeta?.silhouette || 'Regular Fit',
        is_wearing: true,
        binding: bindingObj,
      };

      setWardrobe((current) => [
        ...current.map((item) => item.category === newItem.category ? { ...item, is_wearing: false } : item),
        newItem,
      ]);
      
      setActiveTab('wardrobe');
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : 'Import garment thất bại.');
    } finally {
      setImportingGarment(false);
      event.target.value = '';
    }
  };

  const toggleWearItem = (itemId: string) => {
    setWardrobe((current) => {
      const target = current.find((i) => i.id === itemId);
      if (!target) return current;
      const willWear = !target.is_wearing;
      return current.map((item) => {
        if (item.id === itemId) return { ...item, is_wearing: willWear };
        if (willWear && item.category === target.category) return { ...item, is_wearing: false };
        return item;
      });
    });
  };

  const removeWardrobeItem = (itemId: string) => {
    setWardrobe((current) => current.filter((i) => i.id !== itemId));
  };

  const handleSubmit = async () => {
    if (selectedTags.length === 0) {
      setError('Vui lòng chọn ít nhất một mục tiêu/nhu cầu phối đồ.');
      setActiveTab('goals');
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/stylist/wardrobe-recommend/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          measurements: {
            ...measurements,
            gender,
            face_shape: faceShape,
            hair_style: hairStyle,
            glasses_type: glassesType,
          },
          selected_tags: selectedTags,
          wardrobe_items: wardrobe.map((item) => ({
            id: item.id,
            category: item.category,
            name: item.name,
            styles: item.styles,
            color: item.color_family,
            material: item.material,
            is_wearing: item.is_wearing,
          })),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Không thể tạo tư vấn.');
      setResult(data.data.ai_reasoning_and_recommendation);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Đã có lỗi xảy ra.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="w-full max-w-7xl mx-auto p-4 md:p-8 font-sans">
      {/* Header */}
      <header className="mb-6 max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 border border-indigo-200/60 px-3.5 py-1 text-xs font-bold text-indigo-700 mb-3 shadow-sm">
          <span>✨</span> 3D AI Stylist & Granular Body Studio
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          Trợ Lý Tạo Mẫu AI & Thử Đồ 3D
        </h1>
        <p className="mt-2 text-sm md:text-base text-slate-600">
          Mô phỏng hình thể 3D liền khối chính xác theo từng bộ phận cơ thể. Tùy chọn 40 mẫu tóc, 40 kiểu kính, 7 dáng mặt và phối đồ thông minh.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* LEFT COLUMN: 3D MANNEQUIN & STUDIO CONTROLS (5 Cols) */}
        <section className="lg:col-span-5 space-y-4">
          <div className="sticky top-6">
            <BodyAvatar3D
              measurements={measurements}
              gender={gender}
              faceShape={faceShape}
              hairStyle={hairStyle}
              glassesType={glassesType}
              autoRotate={autoRotate}
              outfitStyle={outfitStyle}
              animationEnabled={animationEnabled}
              garmentBindings={activeBindings}
              viewPreset={viewPreset}
              lightingFilter={lightingFilter}
            />

            {/* 3D Tools Controls Bar */}
            <div className="mt-4 rounded-3xl border border-slate-200/80 bg-white/90 p-4 shadow-sm backdrop-blur space-y-3">
              {/* Lighting Filters */}
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block mb-2">Bộ Lọc Ánh Sáng Studio</span>
                <div className="grid grid-cols-5 gap-1.5">
                  {(['studio', 'sunset', 'cyberpunk', 'minimalist', 'vintage'] as LightingFilter[]).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setLightingFilter(f)}
                      className={`rounded-xl py-1.5 text-xs font-bold capitalize transition ${lightingFilter === f ? 'bg-indigo-600 text-white shadow' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                    >
                      {f === 'studio' ? 'Studio' : f === 'sunset' ? 'Hoàng Hôn' : f === 'cyberpunk' ? 'Cyber' : f === 'minimalist' ? 'Tối Giản' : 'Vintage'}
                    </button>
                  ))}
                </div>
              </div>

              {/* 360 Camera View Presets */}
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block mb-2">Góc Quay Camera 360°</span>
                <div className="grid grid-cols-7 gap-1">
                  {([
                    { id: 'front', label: 'Chính diện' },
                    { id: 'face', label: 'Khuôn mặt' },
                    { id: 'upper', label: 'Cận trên' },
                    { id: 'lower', label: 'Cận dưới' },
                    { id: 'side', label: 'Ngang' },
                    { id: 'back', label: 'Sau lưng' },
                    { id: 'free', label: 'Tự do' },
                  ] as { id: ViewPreset; label: string }[]).map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      onClick={() => setViewPreset(v.id)}
                      className={`rounded-xl py-1 text-[10px] font-semibold transition ${viewPreset === v.id ? 'bg-slate-900 text-white shadow' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick Action Toggles */}
              <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-xs">
                <label className="flex items-center gap-2 font-medium text-slate-700 cursor-pointer">
                  <input type="checkbox" checked={autoRotate} onChange={(e) => setAutoRotate(e.target.checked)} className="rounded text-indigo-600" />
                  <span>Xoay tự động</span>
                </label>
                <label className="flex items-center gap-2 font-medium text-slate-700 cursor-pointer">
                  <input type="checkbox" checked={animationEnabled} onChange={(e) => setAnimationEnabled(e.target.checked)} className="rounded text-indigo-600" />
                  <span>Chuyển động thở nhẹ</span>
                </label>
              </div>
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: 4 TABS (Appearance, Body, Wardrobe, Goals) (7 Cols) */}
        <section className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 md:p-8 shadow-sm">
          {/* TAB BAR */}
          <div className="flex border-b border-slate-200 mb-6 gap-2 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setActiveTab('appearance')}
              className={`pb-3 text-xs md:text-sm font-bold transition border-b-2 px-3 whitespace-nowrap ${activeTab === 'appearance' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
            >
              1. Diện Mạo & Phụ Kiện
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('body')}
              className={`pb-3 text-xs md:text-sm font-bold transition border-b-2 px-3 whitespace-nowrap ${activeTab === 'body' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
            >
              2. Số Đo Từng Bộ Phận
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('wardrobe')}
              className={`pb-3 text-xs md:text-sm font-bold transition border-b-2 px-3 whitespace-nowrap flex items-center gap-1.5 ${activeTab === 'wardrobe' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
            >
              <span>3. Tủ Đồ Của Tôi</span>
              {wardrobe.length > 0 && (
                <span className="rounded-full bg-indigo-100 text-indigo-700 px-2 py-0.2 text-[11px]">{wardrobe.length}</span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('goals')}
              className={`pb-3 text-xs md:text-sm font-bold transition border-b-2 px-3 whitespace-nowrap ${activeTab === 'goals' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
            >
              4. Mục Tiêu & Phối Đồ
            </button>
          </div>

          {/* TAB 1: APPEARANCE (GENDER, FACE SHAPE, HAIRSTYLE, GLASSES) */}
          {activeTab === 'appearance' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Gender Toggle */}
              <div>
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2.5">1. Chọn Giới Tính Người Mẫu</h3>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => handleGenderChange('female')}
                    className={`rounded-2xl border p-3.5 flex items-center justify-center gap-2 font-bold text-sm transition ${gender === 'female' ? 'border-indigo-600 bg-indigo-50/70 text-indigo-700 shadow-sm ring-2 ring-indigo-200' : 'border-slate-200 bg-slate-50/60 text-slate-700 hover:bg-slate-100'}`}
                  >
                    <span>👩 Nữ (Women)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleGenderChange('male')}
                    className={`rounded-2xl border p-3.5 flex items-center justify-center gap-2 font-bold text-sm transition ${gender === 'male' ? 'border-indigo-600 bg-indigo-50/70 text-indigo-700 shadow-sm ring-2 ring-indigo-200' : 'border-slate-200 bg-slate-50/60 text-slate-700 hover:bg-slate-100'}`}
                  >
                    <span>👨 Nam (Men)</span>
                  </button>
                </div>
              </div>

              {/* Face Shape Picker */}
              <div className="border-t border-slate-100 pt-5">
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2.5">2. Dáng Khuôn Mặt</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {FACE_SHAPES.map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setFaceShape(f.id)}
                      className={`rounded-2xl border p-2.5 text-left transition ${faceShape === f.id ? 'border-indigo-600 bg-indigo-50/80 ring-2 ring-indigo-200 shadow-sm' : 'border-slate-200 bg-slate-50/50 hover:bg-slate-100'}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <span>{f.icon}</span>
                        <p className="text-xs font-bold text-slate-900">{f.name}</p>
                      </div>
                      <p className="text-[10px] text-slate-500 line-clamp-1">{f.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Hairstyle Picker (20 Trending Styles) */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex justify-between items-center mb-2.5">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    3. Mẫu Tóc Thịnh Hành ({currentHairstyles.length} kiểu {gender === 'male' ? 'Nam' : 'Nữ'})
                  </h3>
                  <span className="text-xs font-semibold text-indigo-600">{hairStyle}</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1">
                  {currentHairstyles.map((style) => (
                    <button
                      key={style}
                      type="button"
                      onClick={() => setHairStyle(style)}
                      className={`rounded-xl border px-3 py-2 text-left text-xs font-semibold transition ${hairStyle === style ? 'border-indigo-600 bg-indigo-600 text-white shadow' : 'border-slate-200 bg-slate-50/80 text-slate-700 hover:bg-slate-100'}`}
                    >
                      {style}
                    </button>
                  ))}
                </div>
              </div>

              {/* Eyewear Glasses Picker (20 Prescription + 20 Sunglasses) */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex justify-between items-center mb-2.5">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    4. Kính Cận & Kính Râm (40 Kiểu Kính)
                  </h3>
                  <span className="text-xs font-semibold text-indigo-600">{glassesType}</span>
                </div>

                <div className="space-y-3">
                  <div>
                    <span className="text-[11px] font-bold text-slate-500 block mb-1.5">👓 Kính Cận (Prescription Glasses)</span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-36 overflow-y-auto pr-1">
                      {PRESCRIPTION_GLASSES.map((g) => (
                        <button
                          key={g}
                          type="button"
                          onClick={() => setGlassesType(g)}
                          className={`rounded-xl border px-2.5 py-1.5 text-left text-[11px] font-medium transition ${glassesType === g ? 'border-indigo-600 bg-indigo-600 text-white shadow' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'}`}
                        >
                          {g}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <span className="text-[11px] font-bold text-slate-500 block mb-1.5">🕶️ Kính Râm & Kính Kiểu (Fashion Sunglasses)</span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-36 overflow-y-auto pr-1">
                      {SUNGLASSES_STYLES.map((g) => (
                        <button
                          key={g}
                          type="button"
                          onClick={() => setGlassesType(g)}
                          className={`rounded-xl border px-2.5 py-1.5 text-left text-[11px] font-medium transition ${glassesType === g ? 'border-indigo-600 bg-indigo-600 text-white shadow' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'}`}
                        >
                          {g}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: GRANULAR BODY MEASUREMENTS (ISOLATED SLIDERS) */}
          {activeTab === 'body' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Quick Presets */}
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Chọn Nhanh Dáng Người Mẫu</h3>
                  <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">{bodyShapeHint}</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  {bodyPresets.map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => applyPreset(preset)}
                      className="rounded-2xl border border-slate-200 bg-slate-50/50 p-3 text-left transition hover:border-indigo-500 hover:bg-indigo-50/40 group"
                    >
                      <p className="text-xs font-bold text-slate-900 group-hover:text-indigo-700">{preset.name}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{preset.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Sliders for exact granular body dimensions (ISOLATED CONTROL) */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Thông Số Từng Bộ Phận Cơ Thể (cm)</h3>
                  <span className="text-[11px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                    ✓ Độc lập từng phân vùng (Hông, Đùi, Bắp chân không bị dính chùm)
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {numericFields.map((field) => (
                    <label key={field} className="block bg-slate-50 p-3.5 rounded-2xl border border-slate-200/70 hover:border-indigo-200 transition">
                      <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1.5">
                        <span>{fieldLabels[field]}</span>
                        <span className="text-indigo-600 font-bold bg-white px-2 py-0.5 rounded-md border border-slate-200 shadow-sm">
                          {measurements[field]} {fieldUnits[field]}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={fieldRanges[field].min}
                        max={fieldRanges[field].max}
                        step={fieldRanges[field].step}
                        value={measurements[field]}
                        onChange={(e) => updateMeasurement(field, e.target.value)}
                        className="w-full accent-indigo-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                      />
                    </label>
                  ))}
                </div>
              </div>

              {/* Posture / Alignment */}
              <div className="border-t border-slate-100 pt-5">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3">Đặc Điểm Khung Xương</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-slate-700">Độ dốc vai</span>
                    <select
                      value={measurements.shoulder_slope}
                      onChange={(e) => updateMeasurement('shoulder_slope', e.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-medium"
                    >
                      <option value="straight">Vai ngang</option>
                      <option value="sloped">Vai xuôi</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-slate-700">Dáng ngực</span>
                    <select
                      value={measurements.chest_profile}
                      onChange={(e) => updateMeasurement('chest_profile', e.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-medium"
                    >
                      <option value="full">Ngực đầy đặn</option>
                      <option value="flat">Ngực thanh mảnh</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-slate-700">Trục chân</span>
                    <select
                      value={measurements.leg_alignment}
                      onChange={(e) => updateMeasurement('leg_alignment', e.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-medium"
                    >
                      <option value="straight">Chân thẳng</option>
                      <option value="bowed">Chân cong nhẹ</option>
                    </select>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: WARDROBE MANAGEMENT */}
          {activeTab === 'wardrobe' && (
            <div className="space-y-6 animate-fadeIn">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-2">Thêm Trang Phục Vào Kho Đồ</h3>
                <p className="text-xs text-slate-500 mb-4">
                  Chụp hoặc tải ảnh áo, quần, váy, áo khoác, giày để AI tự động nhận diện cấu trúc 2D, phân loại Style DNA và chuẩn bị mặc thử 3D.
                </p>
                <label className="flex cursor-pointer items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-indigo-300 bg-indigo-50/60 p-6 text-sm font-bold text-indigo-700 transition hover:bg-indigo-100">
                  <span className="text-2xl">📸</span>
                  <span>{importingGarment ? 'AI đang phân tích trang phục...' : 'Tải Ảnh Món Đồ Lên Kho'}</span>
                  <input className="hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={handleGarmentImport} disabled={importingGarment} />
                </label>
              </div>

              {/* Wardrobe Items List */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Tủ Đồ Của Bạn ({wardrobe.length})</h3>
                  <span className="text-xs text-slate-400">Click &apos;Mặc thử&apos; để đưa lên 3D</span>
                </div>
                {wardrobe.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 p-8 text-center text-slate-400 text-xs">
                    Tủ đồ đang trống. Hãy tải lên vài món đồ yêu thích để AI phân tích và phối trang phục!
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-72 overflow-y-auto pr-1">
                    {wardrobe.map((item) => (
                      <div
                        key={item.id}
                        className={`rounded-2xl border p-3 flex gap-3 items-center transition ${item.is_wearing ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-200' : 'border-slate-200 bg-white'}`}
                      >
                        {item.image_url ? (
                          <img src={item.image_url} alt={item.name} className="w-14 h-14 object-cover rounded-xl border border-slate-200" />
                        ) : (
                          <div className="w-14 h-14 rounded-xl bg-slate-100 flex items-center justify-center text-xl">👗</div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold text-slate-900 truncate">{item.name}</p>
                          <div className="flex flex-wrap gap-1 mt-1">
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 uppercase">{item.category}</span>
                            <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700">{item.styles?.[0] || 'Chic'}</span>
                          </div>
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <button
                            type="button"
                            onClick={() => toggleWearItem(item.id)}
                            className={`rounded-xl px-3 py-1 text-xs font-bold transition ${item.is_wearing ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                          >
                            {item.is_wearing ? 'Đang mặc' : 'Mặc thử'}
                          </button>
                          <button
                            type="button"
                            onClick={() => removeWardrobeItem(item.id)}
                            className="text-[10px] text-slate-400 hover:text-red-500 transition text-center"
                          >
                            Xóa
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: GOALS & AI RECOMMENDATION */}
          {activeTab === 'goals' && (
            <div className="space-y-6 animate-fadeIn">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-2">Chọn Nhu Cầu & Dịp Sự Kiện</h3>
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => toggleTag(tag)}
                      className={`rounded-full px-4 py-2 text-xs font-bold transition ${selectedTags.includes(tag) ? 'bg-indigo-600 text-white shadow-md' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                className="w-full rounded-2xl bg-indigo-600 py-4 text-sm font-bold text-white shadow-xl shadow-indigo-200 transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? 'AI Stylist Đang Phân Tích & Phối Đồ...' : 'Tạo Tư Vấn Phối Đồ Toàn Diện'}
              </button>
            </div>
          )}

          {/* AI RESULT DISPLAY */}
          {result && (
            <div className="mt-8 rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50/50 via-white to-purple-50/30 p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">💡</span>
                <h3 className="text-base font-extrabold text-indigo-950">Tư Vấn Chuyên Sâu Từ AI Stylist</h3>
              </div>
              <div className="prose prose-sm text-slate-700 whitespace-pre-line leading-relaxed">
                {result}
              </div>
            </div>
          )}

          {/* ERROR ALERT */}
          {error && (
            <div className="mt-4 rounded-2xl bg-rose-50 border border-rose-200 p-4 text-xs font-semibold text-rose-700">
              ⚠️ {error}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
