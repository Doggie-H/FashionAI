import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';

const mockWardrobe = [
  { id: '1', name: 'Áo thun trắng Basic', category: 'Top', color: 'White' },
  { id: '2', name: 'Quần Jeans đen', category: 'Bottom', color: 'Black' },
  { id: '3', name: 'Áo khoác Vintage', category: 'Outerwear', color: 'Brown' },
];

export default function WardrobeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Tủ đồ cá nhân</Text>
      
      <FlatList 
        data={mockWardrobe}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <View style={styles.itemCard}>
            <View style={styles.itemInfo}>
                <Text style={styles.itemName}>{item.name}</Text>
                <Text style={styles.itemCategory}>{item.category} • {item.color}</Text>
            </View>
          </View>
        )}
      />
      
      <TouchableOpacity style={styles.uploadBtn}>
        <Text style={styles.uploadText}>+ Tải Ảnh Áo Quần Mới (AI Tách Nền)</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  heading: { fontSize: 20, fontWeight: 'bold', marginBottom: 15, color: '#333' },
  itemCard: { backgroundColor: '#fff', padding: 15, borderRadius: 10, marginBottom: 10, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 5, elevation: 2 },
  itemName: { fontSize: 16, fontWeight: 'bold', color: '#222' },
  itemCategory: { color: '#666', marginTop: 5, fontSize: 14 },
  uploadBtn: { backgroundColor: '#007AFF', padding: 15, borderRadius: 10, alignItems: 'center', marginTop: 10 },
  uploadText: { color: '#fff', fontWeight: 'bold', fontSize: 16 }
});
