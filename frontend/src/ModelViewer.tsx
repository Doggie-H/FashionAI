import React, { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import RiggedMannequin from './RiggedMannequin'

export default function ModelViewer({ 
  gender,
  skinTone, 
  height,
  weight,
  shoulder,
  bust,
  waist,
  hips
}: { 
  gender: string,
  skinTone: string, 
  height: number,
  weight: number,
  shoulder: number,
  bust: number,
  waist: number,
  hips: number
}) {
  return (
    <Canvas shadows camera={{ position: [0, 1.2, 4.0], fov: 50 }}>
      {/* Background color for the room */}
      <color attach="background" args={['#1a1a1a']} />
      
      {/* Dramatic Studio Lighting */}
      <ambientLight intensity={0.2} />
      {/* Main Spotlight mimicking a stage light */}
      <spotLight 
        position={[2, 4, 3]} 
        angle={0.4} 
        penumbra={0.8} 
        intensity={2.5} 
        castShadow 
        shadow-mapSize-width={1024} 
        shadow-mapSize-height={1024}
        shadow-bias={-0.0001}
      />
      {/* Backlight to separate mannequin from background */}
      <spotLight position={[-3, 3, -3]} angle={0.5} penumbra={1} intensity={1.5} color="#ffffff" />
      {/* Soft fill light */}
      <pointLight position={[-2, 1, 2]} intensity={0.5} color="#aaaaaa" />

      {/* Circular Pedestal */}
      <mesh receiveShadow position={[0, -0.85, 0]}>
        <cylinderGeometry args={[0.8, 0.85, 0.1, 64]} />
        <meshStandardMaterial color="#333333" roughness={0.2} metalness={0.1} />
      </mesh>
      
      {/* Floor plane to catch shadows and give a room feel */}
      <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.9, 0]}>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#111111" roughness={0.8} />
      </mesh>

      <Suspense fallback={<Html center><div className="text-white font-light text-sm tracking-widest uppercase animate-pulse whitespace-nowrap">Đang tải người mẫu 3D...</div></Html>}>
        <RiggedMannequin 
          gender={gender} 
          skinTone={skinTone}
          height={height}
          weight={weight}
          shoulder={shoulder}
          bust={bust}
          waist={waist}
          hips={hips}
        />
      </Suspense>
      <OrbitControls autoRotate autoRotateSpeed={0.5} enableZoom={true} target={[0, 0.8, 0]} minPolarAngle={Math.PI/4} maxPolarAngle={Math.PI/1.5} />
    </Canvas>
  )
}
