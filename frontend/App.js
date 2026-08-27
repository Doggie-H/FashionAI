import React, { useState } from 'react';
import { StyleSheet, Text, View, SafeAreaView, TouchableOpacity } from 'react-native';
import WardrobeScreen from './src/screens/WardrobeScreen';
import StylistScreen from './src/screens/StylistScreen';

export default function App() {
  const [activeTab, setActiveTab] = useState('Wardrobe');

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>AI 3D Stylist</Text>
      </View>
      
      <View style={styles.content}>
        {activeTab === 'Wardrobe' ? <WardrobeScreen /> : <StylistScreen />}
      </View>

      <View style={styles.tabBar}>
        <TouchableOpacity 
          style={[styles.tab, activeTab === 'Wardrobe' && styles.activeTab]} 
          onPress={() => setActiveTab('Wardrobe')}
        >
          <Text style={[styles.tabText, activeTab === 'Wardrobe' && styles.activeTabText]}>Tủ đồ</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.tab, activeTab === 'Stylist' && styles.activeTab]} 
          onPress={() => setActiveTab('Stylist')}
        >
          <Text style={[styles.tabText, activeTab === 'Stylist' && styles.activeTabText]}>AI Stylist 3D</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { padding: 20, paddingTop: 50, backgroundColor: '#fff', alignItems: 'center', borderBottomWidth: 1, borderColor: '#eee' },
  title: { fontSize: 22, fontWeight: 'bold' },
  content: { flex: 1 },
  tabBar: { flexDirection: 'row', backgroundColor: '#fff', borderTopWidth: 1, borderColor: '#eee', paddingBottom: 20 },
  tab: { flex: 1, padding: 15, alignItems: 'center' },
  activeTab: { borderTopWidth: 3, borderColor: '#007AFF' },
  tabText: { fontSize: 16, fontWeight: '600', color: '#888' },
  activeTabText: { color: '#007AFF' }
});
