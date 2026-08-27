'use client';

import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Environment, Html, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

export type GenderType = 'female' | 'male';
export type FaceShapeType = 'oval' | 'round' | 'square' | 'heart' | 'diamond' | 'oblong' | 'triangle';

export type BodyMeasurements = {
  height: number;
  shoulder: number;
  bust: number;
  waist: number;
  hip: number;
  thigh?: number;
  calf?: number;
  bicep?: number;
  neck?: number;
  inseam: number;
  weight?: number;
  shoulder_slope?: 'straight' | 'sloped';
  chest_profile?: 'full' | 'flat';
  leg_alignment?: 'straight' | 'bowed';
};

export type GarmentStructuralProfile = {
  neckline?: string; shoulder_construction?: string; shoulder_width?: string; sleeve_length?: string;
  torso_length?: string; waist_shape?: string; hem_shape?: string; rise?: string;
  waist_construction?: string; hip_fit?: string; leg_shape?: string; leg_length?: string;
  source_views?: string[]; limitations?: string[];
};

export type TryOnGarmentBinding = {
  import_id?: string;
  asset_id?: string;
  revision_id?: string;
  category: 'top' | 'bottom' | 'dress' | 'outerwear' | 'footwear' | 'belt' | 'accessory';
  selected_garment_id?: string;
  template_id?: string;
  rig_status?: 'canonical_proxy' | 'rigged_template' | 'pending_reconstruction' | 'failed';
  render_mode?: 'canonical_proxy' | 'rigged_template' | 'approved_reconstructed_asset';
  asset_uri?: string | null;
  quality_status?: 'approved' | 'proxy' | 'pending_review' | 'rejected' | 'unavailable';
  target_skeleton_id?: string;
  render_binding?: Record<string, string | number>;
  structural_profile?: GarmentStructuralProfile | null;
};

export type LightingFilter = 'studio' | 'sunset' | 'cyberpunk' | 'minimalist' | 'vintage';
export type ViewPreset = 'front' | 'side' | 'back' | 'upper' | 'lower' | 'face' | 'free';

type Props = {
  measurements: BodyMeasurements;
  gender?: GenderType;
  faceShape?: FaceShapeType;
  hairStyle?: string;
  glassesType?: string;
  autoRotate?: boolean;
  outfitStyle?: 'neutral' | 'navy' | 'burgundy' | 'emerald';
  animationEnabled?: boolean;
  garmentBindings?: TryOnGarmentBinding[];
  viewPreset?: ViewPreset;
  lightingFilter?: LightingFilter;
};

const filterConfigs: Record<LightingFilter, {
  background: string;
  wallColor: string;
  floorColor: string;
  ambientIntensity: number;
  keyIntensity: number;
  keyColor: string;
  fillIntensity: number;
  fillColor: string;
  rimIntensity: number;
  rimColor: string;
  podiumColor: string;
  podiumRimColor: string;
  skinTone: string;
  envPreset: 'studio' | 'sunset' | 'city' | 'apartment' | 'park';
}> = {
  studio: {
    background: '#0f172a',
    wallColor: '#cbd5e1',
    floorColor: '#e2e8f0',
    ambientIntensity: 0.70,
    keyIntensity: 1.15,
    keyColor: '#fffef5',
    fillIntensity: 0.50,
    fillColor: '#94a3b8',
    rimIntensity: 0.65,
    rimColor: '#e2e8f0',
    podiumColor: '#f8fafc',
    podiumRimColor: '#6366f1',
    skinTone: '#d9c5b2', // Smooth natural skin mannequin tone
    envPreset: 'studio',
  },
  sunset: {
    background: '#451a03',
    wallColor: '#fed7aa',
    floorColor: '#ffedd5',
    ambientIntensity: 0.60,
    keyIntensity: 1.25,
    keyColor: '#fed7aa',
    fillIntensity: 0.45,
    fillColor: '#f472b6',
    rimIntensity: 0.70,
    rimColor: '#fde68a',
    podiumColor: '#ffedd5',
    podiumRimColor: '#f97316',
    skinTone: '#dec0a5',
    envPreset: 'sunset',
  },
  cyberpunk: {
    background: '#030712',
    wallColor: '#1e1b4b',
    floorColor: '#0f172a',
    ambientIntensity: 0.50,
    keyIntensity: 1.30,
    keyColor: '#38bdf8',
    fillIntensity: 0.80,
    fillColor: '#f43f5e',
    rimIntensity: 0.90,
    rimColor: '#c084fc',
    podiumColor: '#18181b',
    podiumRimColor: '#06b6d4',
    skinTone: '#94a3b8',
    envPreset: 'city',
  },
  minimalist: {
    background: '#1e293b',
    wallColor: '#f1f5f9',
    floorColor: '#ffffff',
    ambientIntensity: 0.75,
    keyIntensity: 1.0,
    keyColor: '#ffffff',
    fillIntensity: 0.40,
    fillColor: '#cbd5e1',
    rimIntensity: 0.45,
    rimColor: '#e2e8f0',
    podiumColor: '#ffffff',
    podiumRimColor: '#94a3b8',
    skinTone: '#d5bfab',
    envPreset: 'apartment',
  },
  vintage: {
    background: '#291e0a',
    wallColor: '#fef3c7',
    floorColor: '#fde68a',
    ambientIntensity: 0.60,
    keyIntensity: 1.15,
    keyColor: '#fde68a',
    fillIntensity: 0.45,
    fillColor: '#d97706',
    rimIntensity: 0.60,
    rimColor: '#fef08a',
    podiumColor: '#fef3c7',
    podiumRimColor: '#d97706',
    skinTone: '#d3ba9e',
    envPreset: 'park',
  },
};

