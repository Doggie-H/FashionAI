import React, { useMemo } from 'react'
import * as THREE from 'three'
import { Sphere, Cylinder } from '@react-three/drei'

interface MannequinProps {
  gender: string;
  skinTone: string;
  height: number;
  weight: number;
  shoulder: number;
  bust: number;
  waist: number;
  hips: number;
}

const SKIN_COLORS: Record<string, number> = {
  'Trắng sáng (Cool undertone)': 0xffe0bd,
  'Trung tính (Neutral)': 0xf1c27d,
  'Ngăm đen (Warm undertone)': 0x8d5524,
  'Da Vàng (Olive/Asian)': 0xe5c298
}

export default function ProceduralMannequin({
  gender,
  skinTone,
  height,
  weight,
  shoulder,
  bust,
  waist,
  hips
}: MannequinProps) {
  const colorHex = SKIN_COLORS[skinTone] || 0xe8e8e8
  
  const material = useMemo(() => new THREE.MeshStandardMaterial({
    color: colorHex,
    roughness: 0.3,
    metalness: 0.1,
  }), [colorHex])

  // --- ANATOMICAL MATH ---
  // Base height in 3D world is 1.75 units for a 170cm person
  const H = 1.75 * (height / 170)
  // Weight scale uses a gentle curve so it doesn't inflate too fast
  const W = Math.pow(weight / 60, 0.45)
  const S = shoulder / 40
  const B = bust / 85
  const Wa = waist / 65
  const Hi = hips / 90

  // 1. Crotch (Center of body, approx 47% of total height)
  const crotchY = H * 0.47

  // 2. Head (Avg 1/8th of height)
  const headRadius = 0.095 * W
  const headY = H - headRadius

  // 3. Neck
  const neckHeight = 0.06 * H
  const neckY = headY - headRadius - neckHeight / 2

  // 4. Chest (Upper Torso)
  const chestRadius = 0.13 * B * W
  const chestY = neckY - neckHeight / 2 - chestRadius * 0.9

  // 5. Pelvis (Lower Torso)
  const pelvisRadius = 0.14 * Hi * W
  const pelvisY = crotchY + pelvisRadius * 0.7

  // 6. Abdomen (Waist)
  const abdomenHeight = (chestY - chestRadius * 0.5) - (pelvisY + pelvisRadius * 0.5)
  const abdomenY = pelvisY + pelvisRadius * 0.5 + abdomenHeight / 2
  const waistRadiusTop = chestRadius * 0.8 * Wa
  const waistRadiusBot = pelvisRadius * 0.8 * Wa

  // 7. Shoulders & Arms
  const shoulderDist = 0.17 * S * W
  const shoulderY = chestY + chestRadius * 0.4
  
  const upperArmLength = H * 0.18
  const lowerArmLength = H * 0.16
  const armThickness = 0.04 * W

  // 8. Legs
  const upperLegLength = crotchY * 0.48
  const lowerLegLength = crotchY * 0.45
  const legThickness = 0.055 * W
  const legDist = pelvisRadius * 0.65

  // We group the whole body and offset it so the feet rest on Y=0
  return (
    <group position={[0, -0.05, 0]}>
      {/* --- TORSO & HEAD --- */}
      {/* Head */}
      <Sphere args={[headRadius, 32, 32]} position={[0, headY, 0]} scale={[1, 1.2, 1.1]} material={material} castShadow receiveShadow />
      
      {/* Neck */}
      <Cylinder args={[0.04 * W, 0.05 * W, neckHeight, 16]} position={[0, neckY, 0]} material={material} castShadow receiveShadow />
      
      {/* Chest */}
      <Sphere args={[chestRadius, 32, 32]} position={[0, chestY, 0]} scale={[1, 1.1, 0.75]} material={material} castShadow receiveShadow />
      
      {/* Abdomen / Waist */}
      <Cylinder args={[waistRadiusTop, waistRadiusBot, abdomenHeight, 32]} position={[0, abdomenY, 0]} scale={[1, 1, 0.6]} material={material} castShadow receiveShadow />
      
      {/* Pelvis */}
      <Sphere args={[pelvisRadius, 32, 32]} position={[0, pelvisY, 0]} scale={[1, 0.9, 0.8]} material={material} castShadow receiveShadow />

      {/* --- ARMS --- */}
      {/* Left Shoulder */}
      <Sphere args={[0.05 * W, 16, 16]} position={[-shoulderDist, shoulderY, 0]} material={material} castShadow receiveShadow />
      {/* Left Upper Arm */}
      <Cylinder args={[armThickness, armThickness * 0.85, upperArmLength, 16]} position={[-shoulderDist - 0.02, shoulderY - upperArmLength/2, 0]} rotation={[0, 0, -0.1]} material={material} castShadow receiveShadow />
      {/* Left Elbow */}
      <Sphere args={[armThickness * 0.85, 16, 16]} position={[-shoulderDist - 0.04, shoulderY - upperArmLength, 0]} material={material} castShadow receiveShadow />
      {/* Left Lower Arm */}
      <Cylinder args={[armThickness * 0.85, armThickness * 0.65, lowerArmLength, 16]} position={[-shoulderDist - 0.04, shoulderY - upperArmLength - lowerArmLength/2, 0.02]} rotation={[0.1, 0, 0]} material={material} castShadow receiveShadow />
      {/* Left Hand */}
      <Sphere args={[armThickness * 0.7, 16, 16]} position={[-shoulderDist - 0.04, shoulderY - upperArmLength - lowerArmLength, 0.04]} scale={[1, 1.3, 0.8]} material={material} castShadow receiveShadow />

      {/* Right Shoulder */}
      <Sphere args={[0.05 * W, 16, 16]} position={[shoulderDist, shoulderY, 0]} material={material} castShadow receiveShadow />
      {/* Right Upper Arm */}
      <Cylinder args={[armThickness, armThickness * 0.85, upperArmLength, 16]} position={[shoulderDist + 0.02, shoulderY - upperArmLength/2, 0]} rotation={[0, 0, 0.1]} material={material} castShadow receiveShadow />
      {/* Right Elbow */}
      <Sphere args={[armThickness * 0.85, 16, 16]} position={[shoulderDist + 0.04, shoulderY - upperArmLength, 0]} material={material} castShadow receiveShadow />
      {/* Right Lower Arm */}
      <Cylinder args={[armThickness * 0.85, armThickness * 0.65, lowerArmLength, 16]} position={[shoulderDist + 0.04, shoulderY - upperArmLength - lowerArmLength/2, 0.02]} rotation={[0.1, 0, 0]} material={material} castShadow receiveShadow />
      {/* Right Hand */}
      <Sphere args={[armThickness * 0.7, 16, 16]} position={[shoulderDist + 0.04, shoulderY - upperArmLength - lowerArmLength, 0.04]} scale={[1, 1.3, 0.8]} material={material} castShadow receiveShadow />

      {/* --- LEGS --- */}
      {/* Left Hip Joint */}
      <Sphere args={[legThickness * 1.1, 16, 16]} position={[-legDist, pelvisY - pelvisRadius*0.2, 0]} material={material} castShadow receiveShadow />
      {/* Left Upper Leg */}
      <Cylinder args={[legThickness, legThickness * 0.85, upperLegLength, 16]} position={[-legDist, pelvisY - pelvisRadius*0.2 - upperLegLength/2, 0]} material={material} castShadow receiveShadow />
      {/* Left Knee */}
      <Sphere args={[legThickness * 0.85, 16, 16]} position={[-legDist, pelvisY - pelvisRadius*0.2 - upperLegLength, 0.02]} material={material} castShadow receiveShadow />
      {/* Left Lower Leg */}
      <Cylinder args={[legThickness * 0.85, legThickness * 0.7, lowerLegLength, 16]} position={[-legDist, pelvisY - pelvisRadius*0.2 - upperLegLength - lowerLegLength/2, 0.02]} material={material} castShadow receiveShadow />
      {/* Left Foot */}
      <Sphere args={[legThickness * 0.75, 16, 16]} position={[-legDist, pelvisY - pelvisRadius*0.2 - upperLegLength - lowerLegLength, 0.06]} scale={[1, 0.6, 1.8]} material={material} castShadow receiveShadow />

      {/* Right Hip Joint */}
      <Sphere args={[legThickness * 1.1, 16, 16]} position={[legDist, pelvisY - pelvisRadius*0.2, 0]} material={material} castShadow receiveShadow />
      {/* Right Upper Leg */}
      <Cylinder args={[legThickness, legThickness * 0.85, upperLegLength, 16]} position={[legDist, pelvisY - pelvisRadius*0.2 - upperLegLength/2, 0]} material={material} castShadow receiveShadow />
      {/* Right Knee */}
      <Sphere args={[legThickness * 0.85, 16, 16]} position={[legDist, pelvisY - pelvisRadius*0.2 - upperLegLength, 0.02]} material={material} castShadow receiveShadow />
      {/* Right Lower Leg */}
      <Cylinder args={[legThickness * 0.85, legThickness * 0.7, lowerLegLength, 16]} position={[legDist, pelvisY - pelvisRadius*0.2 - upperLegLength - lowerLegLength/2, 0.02]} material={material} castShadow receiveShadow />
      {/* Right Foot */}
      <Sphere args={[legThickness * 0.75, 16, 16]} position={[legDist, pelvisY - pelvisRadius*0.2 - upperLegLength - lowerLegLength, 0.06]} scale={[1, 0.6, 1.8]} material={material} castShadow receiveShadow />
    </group>
  )
}
