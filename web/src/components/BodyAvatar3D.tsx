'use client';

import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Environment, Html, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import * as SkeletonUtils from 'three/examples/jsm/utils/SkeletonUtils.js';

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
  accentTone: string;
  envPreset: 'studio' | 'sunset' | 'city' | 'apartment' | 'park';
}> = {
  studio: {
    background: '#e2e8f0',
    ambientIntensity: 0.65,
    keyIntensity: 0.95,
    keyColor: '#fffdf5',
    fillIntensity: 0.40,
    fillColor: '#94a3b8',
    rimIntensity: 0.30,
    rimColor: '#cbd5e1',
    podiumColor: '#f1f5f9',
    podiumRimColor: '#6366f1',
    skinTone: '#d8c5b2',
    accentTone: '#475569',
    envPreset: 'studio',
  },
  sunset: {
    background: '#fef3c7',
    ambientIntensity: 0.55,
    keyIntensity: 1.05,
    keyColor: '#fed7aa',
    fillIntensity: 0.40,
    fillColor: '#f472b6',
    rimIntensity: 0.35,
    rimColor: '#fde68a',
    podiumColor: '#ffedd5',
    podiumRimColor: '#f97316',
    skinTone: '#ddc2a9',
    accentTone: '#c2410c',
    envPreset: 'sunset',
  },
  cyberpunk: {
    background: '#09090b',
    ambientIntensity: 0.45,
    keyIntensity: 1.20,
    keyColor: '#38bdf8',
    fillIntensity: 0.70,
    fillColor: '#f43f5e',
    rimIntensity: 0.75,
    rimColor: '#c084fc',
    podiumColor: '#18181b',
    podiumRimColor: '#06b6d4',
    skinTone: '#94a3b8',
    accentTone: '#06b6d4',
    envPreset: 'city',
  },
  minimalist: {
    background: '#f1f5f9',
    ambientIntensity: 0.70,
    keyIntensity: 0.85,
    keyColor: '#ffffff',
    fillIntensity: 0.35,
    fillColor: '#cbd5e1',
    rimIntensity: 0.20,
    rimColor: '#e2e8f0',
    podiumColor: '#ffffff',
    podiumRimColor: '#cbd5e1',
    skinTone: '#d1beaa',
    accentTone: '#64748b',
    envPreset: 'apartment',
  },
  vintage: {
    background: '#f5edd6',
    ambientIntensity: 0.55,
    keyIntensity: 0.95,
    keyColor: '#fde68a',
    fillIntensity: 0.35,
    fillColor: '#d97706',
    rimIntensity: 0.30,
    rimColor: '#fef08a',
    podiumColor: '#fef3c7',
    podiumRimColor: '#d97706',
    skinTone: '#d4bea5',
    accentTone: '#92400e',
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
      <group position={[0, 1.20, 0.01]}>
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
    return <mesh position={[0, 1.16, 0.02]} scale={[shoulderWidth * 2.2, 0.45, bustDepth * 1.4]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>;
  }
  if (category === 'bottom') {
    const legWidth = profile.leg_shape === 'wide' ? 0.22 : profile.leg_shape === 'skinny' ? 0.13 : 0.16;
    return (
      <group position={[0, 0.82, 0.01]}>
        <mesh position={[0, 0.05, 0]} scale={[hipWidth * 2.0, 0.18, hipWidth * 1.2]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[-0.09, -legLen * 0.46, 0]} scale={[legWidth, legLen * 0.85, legWidth * 1.1]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[0.09, -legLen * 0.46, 0]} scale={[legWidth, legLen * 0.85, legWidth * 1.1]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
      </group>
    );
  }
  if (category === 'dress') {
    return <mesh position={[0, 0.95, 0.01]} scale={[hipWidth * 2.0, 0.65, bustDepth * 1.25]}><cylinderGeometry args={[0.24, 0.36, 1, 24]} />{material}</mesh>;
  }
  if (category === 'belt') {
    return <mesh position={[0, 1.02, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[waistWidth * 2.0, waistWidth * 1.6, 0.04]}><torusGeometry args={[0.5, 0.04, 12, 32]} />{material}</mesh>;
  }
  if (category === 'footwear') {
    return (
      <group position={[0, 0.02, 0.03]}>
        <mesh position={[-0.09, 0, 0]} scale={[0.10, 0.06, 0.22]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
        <mesh position={[0.09, 0, 0]} scale={[0.10, 0.06, 0.22]}><boxGeometry args={[1, 1, 1]} />{material}</mesh>
      </group>
    );
  }
  return <mesh position={[0, 1.02, 0.24]} scale={[0.24, 0.24, 0.05]}><circleGeometry args={[1, 24]} />{material}</mesh>;
}

function ResolvedGarment({ binding, measurements }: { binding: TryOnGarmentBinding; measurements: BodyMeasurements }) {
  return <GarmentProxy binding={binding} measurements={measurements} />;
}

/** 3D Studio Pedestal Platform under the Mannequin */
function StudioPedestal({ filter }: { filter: LightingFilter }) {
  const config = filterConfigs[filter] || filterConfigs.studio;
  return (
    <group position={[0, -0.98, 0]}>
      <mesh position={[0, -0.02, 0]} receiveShadow>
        <cylinderGeometry args={[1.05, 1.10, 0.06, 64]} />
        <meshStandardMaterial color={config.podiumColor} roughness={0.70} metalness={0.05} />
      </mesh>
      <mesh position={[0, -0.02, 0]}>
        <cylinderGeometry args={[1.102, 1.105, 0.03, 64]} />
        <meshStandardMaterial
          color={config.podiumRimColor}
          emissive={config.podiumRimColor}
          emissiveIntensity={filter === 'cyberpunk' ? 0.6 : 0.25}
          roughness={0.4}
          metalness={0.3}
        />
      </mesh>
      <mesh position={[0, -0.08, 0]} receiveShadow>
        <cylinderGeometry args={[1.18, 1.25, 0.08, 64]} />
        <meshStandardMaterial color={config.podiumColor} roughness={0.75} metalness={0.02} />
      </mesh>
      <mesh position={[0, -0.121, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[16, 16]} />
        <shadowMaterial opacity={0.30} />
      </mesh>
    </group>
  );
}

/** Seamless Studio Cyclorama Backdrop */
function StudioBackdrop({ filter }: { filter: LightingFilter }) {
  const config = filterConfigs[filter] || filterConfigs.studio;
  return (
    <group position={[0, 0.0, -3.0]}>
      <mesh receiveShadow>
        <planeGeometry args={[14, 10]} />
        <meshStandardMaterial color={config.background} roughness={0.95} metalness={0.0} />
      </mesh>
    </group>
  );
}

/** 3D Realistic Hairstyle Mesh attached to Head */
function FashionHairstyle3D({
  hairStyle = '',
  gender = 'female'
}: {
  hairStyle?: string;
  gender?: GenderType;
}) {
  const hairMat = <meshStandardMaterial color="#221710" roughness={0.75} metalness={0.05} />;
  const style = hairStyle.toLowerCase();

  // Short Men / Pixie Hair Styles
  if (
    gender === 'male' ||
    style.includes('crop') ||
    style.includes('undercut') ||
    style.includes('buzz') ||
    style.includes('fade') ||
    style.includes('pompadour') ||
    style.includes('quiff') ||
    style.includes('side part') ||
    style.includes('two block') ||
    style.includes('pixie')
  ) {
    const isBuzz = style.includes('buzz');
    const isPompadour = style.includes('pompadour') || style.includes('quiff');
    const volumeHeight = isBuzz ? 0.02 : isPompadour ? 0.06 : 0.038;

    return (
      <group position={[0, 1.56, 0.01]}>
        <mesh position={[0, 0.06, -0.01]}>
          <sphereGeometry args={[0.098, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
          {hairMat}
        </mesh>
        <mesh position={[0, 0.08 + volumeHeight * 0.5, 0.01]} scale={[0.145, volumeHeight, 0.155]}>
          <boxGeometry args={[1, 1, 1]} />
          {hairMat}
        </mesh>
        <mesh position={[-0.082, 0.02, 0.0]} scale={[0.018, 0.07, 0.11]}>
          <boxGeometry args={[1, 1, 1]} />
          {hairMat}
        </mesh>
        <mesh position={[0.082, 0.02, 0.0]} scale={[0.018, 0.07, 0.11]}>
          <boxGeometry args={[1, 1, 1]} />
          {hairMat}
        </mesh>
      </group>
    );
  }

  // Long / Layer / Wave / Bob Women Styles
  const isBob = style.includes('bob') || style.includes('french bob') || style.includes('layer bob');
  const isLong = style.includes('long') || style.includes('wave') || style.includes('butterfly') || style.includes('hime') || style.includes('straight');
  const hairLength = isLong ? 0.42 : isBob ? 0.20 : 0.30;

  return (
    <group position={[0, 1.56, 0.01]}>
      <mesh position={[0, 0.06, -0.01]}>
        <sphereGeometry args={[0.102, 28, 28, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
        {hairMat}
      </mesh>
      <mesh position={[-0.088, -hairLength * 0.35, 0.01]} scale={[0.036, hairLength, 0.10]} rotation={[0, 0, -0.06]}>
        <cylinderGeometry args={[0.6, 0.9, 1, 16]} />
        {hairMat}
      </mesh>
      <mesh position={[0.088, -hairLength * 0.35, 0.01]} scale={[0.036, hairLength, 0.10]} rotation={[0, 0, 0.06]}>
        <cylinderGeometry args={[0.6, 0.9, 1, 16]} />
        {hairMat}
      </mesh>
      <mesh position={[0, -hairLength * 0.38, -0.07]} scale={[0.15, hairLength, 0.05]} rotation={[0.05, 0, 0]}>
        <boxGeometry args={[1, 1, 1]} />
        {hairMat}
      </mesh>
    </group>
  );
}

/** 3D Realistic Eyewear Glasses Mesh attached strictly to Nose Bridge */
function FashionGlasses3D({
  glassesType = ''
}: {
  glassesType?: string;
}) {
  if (!glassesType || glassesType.includes('Không đeo kính')) return null;

  const isSunglasses = glassesType.includes('Kính Râm') || glassesType.includes('Wayfarer') || glassesType.includes('Aviator') || glassesType.includes('Shield');
  const isRound = glassesType.includes('Tròn') || glassesType.includes('Oval');
  const isGold = glassesType.includes('Vàng') || glassesType.includes('Titan') || glassesType.includes('Kim Loại');

  const frameColor = isGold ? '#d97706' : isSunglasses ? '#09090b' : '#334155';
  const frameMat = <meshStandardMaterial color={frameColor} roughness={0.3} metalness={isGold ? 0.8 : 0.2} />;
  const lensColor = isSunglasses ? '#18181b' : '#93c5fd';
  const lensMat = <meshStandardMaterial color={lensColor} roughness={0.1} metalness={0.1} transparent opacity={isSunglasses ? 0.92 : 0.4} />;

  return (
    <group position={[0, 1.54, 0.105]}>
      {/* Left Frame */}
      <group position={[-0.036, 0, 0]}>
        {isRound ? (
          <>
            <mesh scale={[0.024, 0.024, 0.005]}><torusGeometry args={[1, 0.14, 12, 24]} />{frameMat}</mesh>
            <mesh scale={[0.022, 0.022, 0.002]}><circleGeometry args={[1, 24]} />{lensMat}</mesh>
          </>
        ) : (
          <>
            <mesh scale={[0.048, 0.032, 0.006]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.027, 0.002]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        )}
      </group>

      {/* Right Frame */}
      <group position={[0.036, 0, 0]}>
        {isRound ? (
          <>
            <mesh scale={[0.024, 0.024, 0.005]}><torusGeometry args={[1, 0.14, 12, 24]} />{frameMat}</mesh>
            <mesh scale={[0.022, 0.022, 0.002]}><circleGeometry args={[1, 24]} />{lensMat}</mesh>
          </>
        ) : (
          <>
            <mesh scale={[0.048, 0.032, 0.006]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
            <mesh scale={[0.042, 0.027, 0.002]}><boxGeometry args={[1, 1, 1]} />{lensMat}</mesh>
          </>
        )}
      </group>

      {/* Nose Bridge */}
      <mesh position={[0, 0.003, 0.002]} scale={[0.022, 0.003, 0.005]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
      {/* Temples */}
      <mesh position={[-0.062, 0, -0.06]} scale={[0.003, 0.003, 0.12]} rotation={[0, -0.06, 0]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
      <mesh position={[0.062, 0, -0.06]} scale={[0.003, 0.003, 0.12]} rotation={[0, 0, 0.06]}><boxGeometry args={[1, 1, 1]} />{frameMat}</mesh>
    </group>
  );
}

/** 
 * Realistic Human Fashion Mannequin
 */
function RealisticMannequinAvatar({
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
  const { scene } = useGLTF('/models/Xbot.glb');
  const avatar = useMemo(() => SkeletonUtils.clone(scene), [scene]);
  const config = filterConfigs[lightingFilter] || filterConfigs.studio;

  // Granular Anatomical Ratios
  const isMale = gender === 'male';
  const heightRatio = measurements.height / 170;
  const shoulderRatio = measurements.shoulder / (isMale ? 46 : 40);
  const bustRatio = measurements.bust / (isMale ? 94 : 86);
  const waistRatio = measurements.waist / (isMale ? 78 : 68);
  const hipRatio = measurements.hip / (isMale ? 92 : 94);
  const thighRatio = (measurements.thigh || 54) / (isMale ? 56 : 52);
  const calfRatio = (measurements.calf || 36) / 36;
  const bicepRatio = (measurements.bicep || 28) / (isMale ? 32 : 26);
  const neckRatio = (measurements.neck || 36) / (isMale ? 38 : 34);
  const inseamRatio = measurements.inseam / 78;

  useEffect(() => {
    // 1. Overall Vertical Height & Proportions
    avatar.scale.set(0.92, heightRatio * 0.92, 0.92);

    // 2. High-End Studio Cashmere Clay Matte Material for Mannequin
    const skinMat = new THREE.MeshStandardMaterial({
      color: config.skinTone,
      roughness: 0.84,
      metalness: 0.0,
      flatShading: false,
    });

    const jointMat = new THREE.MeshStandardMaterial({
      color: config.accentTone,
      roughness: 0.70,
      metalness: 0.1,
    });

    avatar.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
        object.material = object.name.includes('001') ? jointMat : skinMat;
        if (object.geometry) {
          object.geometry.computeVertexNormals();
        }
      }

      if (object instanceof THREE.Bone) {
        const boneName = object.name.toLowerCase();

        // 1. Hips -> ONLY SCALES HIPS WIDTH & DEPTH
        if (boneName.includes('hips')) {
          object.scale.set(hipRatio, 1.0, hipRatio);
        }

        // 2. Waist (Spine) -> ONLY SCALES WAIST
        if (boneName.includes('spine') && !boneName.includes('spine1') && !boneName.includes('spine2')) {
          object.scale.set(waistRatio / hipRatio, 1.0, waistRatio / hipRatio);
        }

        // 3. Chest & Bust (Spine1 / Spine2) -> ONLY SCALES CHEST
        if (boneName.includes('spine1') || boneName.includes('spine2')) {
          const depthBust = measurements.chest_profile === 'full' ? bustRatio * 1.10 : bustRatio * 0.96;
          object.scale.set(bustRatio / waistRatio, 1.0, depthBust / waistRatio);
        }

        // 4. Shoulders -> ONLY SCALES SHOULDER WIDTH
        if (boneName.includes('shoulder')) {
          object.scale.x = shoulderRatio;
          if (measurements.shoulder_slope === 'sloped') {
            object.rotation.z = boneName.includes('left') ? -0.06 : 0.06;
          }
        }

        // 5. Neck -> ONLY SCALES NECK
        if (boneName.includes('neck')) {
          object.scale.set(neckRatio, 1.0, neckRatio);
        }

        // 6. Head -> MORPHED BY FACE SHAPE
        if (boneName.includes('head') && !boneName.includes('top')) {
          let headX = 1.0;
          let headZ = 1.0;
          if (faceShape === 'round') { headX = 1.10; headZ = 1.06; }
          else if (faceShape === 'square') { headX = 1.14; headZ = 1.02; }
          else if (faceShape === 'heart') { headX = 0.94; headZ = 0.96; }
          else if (faceShape === 'diamond') { headX = 1.10; headZ = 0.96; }
          else if (faceShape === 'oblong') { headX = 0.92; headZ = 0.96; }
          else if (faceShape === 'triangle') { headX = 1.15; headZ = 1.02; }
          object.scale.set(headX, 1.0, headZ);
        }

        // 7. Thighs (LeftUpLeg / RightUpLeg) -> ONLY SCALES THIGHS & INSEAM (Counteracts hip scaling!)
        if (boneName.includes('upleg')) {
          object.scale.set(thighRatio / hipRatio, inseamRatio, thighRatio / hipRatio);
          if (measurements.leg_alignment === 'bowed') {
            object.rotation.z = boneName.includes('left') ? -0.04 : 0.04;
          }
        }

        // 8. Calves (LeftLeg / RightLeg) -> ONLY SCALES CALF (Counteracts thigh scaling!)
        if (boneName.includes('leg') && !boneName.includes('upleg')) {
          object.scale.set(calfRatio / thighRatio, 1.0, calfRatio / thighRatio);
        }

        // 9. Arms & Biceps (LeftArm / RightArm) -> Lowered arms in natural fashion rest pose
        if (boneName.includes('arm') && !boneName.includes('forearm')) {
          object.scale.set(bicepRatio, 1.0, bicepRatio);
          // Natural resting arm pose down along torso
          if (boneName.includes('left')) {
            object.rotation.z = -1.25;
            object.rotation.x = 0.05;
          }
          if (boneName.includes('right')) {
            object.rotation.z = 1.25;
            object.rotation.x = 0.05;
          }
        }

        if (boneName.includes('forearm')) {
          if (boneName.includes('left')) object.rotation.y = 0.15;
          if (boneName.includes('right')) object.rotation.y = -0.15;
        }
      }
    });
  }, [
    avatar,
    gender,
    heightRatio,
    shoulderRatio,
    bustRatio,
    waistRatio,
    hipRatio,
    thighRatio,
    calfRatio,
    bicepRatio,
    neckRatio,
    inseamRatio,
    faceShape,
    measurements.shoulder_slope,
    measurements.chest_profile,
    measurements.leg_alignment,
    config.skinTone,
    config.accentTone,
  ]);

  useFrame((state, delta) => {
    if (autoRotate && group.current) {
      group.current.rotation.y += delta * 0.45;
    }
    if (animationEnabled && group.current) {
      const breath = Math.sin(state.clock.elapsedTime * 1.8) * 0.005;
      group.current.scale.set(1 + breath * 0.2, 1, 1 + breath);
    }
  });

  return (
    <group ref={group} position={[0, -0.96, 0]}>
      {/* Authentic Rigged Realistic Mannequin */}
      <primitive object={avatar} />

      {/* 3D Hairstyle Mesh attached at Head */}
      <FashionHairstyle3D hairStyle={hairStyle} gender={gender} />

      {/* 3D Eyewear Glasses Mesh attached at Nose Bridge */}
      <FashionGlasses3D glassesType={glassesType} />

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
      front: { pos: [0, 0.0, 3.5], lookAt: [0, -0.05, 0] },
      side: { pos: [3.5, 0.0, 0], lookAt: [0, -0.05, 0] },
      back: { pos: [0, 0.0, -3.5], lookAt: [0, -0.05, 0] },
      upper: { pos: [0, 0.35, 2.0], lookAt: [0, 0.32, 0] },
      lower: { pos: [0, -0.45, 2.0], lookAt: [0, -0.48, 0] },
      face: { pos: [0, 0.58, 1.25], lookAt: [0, 0.58, 0] },
      free: { pos: [0, 0.0, 3.5], lookAt: [0, -0.05, 0] },
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
        <span>Đang nạp người mẫu thời trang 3D...</span>
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
    <div className="avatar-stage relative overflow-hidden rounded-[2.5rem] border border-slate-200/80 shadow-2xl h-[540px] w-full bg-slate-200" aria-label="Hình nhân 3D Studio">
      <Canvas
        shadows
        camera={{ position: [0, 0.0, 3.5], fov: 36 }}
        dpr={[1, 1.75]}
        gl={{
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 0.92,
          antialias: true
        }}
      >
        <color attach="background" args={[currentFilter.background]} />
        
        {/* Soft Ambient Light */}
        <ambientLight intensity={currentFilter.ambientIntensity} />

        {/* Soft Key Light */}
        <directionalLight
          position={[2.5, 4.0, 3.0]}
          intensity={currentFilter.keyIntensity}
          color={currentFilter.keyColor}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-bias={-0.0001}
        />

        {/* Diffused Fill Light */}
        <directionalLight
          position={[-2.5, 2.0, 2.0]}
          intensity={currentFilter.fillIntensity}
          color={currentFilter.fillColor}
        />

        {/* Soft Rim Light */}
        <directionalLight
          position={[0, 2.5, -3.0]}
          intensity={currentFilter.rimIntensity}
          color={currentFilter.rimColor}
        />

        <Suspense fallback={<LoadingAvatar />}>
          {/* Studio Backdrop */}
          <StudioBackdrop filter={lightingFilter} />

          {/* 3D Pedestal Stand under Mannequin */}
          <StudioPedestal filter={lightingFilter} />

          {/* Realistic Rigged Mannequin Avatar */}
          <RealisticMannequinAvatar
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
          target={[0, -0.05, 0]}
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

useGLTF.preload('/models/Xbot.glb');