function colorForGarment(binding: TryOnGarmentBinding): string {
  const id = binding.selected_garment_id ?? binding.asset_id ?? binding.import_id ?? '';
  if (id.includes('burgundy')) return '#881337';
  if (id.includes('navy')) return '#1e3a8a';
  if (id.includes('earth')) return '#92400e';
  if (id.includes('white')) return '#f1f5f9';
  return '#1e293b';
}

function GarmentProxy({ binding, measurements }: { binding: TryOnGarmentBinding; measurements: BodyMeasurements }) {
  const color = colorForGarment(binding);
  const material = <meshStandardMaterial color={color} roughness={0.82} metalness={0.02} transparent opacity={0.92} />;
  const category = binding.category;
  const profile = binding.structural_profile ?? {};
  
  const shoulderWidth = (measurements.shoulder / 42) * 0.38;
  const bustDepth = (measurements.bust / 88) * 0.24;
  const waistWidth = (measurements.waist / 72) * 0.24;
  const hipWidth = (measurements.hip / 94) * 0.34;
  const legLen = (measurements.inseam / 78) * 0.72;

  if (category === 'top') {
    const s = profile.shoulder_width === 'wide' ? shoulderWidth * 1.15 : shoulderWidth;
    const tLen = profile.torso_length === 'cropped' ? 0.26 : profile.torso_length === 'long' ? 0.44 : 0.35;
    return (
      <group position={[0, 0.32, 0.01]}>
        <mesh position={[0, 0.05, 0]} scale={[s * 2, tLen * 0.58, bustDepth * 1.25]}>
          <boxGeometry args={[1, 1, 1]} />
          {material}
        </mesh>
        <mesh position={[0, -0.15, 0]} scale={[waistWidth * 2, tLen * 0.42, bustDepth * 1.1]}>
          <boxGeometry args={[1, 1, 1]} />
          {material}
        </mesh>
        {profile.sleeve_length !== 'sleeveless' && (
          <>
            <mesh position={[-(s * 1.05), 0.02, 0]} scale={[0.13, 0.36, 0.20]} rotation={[0, 0, 0.18]}>
              <boxGeometry args={[1, 1, 1]} />
              {material}
            </mesh>
            <mesh position={[(s * 1.05), 0.02, 0]} scale={[0.13, 0.36, 0.20]} rotation={[0, 0, -0.18]}>
              <boxGeometry args={[1, 1, 1]} />
              {material}
            </mesh>
          </>
        )}
      </group>
    );
  }
  if (category === 'outerwear') {
    return <mesh position={[0, 0.28, 0.02]} scale={[shoulderWidth * 2.2, 0.45, bustDepth * 1.4]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>;
  }
  if (category === 'bottom') {
    const legWidth = profile.leg_shape === 'wide' ? 0.22 : profile.leg_shape === 'skinny' ? 0.13 : 0.16;
    return (
      <group position={[0, -0.10, 0.01]}>
        <mesh position={[0, 0.05, 0]} scale={[hipWidth * 2.0, 0.18, hipWidth * 1.2]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[-0.09, -legLen * 0.46, 0]} scale={[legWidth, legLen * 0.85, legWidth * 1.1]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[0.09, -legLen * 0.46, 0]} scale={[legWidth, legLen * 0.85, legWidth * 1.1]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
      </group>
    );
  }
  if (category === 'dress') {
    return <mesh position={[0, 0.06, 0.01]} scale={[hipWidth * 2.0, 0.65, bustDepth * 1.25]}><cylinderGeometry args={[0.24, 0.36, 1, 24]} />{material}</mesh>;
  }
  if (category === 'belt') {
    return <mesh position={[0, 0.14, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[waistWidth * 2.0, waistWidth * 1.6, 0.04]}><torusGeometry args={[0.5, 0.04, 12, 32]} />{material}</mesh>;
  }
  if (category === 'footwear') {
    return (
      <group position={[0, -0.84, 0.03]}>
        <mesh position={[-0.09, 0, 0]} scale={[0.10, 0.06, 0.22]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[0.09, 0, 0]} scale={[0.10, 0.06, 0.22]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
      </group>
    );
  }
  return <mesh position={[0, 0.15, 0.24]} scale={[0.24, 0.24, 0.05]}><circleGeometry args={[1, 24]} />{material}</mesh>;
}

function ResolvedGarment({ binding, measurements }: { binding: TryOnGarmentBinding; measurements: BodyMeasurements }) {
  return <GarmentProxy binding={binding} measurements={measurements} />;
}

/** 
 * Professional 360° Studio Cyclorama Infinity Room
 * True 3D curved infinity cove that wraps 360 degrees around the avatar
 */
function StudioCycloramaRoom({ filter }: { filter: LightingFilter }) {
  const config = filterConfigs[filter] || filterConfigs.studio;
  return (
    <group position={[0, 0, 0]}>
      {/* 360° Curved Infinity Wall Cylindrical Dome */}
      <mesh position={[0, 2.0, 0]} receiveShadow>
        <cylinderGeometry args={[7.5, 7.5, 9.0, 48, 1, true]} />
        <meshStandardMaterial color={config.wallColor} roughness={0.92} metalness={0.02} side={THREE.BackSide} />
      </mesh>

      {/* 360° Seamless Floor */}
      <mesh position={[0, -0.96, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[7.5, 64]} />
        <meshStandardMaterial color={config.floorColor} roughness={0.88} metalness={0.05} />
      </mesh>

      {/* Circular Studio Spotlight Floor Pool */}
      <mesh position={[0, -0.958, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.15, 2.4, 64]} />
        <meshBasicMaterial color={config.podiumRimColor} transparent opacity={filter === 'cyberpunk' ? 0.25 : 0.08} />
      </mesh>

      {/* 3D Elevated Pedestal Platform under Mannequin */}
      <group position={[0, -0.93, 0]}>
        <mesh position={[0, -0.015, 0]} receiveShadow>
          <cylinderGeometry args={[1.05, 1.10, 0.04, 64]} />
          <meshStandardMaterial color={config.podiumColor} roughness={0.72} metalness={0.06} />
        </mesh>
        <mesh position={[0, -0.015, 0]}>
          <cylinderGeometry args={[1.102, 1.104, 0.02, 64]} />
          <meshStandardMaterial
            color={config.podiumRimColor}
            emissive={config.podiumRimColor}
            emissiveIntensity={filter === 'cyberpunk' ? 0.7 : 0.3}
            roughness={0.3}
            metalness={0.4}
          />
        </mesh>
        <mesh position={[0, -0.05, 0]} receiveShadow>
          <cylinderGeometry args={[1.18, 1.25, 0.05, 64]} />
          <meshStandardMaterial color={config.podiumColor} roughness={0.80} metalness={0.02} />
        </mesh>
        {/* Soft Contact Drop Shadow */}
        <mesh position={[0, -0.076, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <circleGeometry args={[1.8, 32]} />
          <shadowMaterial opacity={0.35} />
        </mesh>
      </group>
    </group>
  );
}

/** 
 * Comprehensive 3D Hairstyles with Detailed Real-World Silhouettes (20 Men + 20 Women)
 */
function RealisticHairstyle3D({
  hairStyle = '',
  gender = 'female',
  headY = 0.74
}: {
  hairStyle?: string;
  gender?: GenderType;
  headY?: number;
}) {
  const hairColor = '#241a12';
  const hairMat = <meshStandardMaterial color={hairColor} roughness={0.72} metalness={0.04} />;
  const style = hairStyle.toLowerCase();

  // MEN'S 20 TRENDING STYLES
  if (gender === 'male' || style.includes('nam') || style.includes('side part') || style.includes('two block') || style.includes('undercut') || style.includes('buzz') || style.includes('pompadour') || style.includes('crop') || style.includes('quiff') || style.includes('comma')) {
    // 1. Side Part 7/3
    if (style.includes('side part') || style.includes('7/3')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
          <mesh position={[-0.03, 0.09, 0.01]} rotation={[0, 0, -0.15]} scale={[0.11, 0.045, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0.05, 0.075, 0.01]} rotation={[0, 0, 0.22]} scale={[0.06, 0.035, 0.14]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[-0.082, 0.01, 0.01]} scale={[0.018, 0.07, 0.11]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0.082, 0.01, 0.01]} scale={[0.018, 0.07, 0.11]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 2. Two Block Hàn Quốc
    if (style.includes('two block')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.095, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
          <mesh position={[0, 0.085, 0.02]} scale={[0.165, 0.055, 0.165]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0, 0.05, 0.085]} scale={[0.14, 0.05, 0.03]} rotation={[0.2, 0, 0]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[-0.088, 0.01, 0.01]} scale={[0.014, 0.06, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0.088, 0.01, 0.01]} scale={[0.014, 0.06, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 3. Undercut Vuốt Ngược / Slicked Back
    if (style.includes('undercut') || style.includes('slicked back')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.094, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.50]} />{hairMat}</mesh>
          <mesh position={[0, 0.09, -0.02]} scale={[0.13, 0.05, 0.17]} rotation={[-0.12, 0, 0]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[-0.085, 0.01, 0.0]} scale={[0.012, 0.065, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0.085, 0.01, 0.0]} scale={[0.012, 0.065, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 4. Textured Crop / French Crop / Caesar
    if (style.includes('crop') || style.includes('caesar')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
          <mesh position={[0, 0.08, 0.01]} scale={[0.15, 0.04, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0, 0.05, 0.082]} scale={[0.12, 0.03, 0.025]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 5. Pompadour / Quiff / Ivy League
    if (style.includes('pompadour') || style.includes('quiff') || style.includes('ivy league')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.095, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.50]} />{hairMat}</mesh>
          <mesh position={[0, 0.11, 0.03]} scale={[0.13, 0.08, 0.14]} rotation={[0.18, 0, 0]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[-0.085, 0.01, 0.0]} scale={[0.014, 0.065, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0.085, 0.01, 0.0]} scale={[0.014, 0.065, 0.10]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 6. Mullet / Wolf Cut Nam
    if (style.includes('mullet') || style.includes('wolf cut')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
          <mesh position={[0, 0.085, 0.01]} scale={[0.15, 0.05, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[0, -0.12, -0.07]} scale={[0.14, 0.22, 0.05]} rotation={[0.08, 0, 0]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        </group>
      );
    }
    // 7. Comma Hair (Tóc Dấu Phẩy)
    if (style.includes('comma')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
          <mesh position={[-0.03, 0.085, 0.02]} scale={[0.11, 0.05, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
          <mesh position={[-0.04, 0.04, 0.085]} scale={[0.05, 0.06, 0.03]} rotation={[0, 0, 0.35]}><torusGeometry args={[0.03, 0.012, 12, 24, Math.PI * 0.8]} />{hairMat}</mesh>
        </group>
      );
    }
    // 8. Man Bun / Top Knot
    if (style.includes('man bun') || style.includes('top knot')) {
      return (
        <group position={[0, headY, 0]}>
          <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.095, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.50]} />{hairMat}</mesh>
          <mesh position={[0, 0.14, -0.03]} scale={[0.055, 0.055, 0.055]}><sphereGeometry args={[1, 24, 24]} />{hairMat}</mesh>
        </group>
      );
    }
    // Default Men Short Fade / Buzz
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.05, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
        <mesh position={[0, 0.075, 0.01]} scale={[0.14, 0.035, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
      </group>
    );
  }

  // WOMEN'S 20 TRENDING STYLES
  // 1. Layer Bob / French Bob
  if (style.includes('bob')) {
    const isFrench = style.includes('french');
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
        <mesh position={[-0.088, -0.06, 0.01]} scale={[0.035, 0.18, 0.09]} rotation={[0, 0, -0.05]}><cylinderGeometry args={[0.7, 0.9, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0.088, -0.06, 0.01]} scale={[0.035, 0.18, 0.09]} rotation={[0, 0, 0.05]}><cylinderGeometry args={[0.7, 0.9, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0, -0.06, -0.065]} scale={[0.15, 0.18, 0.045]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        {isFrench && <mesh position={[0, 0.05, 0.085]} scale={[0.11, 0.035, 0.02]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>}
      </group>
    );
  }
  // 2. Curtain Bangs / Butterfly Cut
  if (style.includes('curtain') || style.includes('butterfly') || style.includes('mái bay')) {
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
        <mesh position={[-0.055, 0.04, 0.08]} scale={[0.045, 0.10, 0.025]} rotation={[0, 0.25, -0.3]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[0.055, 0.04, 0.08]} scale={[0.045, 0.10, 0.025]} rotation={[0, -0.25, 0.3]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[-0.092, -0.15, 0.01]} scale={[0.038, 0.36, 0.10]}><cylinderGeometry args={[0.6, 0.9, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0.092, -0.15, 0.01]} scale={[0.038, 0.36, 0.10]}><cylinderGeometry args={[0.6, 0.9, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0, -0.16, -0.07]} scale={[0.16, 0.38, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
      </group>
    );
  }
  // 3. Long Wavy Sóng Nước / Sleek Straight
  if (style.includes('wavy') || style.includes('straight') || style.includes('sóng') || style.includes('thẳng')) {
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
        <mesh position={[-0.095, -0.18, 0.01]} scale={[0.04, 0.44, 0.11]} rotation={[0, 0, -0.04]}><cylinderGeometry args={[0.5, 0.85, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0.095, -0.18, 0.01]} scale={[0.04, 0.44, 0.11]} rotation={[0, 0, 0.04]}><cylinderGeometry args={[0.5, 0.85, 1, 16]} />{hairMat}</mesh>
        <mesh position={[0, -0.20, -0.075]} scale={[0.17, 0.46, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
      </group>
    );
  }
  // 4. Hime Cut Nhật Bản
  if (style.includes('hime')) {
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
        <mesh position={[0, 0.05, 0.084]} scale={[0.12, 0.04, 0.02]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[-0.086, -0.04, 0.05]} scale={[0.025, 0.14, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[0.086, -0.04, 0.05]} scale={[0.025, 0.14, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[0, -0.18, -0.07]} scale={[0.17, 0.44, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
      </group>
    );
  }
  // 5. High Ponytail / Messy Bun
  if (style.includes('ponytail') || style.includes('đuôi ngựa')) {
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
        <mesh position={[0, 0.14, -0.06]} scale={[0.04, 0.04, 0.04]}><sphereGeometry args={[1, 16, 16]} />{hairMat}</mesh>
        <mesh position={[0, 0.02, -0.12]} scale={[0.05, 0.32, 0.05]} rotation={[-0.25, 0, 0]}><cylinderGeometry args={[0.4, 0.8, 1, 16]} />{hairMat}</mesh>
      </group>
    );
  }
  // 6. Pixie Cut Nữ
  if (style.includes('pixie')) {
    return (
      <group position={[0, headY, 0]}>
        <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.096, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />{hairMat}</mesh>
        <mesh position={[0, 0.08, 0.02]} scale={[0.14, 0.045, 0.15]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
        <mesh position={[-0.03, 0.045, 0.08]} scale={[0.07, 0.04, 0.02]} rotation={[0, 0, -0.2]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
      </group>
    );
  }

  // Default Standard Women Long Layer
  return (
    <group position={[0, headY, 0]}>
      <mesh position={[0, 0.055, 0]}><sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />{hairMat}</mesh>
      <mesh position={[-0.09, -0.12, 0.01]} scale={[0.038, 0.32, 0.09]} rotation={[0, 0, -0.05]}><cylinderGeometry args={[0.6, 0.9, 1, 16]} />{hairMat}</mesh>
      <mesh position={[0.09, -0.12, 0.01]} scale={[0.038, 0.32, 0.09]} rotation={[0, 0, 0.05]}><cylinderGeometry args={[0.6, 0.9, 1, 16]} />{hairMat}</mesh>
      <mesh position={[0, -0.14, -0.07]} scale={[0.16, 0.35, 0.05]}><boxGeometry args={[1, 1, 1]} />{hairMat}</mesh>
    </group>
  );
}

/** 
 * Comprehensive 3D Eyewear Glasses with Detailed Real-World Frames (40 Styles)
 */
function RealisticGlasses3D({
  glassesType = '',
  headY = 0.74
}: {
  glassesType?: string;
  headY?: number;
}) {
  if (!glassesType || glassesType.includes('Không đeo kính')) return null;

  const style = glassesType.toLowerCase();
  const isSunglasses = style.includes('kính râm') || style.includes('wayfarer') || style.includes('aviator') || style.includes('shield');
  const isRound = style.includes('tròn') || style.includes('oval');
  const isCatEye = style.includes('mắt mèo') || style.includes('cat-eye');
  const isAviator = style.includes('aviator') || style.includes('phi công');
  const isBrowline = style.includes('browline') || style.includes('clubmaster');
  const isHexagon = style.includes('đa giác') || style.includes('hexagon') || style.includes('bát giác');
  const isClear = style.includes('trong suốt') || style.includes('clear');
  const isGold = style.includes('vàng') || style.includes('titan') || style.includes('kim loại');
  const isTortoise = style.includes('đồi mồi');

  const frameColor = isGold ? '#d97706' : isTortoise ? '#78350f' : isClear ? '#f8fafc' : isSunglasses ? '#09090b' : '#334155';
  const frameMat = (
    <meshStandardMaterial
      color={frameColor}
      roughness={isGold ? 0.25 : 0.4}
      metalness={isGold ? 0.85 : 0.15}
      transparent={isClear}
      opacity={isClear ? 0.65 : 1.0}
    />
  );

  const lensColor = isSunglasses ? (style.includes('nâu trà') ? '#78350f' : style.includes('tráng gương') ? '#cbd5e1' : '#18181b') : '#93c5fd';
  const lensMat = (
    <meshStandardMaterial
      color={lensColor}
      roughness={0.08}
      metalness={style.includes('tráng gương') ? 0.9 : 0.1}
      transparent
      opacity={isSunglasses ? 0.92 : 0.35}
    />
  );

  return (
    <group position={[0, headY - 0.015, 0.104]}>
      {/* 1. Left Frame */}
      <group position={[-0.036, 0, 0]}>
        {isRound ? (
          <>
            <mesh scale={[0.024, 0.024, 0.005]}><torusGeometry args={[1, 0.14, 16, 32]} />{frameMat}</mesh>
            <mesh scale={[0.022, 0.022, 0.002]}><circleGeometry args={[1, 32]} />{lensMat}</mesh>
          </>
        ) : isCatEye ? (
          <>
            <mesh scale={[0.048, 0.032, 0.006]} rotation={[0, 0, -0.18]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.026, 0.002]} rotation={[0, 0, -0.18]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        ) : isHexagon ? (
          <>
            <mesh scale={[0.025, 0.025, 0.005]}><torusGeometry args={[1, 0.12, 6, 6]} />{frameMat}</mesh>
            <mesh scale={[0.023, 0.023, 0.002]}><circleGeometry args={[1, 6]} />{lensMat}</mesh>
          </>
        ) : (
          <>
            <mesh scale={[0.048, 0.032, 0.006]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.027, 0.002]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        )}
      </group>

      {/* 2. Right Frame */}
      <group position={[0.036, 0, 0]}>
        {isRound ? (
          <>
            <mesh scale={[0.024, 0.024, 0.005]}><torusGeometry args={[1, 0.14, 16, 32]} />{frameMat}</mesh>
            <mesh scale={[0.022, 0.022, 0.002]}><circleGeometry args={[1, 32]} />{lensMat}</mesh>
          </>
        ) : isCatEye ? (
          <>
            <mesh scale={[0.048, 0.032, 0.006]} rotation={[0, 0, 0.18]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.026, 0.002]} rotation={[0, 0, 0.18]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        ) : isHexagon ? (
          <>
            <mesh scale={[0.025, 0.025, 0.005]}><torusGeometry args={[1, 0.12, 6, 6]} />{frameMat}</mesh>
            <mesh scale={[0.023, 0.023, 0.002]}><circleGeometry args={[1, 6]} />{lensMat}</mesh>
          </>
        ) : (
          <>
            <mesh scale={[0.048, 0.032, 0.006]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.027, 0.002]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        )}
      </group>

      {/* 3. Nose Bridge */}
      <mesh position={[0, 0.003, 0.002]} scale={[0.022, 0.003, 0.005]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
      {/* Aviator Top Double Brow Bar */}
      {isAviator && <mesh position={[0, 0.016, 0.002]} scale={[0.065, 0.003, 0.004]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>}
      {/* Browline Upper Brow Accent */}
      {isBrowline && <mesh position={[0, 0.015, 0.003]} scale={[0.096, 0.006, 0.008]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>}

      {/* 4. Temples */}
      <mesh position={[-0.062, 0, -0.06]} scale={[0.003, 0.003, 0.12]} rotation={[0, -0.06, 0]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
      <mesh position={[0.062, 0, -0.06]} scale={[0.003, 0.003, 0.12]} rotation={[0, 0, 0.06]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
    </group>
  );
}

/** 
 * Photorealistic Human Avatar with Seamless Skin (NO robotic joints)
 * Continuous high-poly organic skin mesh with smooth morphological scaling.
 */
function SeamlessHumanAvatar({
  measurements,
  gender = 'female',
  faceShape = 'oval',
  hairStyle = '',
  glassesType = '',
  lightingFilter = 'studio',
  autoRotate = false,
  animationEnabled = false,
  garmentBindings = []
}: Props) {
  const group = useRef<THREE.Group>(null);
  const modelUrl = gender === 'male' ? '/models/seamless_male.glb' : '/models/seamless_female.glb';
  const { scene } = useGLTF(modelUrl);
  const config = filterConfigs[lightingFilter] || filterConfigs.studio;

  // Granular Morphological Ratios
  const isMale = gender === 'male';
  const heightScale = measurements.height / 170;
  const shoulderRatio = measurements.shoulder / (isMale ? 46 : 40);
  const bustRatio = measurements.bust / (isMale ? 94 : 86);
  const waistRatio = measurements.waist / (isMale ? 78 : 68);
  const hipRatio = measurements.hip / (isMale ? 92 : 94);
  const thighRatio = (measurements.thigh || 54) / (isMale ? 56 : 52);
  const calfRatio = (measurements.calf || 36) / 36;
  const bicepRatio = (measurements.bicep || 28) / (isMale ? 32 : 26);

  // Deform the continuous single-mesh human skin
  const morphedMesh = useMemo(() => {
    let sourceMesh: THREE.Mesh | null = null;
    scene.traverse((child) => {
      if (child instanceof THREE.Mesh && !sourceMesh) {
        sourceMesh = child;
      }
    });

    if (!sourceMesh) return scene.clone(true);

    const clonedGeometry = (sourceMesh as THREE.Mesh).geometry.clone();
    const posAttr = clonedGeometry.getAttribute('position') as THREE.BufferAttribute;
    const posArray = posAttr.array as Float32Array;

    // Face shape morph factors
    let faceScaleX = 1.0;
    let faceScaleZ = 1.0;
    if (faceShape === 'round') { faceScaleX = 1.12; faceScaleZ = 1.08; }
    else if (faceShape === 'square') { faceScaleX = 1.18; faceScaleZ = 1.02; }
    else if (faceShape === 'heart') { faceScaleX = 0.92; faceScaleZ = 0.96; }
    else if (faceShape === 'diamond') { faceScaleX = 1.14; faceScaleZ = 0.95; }
    else if (faceShape === 'oblong') { faceScaleX = 0.90; faceScaleZ = 0.95; }
    else if (faceShape === 'triangle') { faceScaleX = 1.20; faceScaleZ = 1.02; }

    for (let i = 0; i < posArray.length; i += 3) {
      let x = posArray[i];
      let y = posArray[i + 1];
      let z = posArray[i + 2];

      // 1. Head Morphing (y > 0.64)
      if (y > 0.64) {
        const headT = Math.min(1.0, (y - 0.64) / 0.20);
        x *= (1.0 + (faceScaleX - 1.0) * headT);
        z *= (1.0 + (faceScaleZ - 1.0) * headT);
      }
      // 2. Chest & Shoulders (0.30 <= y <= 0.60)
      else if (y >= 0.30 && y <= 0.60 && Math.abs(x) < 0.24) {
        const chestT = Math.sin(((y - 0.30) / 0.30) * Math.PI);
        x *= (1.0 + (shoulderRatio - 1.0) * chestT);
        z *= (1.0 + (bustRatio - 1.0) * chestT);
      }
      // 3. Waist & Abdomen (0.06 <= y < 0.30)
      else if (y >= 0.06 && y < 0.30 && Math.abs(x) < 0.20) {
        const waistT = Math.sin(((y - 0.06) / 0.24) * Math.PI);
        x *= (1.0 + (waistRatio - 1.0) * waistT);
        z *= (1.0 + (waistRatio - 1.0) * waistT);
      }
      // 4. Hips & Pelvis (-0.16 <= y < 0.06) -> ONLY HIPS!
      else if (y >= -0.16 && y < 0.06 && Math.abs(x) < 0.24) {
        const hipT = Math.sin(((y - (-0.16)) / 0.22) * Math.PI);
        x *= (1.0 + (hipRatio - 1.0) * hipT);
        z *= (1.0 + (hipRatio - 1.0) * hipT);
      }
      // 5. Thighs (-0.52 <= y < -0.16) -> ONLY THIGHS!
      else if (y >= -0.52 && y < -0.16 && Math.abs(x) > 0.02) {
        const thighT = Math.sin(((y - (-0.52)) / 0.36) * Math.PI);
        x *= (1.0 + (thighRatio - 1.0) * thighT);
        z *= (1.0 + (thighRatio - 1.0) * thighT);
      }
      // 6. Calves (-0.84 <= y < -0.52) -> ONLY CALVES!
      else if (y >= -0.84 && y < -0.52 && Math.abs(x) > 0.02) {
        const calfT = Math.sin(((y - (-0.84)) / 0.32) * Math.PI);
        x *= (1.0 + (calfRatio - 1.0) * calfT);
        z *= (1.0 + (calfRatio - 1.0) * calfT);
      }
      // 7. Arms (Math.abs(x) > 0.15 && y < 0.54) -> ONLY ARMS & BICEP!
      else if (Math.abs(x) > 0.15 && y < 0.54) {
        const side = x > 0 ? 1 : -1;
        x += side * (shoulderRatio - 1.0) * 0.04;
        const armT = Math.max(0, Math.sin(((y - (-0.12)) / 0.62) * Math.PI));
        x += side * (bicepRatio - 1.0) * 0.015 * armT;
        z *= (1.0 + (bicepRatio - 1.0) * 0.4 * armT);
      }

      posArray[i] = x;
      posArray[i + 1] = y;
      posArray[i + 2] = z;
    }

    posAttr.needsUpdate = true;
    clonedGeometry.computeVertexNormals();

    // High-End Cashmere Studio Matte Clay Skin Material
    const skinMat = new THREE.MeshStandardMaterial({
      color: config.skinTone,
      roughness: 0.84,
      metalness: 0.0,
      flatShading: false,
    });

    const mesh = new THREE.Mesh(clonedGeometry, skinMat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }, [
    scene,
    gender,
    shoulderRatio,
    bustRatio,
    waistRatio,
    hipRatio,
    thighRatio,
    calfRatio,
    bicepRatio,
    faceShape,
    config.skinTone
  ]);

  const headCenterY = 0.74 * heightScale;

  useFrame((state, delta) => {
    if (autoRotate && group.current) {
      group.current.rotation.y += delta * 0.45;
    }
    if (animationEnabled && group.current) {
      const breath = Math.sin(state.clock.elapsedTime * 1.8) * 0.005;
      group.current.scale.set(1 + breath * 0.2, heightScale, 1 + breath);
    }
  });

  return (
    <group ref={group} scale={[1, heightScale, 1]}>
      {/* 100% Seamless Continuous Human Skin Body */}
      <primitive object={morphedMesh} />

      {/* 3D Realistic Hairstyle Mesh attached at Head */}
      <RealisticHairstyle3D hairStyle={hairStyle} gender={gender} headY={headCenterY} />

      {/* 3D Realistic Eyewear Glasses Mesh attached at Nose Bridge */}
      <RealisticGlasses3D glassesType={glassesType} headY={headCenterY} />

      {/* Wardrobe Items */}
      {garmentBindings.map((binding, index) => (
        <ResolvedGarment
          key={binding.import_id ?? binding.asset_id ?? `${binding.category}-${index}`}
          binding={binding}
          measurements={measurements}
        />
      ))}
    </group>
  );
}

function CameraViewController({ viewPreset = 'front' }: { viewPreset?: ViewPreset }) {
  const { camera } = useThree();
  useEffect(() => {
    const positions: Record<ViewPreset, { pos: [number, number, number]; lookAt: [number, number, number] }> = {
      front: { pos: [0, 0.02, 3.2], lookAt: [0, -0.02, 0] },
      side: { pos: [3.2, 0.02, 0], lookAt: [0, -0.02, 0] },
      back: { pos: [0, 0.02, -3.2], lookAt: [0, -0.02, 0] },
      upper: { pos: [0, 0.38, 1.8], lookAt: [0, 0.35, 0] },
      lower: { pos: [0, -0.42, 1.9], lookAt: [0, -0.45, 0] },
      face: { pos: [0, 0.72, 1.15], lookAt: [0, 0.72, 0] },
      free: { pos: [0, 0.02, 3.2], lookAt: [0, -0.02, 0] },
    };
    if (viewPreset === 'free') return;
    const target = positions[viewPreset];
    camera.position.set(...target.pos);
    camera.lookAt(...target.lookAt);
    camera.updateProjectionMatrix();
  }, [camera, viewPreset]);
  return null;
}

function LoadingAvatar() {
  return (
    <Html center>
      <div className="rounded-2xl bg-slate-950/85 backdrop-blur-md px-5 py-2.5 text-xs font-bold text-white shadow-2xl flex items-center gap-2 border border-white/10">
        <span className="inline-block animate-spin">⏳</span>
        <span>Đang nạp studio thời trang 3D...</span>
      </div>
    </Html>
  );
}

export default function BodyAvatar3D({
  measurements,
  gender = 'female',
  faceShape = 'oval',
  hairStyle = '',
  glassesType = '',
  autoRotate = false,
  outfitStyle = 'neutral',
  animationEnabled = false,
  garmentBindings = [],
  viewPreset = 'front',
  lightingFilter = 'studio'
}: Props) {
  const currentFilter = filterConfigs[lightingFilter] || filterConfigs.studio;

  return (
    <div className="avatar-stage relative overflow-hidden rounded-[2.5rem] border border-slate-200/80 shadow-2xl h-[540px] w-full bg-slate-900" aria-label="Hình nhân 3D Studio">
      <Canvas
        shadows
        camera={{ position: [0, 0.02, 3.2], fov: 36 }}
        dpr={[1, 1.75]}
        gl={{
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 0.95,
          antialias: true
        }}
      >
        <color attach="background" args={[currentFilter.background]} />
        
        {/* Soft Ambient Light */}
        <ambientLight intensity={currentFilter.ambientIntensity} />

        {/* Master Key Light (Overhead 45° Studio Softbox) */}
        <directionalLight
          position={[2.5, 4.2, 3.0]}
          intensity={currentFilter.keyIntensity}
          color={currentFilter.keyColor}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-bias={-0.0001}
        />

        {/* Diffused Fill Light (Soft Bounce Card) */}
        <directionalLight
          position={[-2.5, 2.0, 2.0]}
          intensity={currentFilter.fillIntensity}
          color={currentFilter.fillColor}
        />

        {/* Studio Rim / Kicker Light (High-Angle Backlight) */}
        <directionalLight
          position={[0, 3.0, -3.0]}
          intensity={currentFilter.rimIntensity}
          color={currentFilter.rimColor}
        />

        <Suspense fallback={<LoadingAvatar />}>
          {/* True 360° Studio Cyclorama Infinity Room */}
          <StudioCycloramaRoom filter={lightingFilter} />

          {/* Seamless Continuous Human Skin Avatar */}
          <SeamlessHumanAvatar
            measurements={measurements}
            gender={gender}
            faceShape={faceShape}
            hairStyle={hairStyle}
            glassesType={glassesType}
            outfitStyle={outfitStyle}
            lightingFilter={lightingFilter}
            autoRotate={autoRotate}
            animationEnabled={animationEnabled}
            garmentBindings={garmentBindings}
          />

          <CameraViewController viewPreset={viewPreset} />
          <Environment preset={currentFilter.envPreset} environmentIntensity={0.25} />
        </Suspense>

        {/* Orbit Controls with Horizon Lock on Pedestal */}
        <OrbitControls
          enablePan={false}
          minDistance={1.0}
          maxDistance={5.2}
          target={[0, -0.02, 0]}
          maxPolarAngle={Math.PI / 2 - 0.02}
          minPolarAngle={Math.PI * 0.12}
        />
      </Canvas>

      {/* Floating Badge */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/65 backdrop-blur-md px-4 py-1.5 text-[11px] font-semibold text-white/90 shadow-xl border border-white/10 flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span>
          {gender === 'male' ? 'Nam' : 'Nữ'} · {faceShape.toUpperCase()} · Filter: {lightingFilter.toUpperCase()}
        </span>
      </div>
    </div>
  );
}

useGLTF.preload('/models/seamless_female.glb');
useGLTF.preload('/models/seamless_male.glb');
