import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';

function MannequinPlaceholder(props) {
  const mesh = useRef();
  
  // Xoay từ từ mô hình giả lập
  useFrame((state, delta) => (mesh.current.rotation.y += delta * 0.3));

  return (
    <mesh {...props} ref={mesh}>
      {/* Một khối trụ đơn giản giả lập mannequin 3D */}
      <cylinderGeometry args={[1, 1, 4, 32]} />
      <meshStandardMaterial color={'#007AFF'} wireframe />
    </mesh>
  );
}

export default function Model3D() {
  return (
    <Canvas camera={{ position: [0, 0, 7] }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 10]} intensity={1} />
      
      <MannequinPlaceholder position={[0, -0.5, 0]} />
      
      {/* OrbitControls cho phép người dùng dùng tay vuốt xoay xem 3D */}
      <OrbitControls enablePan={false} />
    </Canvas>
  );
}
