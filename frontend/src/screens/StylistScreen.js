import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image, ScrollView, ActivityIndicator, Alert, Platform } from 'react-native';
import * as ImagePicker from 'expo-image-picker';

export default function StylistScreen() {
  const [imageUri, setImageUri] = useState(null);
  const [tags, setTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState('');

  // User Profile States
  const [bodyType, setBodyType] = useState('Dáng Đồng Hồ Cát');
  const [skinTone, setSkinTone] = useState('Trung tính (Neutral)');
  const [hairType, setHairType] = useState('Tóc dài thẳng');
  const [faceShape, setFaceShape] = useState('Mặt trái xoan');

  // Thay đổi URL này thành IP LAN của máy tính (ví dụ: 192.168.1.10) nếu chạy trên máy thật
  const API_BASE_URL = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000';

  useEffect(() => {
    fetch(`${API_BASE_URL}/stylist/tags`)
      .then(res => res.json())
      .then(data => {
        if (data.tags) setTags(data.tags);
      })
      .catch(err => console.log('Fetch tags error:', err));
  }, []);

  const pickImage = async () => {
    let result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [3, 4],
      quality: 0.8,
    });

    if (!result.canceled) {
      setImageUri(result.assets[0].uri);
    }
  };

  const toggleTag = (tag) => {
    if (selectedTags.includes(tag)) {
      setSelectedTags(selectedTags.filter(t => t !== tag));
    } else {
      setSelectedTags([...selectedTags, tag]);
    }
  };

  const submitToAI = async () => {
    if (!imageUri) {
      Alert.alert('Lỗi', 'Vui lòng chọn một bức ảnh quần áo.');
      return;
    }
    if (selectedTags.length === 0) {
      Alert.alert('Lỗi', 'Vui lòng chọn ít nhất một nhu cầu (tag).');
      return;
    }

    setLoading(true);
    setResult('');

    try {
      const formData = new FormData();
      const filename = imageUri.split('/').pop();
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : `image`;

      formData.append('image', { uri: imageUri, name: filename, type });
      formData.append('tags', selectedTags.join(','));
      formData.append('body_type', bodyType);
      formData.append('skin_tone', skinTone);
      formData.append('hair_type', hairType);
      formData.append('face_shape', faceShape);

      const response = await fetch(`${API_BASE_URL}/stylist/recommend/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        body: formData,
      });

      const data = await response.json();
      if (response.ok) {
        setResult(data.data.ai_reasoning_and_recommendation);
      } else {
        Alert.alert('Lỗi', data.detail || 'Không thể lấy kết quả từ AI.');
      }
    } catch (error) {
      Alert.alert('Lỗi Kết Nối', 'Không thể kết nối đến AI Backend. Hãy đảm bảo Backend đang chạy.');
      console.log(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.heading}>Trợ lý AI Stylist 3D</Text>
      
      {/* Upload Image Section */}
      <TouchableOpacity style={styles.imagePicker} onPress={pickImage}>
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.image} />
        ) : (
          <View style={styles.placeholderContainer}>
            <Text style={styles.placeholderText}>+ Chọn ảnh trang phục</Text>
          </View>
        )}
      </TouchableOpacity>

      {/* User Profile Section */}
      <Text style={styles.subHeading}>Hồ sơ Đặc điểm:</Text>
      
      <Text style={styles.label}>Dáng người:</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.profileScroll}>
        {['Dáng Quả Lê', 'Dáng Quả Táo', 'Dáng Đồng Hồ Cát', 'Dáng Chữ Nhật', 'Cao gầy', 'Petite', 'Đậm người'].map(opt => (
          <TouchableOpacity key={opt} style={[styles.profileBtn, bodyType === opt && styles.profileBtnSelected]} onPress={() => setBodyType(opt)}>
            <Text style={[styles.profileText, bodyType === opt && styles.profileTextSelected]}>{opt}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.label}>Tone da:</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.profileScroll}>
        {['Da ngăm (Warm Tone)', 'Da trắng (Cool Tone)', 'Trung tính (Neutral)'].map(opt => (
          <TouchableOpacity key={opt} style={[styles.profileBtn, skinTone === opt && styles.profileBtnSelected]} onPress={() => setSkinTone(opt)}>
            <Text style={[styles.profileText, skinTone === opt && styles.profileTextSelected]}>{opt}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.label}>Kiểu tóc:</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.profileScroll}>
        {['Tóc ngắn cá tính', 'Tóc dài thẳng', 'Tóc xoăn bồng bềnh', 'Tóc nhuộm sáng'].map(opt => (
          <TouchableOpacity key={opt} style={[styles.profileBtn, hairType === opt && styles.profileBtnSelected]} onPress={() => setHairType(opt)}>
            <Text style={[styles.profileText, hairType === opt && styles.profileTextSelected]}>{opt}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.label}>Khuôn mặt:</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.profileScroll}>
        {['Mặt tròn', 'Mặt V-line', 'Mặt vuông góc cạnh', 'Mặt trái xoan'].map(opt => (
          <TouchableOpacity key={opt} style={[styles.profileBtn, faceShape === opt && styles.profileBtnSelected]} onPress={() => setFaceShape(opt)}>
            <Text style={[styles.profileText, faceShape === opt && styles.profileTextSelected]}>{opt}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Tags Section */}
      <Text style={styles.subHeading}>Chọn Nhu cầu của bạn:</Text>
      <View style={styles.tagsContainer}>
        {tags.map((tag, idx) => (
          <TouchableOpacity 
            key={idx} 
            style={[styles.tag, selectedTags.includes(tag) && styles.tagSelected]}
            onPress={() => toggleTag(tag)}
          >
            <Text style={[styles.tagText, selectedTags.includes(tag) && styles.tagTextSelected]}>{tag}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Submit Button */}
      <TouchableOpacity style={styles.btn} onPress={submitToAI} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Nhận Tư Vấn AI</Text>}
      </TouchableOpacity>

      {/* Result Section */}
      {result ? (
        <View style={styles.resultContainer}>
          <Text style={styles.resultHeading}>✨ Gợi ý từ Stylist:</Text>
          <Text style={styles.resultText}>{result}</Text>
        </View>
      ) : null}
      
      <View style={{height: 50}} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#f9f9f9' },
  heading: { fontSize: 24, fontWeight: 'bold', marginBottom: 20, color: '#333' },
  imagePicker: { height: 250, backgroundColor: '#fff', borderRadius: 15, overflow: 'hidden', borderWidth: 2, borderColor: '#eee', borderStyle: 'dashed', marginBottom: 20, justifyContent: 'center', alignItems: 'center' },
  image: { width: '100%', height: '100%', resizeMode: 'cover' },
  placeholderContainer: { alignItems: 'center' },
  placeholderText: { fontSize: 16, color: '#888', fontWeight: '500' },
  subHeading: { fontSize: 18, fontWeight: '700', marginBottom: 10, color: '#222', marginTop: 10 },
  label: { fontSize: 14, fontWeight: '600', color: '#555', marginBottom: 5 },
  profileScroll: { marginBottom: 15 },
  profileBtn: { backgroundColor: '#f0f0f0', paddingHorizontal: 15, paddingVertical: 8, borderRadius: 20, marginRight: 10 },
  profileBtnSelected: { backgroundColor: '#000' },
  profileText: { color: '#444', fontSize: 13 },
  profileTextSelected: { color: '#fff', fontWeight: 'bold' },
  tagsContainer: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 20 },
  tag: { backgroundColor: '#fff', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: '#ddd', marginRight: 8, marginBottom: 8 },
  tagSelected: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  tagText: { color: '#666', fontSize: 14 },
  tagTextSelected: { color: '#fff', fontWeight: 'bold' },
  btn: { backgroundColor: '#000', padding: 18, borderRadius: 12, alignItems: 'center', elevation: 3, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.2, shadowRadius: 4 },
  btnText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  resultContainer: { marginTop: 20, backgroundColor: '#fff', padding: 20, borderRadius: 15, borderWidth: 1, borderColor: '#eee' },
  resultHeading: { fontSize: 18, fontWeight: 'bold', color: '#007AFF', marginBottom: 10 },
  resultText: { fontSize: 15, color: '#333', lineHeight: 24 },
});
