import { useState, useRef } from 'react'
import ModelViewer from './ModelViewer'

// Metrics defined inline below

const FACE_SHAPES = [
  'Mặt trái xoan',
  'Mặt tròn',
  'Mặt V-line',
  'Mặt vuông góc cạnh'
]

const SKIN_TONES = [
  'Trắng sáng (Cool undertone)',
  'Trung tính (Neutral)',
  'Ngăm đen (Warm undertone)',
  'Da Vàng (Olive/Asian)'
]

const API_BASE = 'http://127.0.0.1:8000/api'

interface WardrobeItem {
  id: string
  imageUrl: string
  description: any
}

export default function App() {
  const [gender, setGender] = useState('female')
  
  // Profile State
  const [userProfile, setUserProfile] = useState({
    skin_tone: SKIN_TONES[0],
    face_shape: FACE_SHAPES[0],
    height: 170,
    weight: 60,
    shoulder: 40,
    bust: 85,
    waist: 65,
    hips: 90
  })

  // Wardrobe State
  const [wardrobeItems, setWardrobeItems] = useState<WardrobeItem[]>([])
  const [isScanning, setIsScanning] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // AI Advice State
  const [contextTags, setContextTags] = useState('Đi dạo phố, phong cách trẻ trung')
  const [isAdvising, setIsAdvising] = useState(false)
  const [adviceResult, setAdviceResult] = useState<{think: string, content: string} | null>(null)
  const [showThinking, setShowThinking] = useState(false)

  const handleGenderChange = (newGender: string) => {
    setGender(newGender)
    // Adjust base metrics slightly based on gender default
    if (newGender === 'male') {
      setUserProfile(prev => ({...prev, height: 175, weight: 70, shoulder: 45, bust: 95, waist: 80, hips: 95}))
    } else {
      setUserProfile(prev => ({...prev, height: 160, weight: 50, shoulder: 38, bust: 85, waist: 62, hips: 90}))
    }
  }

  const updateMetric = (field: string, value: number) => {
    setUserProfile(prev => ({...prev, [field]: value}))
  }

  // Handle Upload Clothing
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const tempUrl = URL.createObjectURL(file)
    setIsScanning(true)

    const formData = new FormData()
    formData.append('image', file)

    try {
      const res = await fetch(`${API_BASE}/scan_clothing`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      
      if (data.status === 'success') {
        setWardrobeItems(prev => [...prev, {
          id: Date.now().toString(),
          imageUrl: tempUrl,
          description: data.data
        }])
      }
    } catch (err) {
      console.error(err)
      alert('Lỗi quét quần áo. Đảm bảo Backend đang chạy.')
    } finally {
      setIsScanning(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeWardrobeItem = (id: string) => {
    setWardrobeItems(prev => prev.filter(i => i.id !== id))
  }

  // Handle Mix & Match
  const handleMixAndMatch = async () => {
    if (wardrobeItems.length === 0) {
      alert("Hãy thêm ít nhất 1 món đồ vào Tủ Đồ Số trước khi tư vấn.")
      return
    }

    setIsAdvising(true)
    setAdviceResult(null)
    setShowThinking(false)

    const descriptions = wardrobeItems.map(item => item.description)

    const formData = new FormData()
    formData.append('user_profile', JSON.stringify(userProfile))
    formData.append('selected_tags', JSON.stringify([contextTags]))
    formData.append('wardrobe', JSON.stringify(descriptions))

    try {
      const res = await fetch(`${API_BASE}/wardrobe_advice`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      
      if (data.status === 'success') {
        const fullText = data.advice
        // Parse <think> block
        const thinkMatch = fullText.match(/<think>([\s\S]*?)<\/think>/)
        const think = thinkMatch ? thinkMatch[1].trim() : ''
        const content = fullText.replace(/<think>[\s\S]*?<\/think>/, '').trim()
        
        setAdviceResult({ think, content })
      }
    } catch (err) {
      console.error(err)
      alert('Lỗi khi hỏi AI. Đảm bảo Backend đang chạy.')
    } finally {
      setIsAdvising(false)
    }
  }

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-800 font-sans">
      {/* CỘT 1: THÔNG SỐ */}
      <div className="w-1/4 h-full bg-white shadow-xl p-6 flex flex-col gap-5 z-10 overflow-y-auto">
        <div>
          <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-500">
            3D AI Stylist
          </h1>
          <p className="text-sm text-slate-500 mt-1">Khoa học thị giác ứng dụng</p>
        </div>

        <hr className="border-slate-100" />

        <div className="flex flex-col gap-2">
          <label className="font-semibold text-sm">Giới tính</label>
          <div className="flex gap-2">
            <button 
              onClick={() => handleGenderChange('female')}
              className={`flex-1 py-2 rounded-lg font-medium transition-colors border ${gender === 'female' ? 'bg-purple-100 text-purple-700 border-purple-300' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
              👩 Nữ
            </button>
            <button 
              onClick={() => handleGenderChange('male')}
              className={`flex-1 py-2 rounded-lg font-medium transition-colors border ${gender === 'male' ? 'bg-blue-100 text-blue-700 border-blue-300' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
              👨 Nam
            </button>
          </div>
        </div>

        {/* SLIDERS CHỈ SỐ CƠ THỂ */}
        <div className="flex flex-col gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
          <h3 className="font-bold text-sm text-purple-700 flex justify-between">
            Chỉ số hình thể <span>(Realtime)</span>
          </h3>
          
          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Chiều cao</label>
              <span>{userProfile.height} cm</span>
            </div>
            <input type="range" min="140" max="200" value={userProfile.height} onChange={(e) => updateMetric('height', Number(e.target.value))} className="accent-purple-500" />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Cân nặng</label>
              <span>{userProfile.weight} kg</span>
            </div>
            <input type="range" min="40" max="120" value={userProfile.weight} onChange={(e) => updateMetric('weight', Number(e.target.value))} className="accent-purple-500" />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Rộng vai</label>
              <span>{userProfile.shoulder} cm</span>
            </div>
            <input type="range" min="30" max="60" value={userProfile.shoulder} onChange={(e) => updateMetric('shoulder', Number(e.target.value))} className="accent-purple-500" />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Vòng 1 (Ngực)</label>
              <span>{userProfile.bust} cm</span>
            </div>
            <input type="range" min="60" max="120" value={userProfile.bust} onChange={(e) => updateMetric('bust', Number(e.target.value))} className="accent-purple-500" />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Vòng 2 (Eo)</label>
              <span>{userProfile.waist} cm</span>
            </div>
            <input type="range" min="50" max="110" value={userProfile.waist} onChange={(e) => updateMetric('waist', Number(e.target.value))} className="accent-purple-500" />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs font-semibold text-slate-600">
              <label>Vòng 3 (Hông)</label>
              <span>{userProfile.hips} cm</span>
            </div>
            <input type="range" min="70" max="130" value={userProfile.hips} onChange={(e) => updateMetric('hips', Number(e.target.value))} className="accent-purple-500" />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="font-semibold text-sm">Tone da</label>
          <select 
            className="p-3 border rounded-lg bg-slate-50 focus:ring-2 focus:ring-purple-500 outline-none"
            value={userProfile.skin_tone}
            onChange={(e) => setUserProfile({...userProfile, skin_tone: e.target.value})}
          >
            {SKIN_TONES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="flex flex-col gap-2">
          <label className="font-semibold text-sm">Khuôn mặt</label>
          <select 
            className="p-3 border rounded-lg bg-slate-50 focus:ring-2 focus:ring-purple-500 outline-none"
            value={userProfile.face_shape}
            onChange={(e) => setUserProfile({...userProfile, face_shape: e.target.value})}
          >
            {FACE_SHAPES.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>

      {/* CỘT 2: 3D MODEL */}
      <div className="flex-1 h-full relative cursor-move bg-gradient-to-b from-slate-200 to-slate-300 flex items-center justify-center">
        {gender ? (
          <>
            <ModelViewer 
              gender={gender}
              skinTone={userProfile.skin_tone}
              height={userProfile.height}
              weight={userProfile.weight}
              shoulder={userProfile.shoulder}
              bust={userProfile.bust}
              waist={userProfile.waist}
              hips={userProfile.hips}
            />
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-black/40 text-white px-5 py-2 rounded-full text-sm backdrop-blur-md font-medium shadow-lg">
              👆 Kéo chuột để xoay 360° | Cuộn để Zoom
            </div>
          </>
        ) : (
          <div className="text-slate-500 font-medium bg-white/50 px-6 py-4 rounded-xl shadow-sm border border-white">
            Vui lòng chọn Giới tính để tải mô hình 3D
          </div>
        )}
      </div>

      {/* CỘT 3: TỦ ĐỒ & AI */}
      <div className="w-[30%] h-full bg-white shadow-xl p-6 flex flex-col gap-6 z-10 overflow-y-auto">
        
        {/* TỦ ĐỒ SỐ */}
        <div className="flex flex-col min-h-[40%] gap-3">
          <div className="flex justify-between items-end">
            <h2 className="text-xl font-bold flex items-center gap-2">🧥 Tủ Đồ Số</h2>
            <span className="text-sm font-medium text-slate-500">{wardrobeItems.length} món</span>
          </div>
          
          {/* Upload Button */}
          <div 
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-300 hover:border-purple-400 bg-slate-50 rounded-xl py-4 flex flex-col items-center justify-center text-slate-500 cursor-pointer transition-colors"
          >
            {isScanning ? (
              <p className="font-medium animate-pulse text-purple-600">Đang quét phân tích...</p>
            ) : (
              <>
                <span className="text-2xl mb-1">+</span>
                <p className="font-medium text-sm">Tải ảnh quần áo lên</p>
              </>
            )}
            <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleFileUpload} />
          </div>

          {/* Wardrobe Grid */}
          <div className="grid grid-cols-3 gap-2 overflow-y-auto max-h-[300px] pr-1">
            {wardrobeItems.map((item) => (
              <div key={item.id} className="relative group rounded-lg overflow-hidden border border-slate-200 shadow-sm aspect-square bg-slate-100">
                <img src={item.imageUrl} alt="wardrobe item" className="w-full h-full object-cover" />
                <button 
                  onClick={() => removeWardrobeItem(item.id)}
                  className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ✕
                </button>
                <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] truncate px-1 py-0.5 text-center">
                  {item.description.item_category || 'Đã phân loại'}
                </div>
              </div>
            ))}
          </div>
        </div>

        <hr className="border-slate-100" />

        {/* MASTER STYLIST */}
        <div className="flex flex-col flex-1 gap-3">
          <h2 className="text-xl font-bold flex items-center gap-2">💡 Master Stylist</h2>
          
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tình huống (Hoàn cảnh)</label>
            <input 
              type="text" 
              className="p-2 border border-slate-200 rounded-lg bg-slate-50 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
              placeholder="Ví dụ: Đi làm công sở, Hẹn hò lãng mạn..."
              value={contextTags}
              onChange={(e) => setContextTags(e.target.value)}
            />
          </div>

          <button 
            onClick={handleMixAndMatch}
            disabled={isAdvising || wardrobeItems.length === 0}
            className="mt-2 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white font-bold py-3 rounded-xl transition-all shadow-md disabled:opacity-50"
          >
            {isAdvising ? 'Đang nháp tư duy...' : '🔥 Mix & Match'}
          </button>

          {/* Kết quả tư vấn */}
          {adviceResult && (
            <div className="mt-3 flex-1 overflow-y-auto flex flex-col gap-3">
              {adviceResult.think && (
                <div className="border border-purple-200 bg-purple-50/50 rounded-xl overflow-hidden">
                  <button 
                    onClick={() => setShowThinking(!showThinking)}
                    className="w-full text-left p-3 text-sm font-semibold text-purple-800 flex justify-between items-center"
                  >
                    🧠 Quá trình suy luận (Khoa học thị giác)
                    <span>{showThinking ? '▼' : '▶'}</span>
                  </button>
                  {showThinking && (
                    <div className="p-3 pt-0 text-xs text-purple-700/80 whitespace-pre-wrap border-t border-purple-100">
                      {adviceResult.think}
                    </div>
                  )}
                </div>
              )}
              
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl text-sm text-slate-700 whitespace-pre-wrap shadow-inner">
                {adviceResult.content}
              </div>
            </div>
          )}
          
          {!adviceResult && !isAdvising && (
             <div className="flex-1 border-2 border-dashed border-slate-200 rounded-xl flex items-center justify-center p-4 text-center">
               <p className="text-sm text-slate-400">Thêm đồ vào tủ, nhập tình huống và bấm Mix & Match để xem AI thể hiện phép màu khoa học.</p>
             </div>
          )}
        </div>

      </div>
    </div>
  )
}
