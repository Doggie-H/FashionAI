import React, { useEffect, useMemo } from 'react'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

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

export default function RiggedMannequin({ 
  skinTone,
  height,
  weight,
  shoulder,
  bust,
  waist,
  hips
}: MannequinProps) {
  // Load the professional Xbot mannequin from Three.js examples
  const { scene } = useGLTF('/models/Xbot.glb')
  
  // Clone the scene so we can mutate it safely without affecting the cache
  const clonedScene = useMemo(() => scene.clone(), [scene])

  // Apply material colors based on skinTone
  useEffect(() => {
    clonedScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh
        // Create a new high-end plastic/clay material
        const newMaterial = new THREE.MeshStandardMaterial({
          color: skinTone === '#ffdbac' ? '#ffffff' : skinTone,
          roughness: 0.3,
          metalness: 0.1,
          clearcoat: 0.1,
        })
        mesh.material = newMaterial
        mesh.castShadow = true
        mesh.receiveShadow = true
      }
    })
  }, [clonedScene, skinTone])

  // Apply non-uniform scaling based on metrics
  useEffect(() => {
    const scaleY = height / 170
    const scaleXZ = Math.pow(weight / 60, 0.5)

    // Reset position before measuring to avoid cumulative shifts
    clonedScene.position.set(0, 0, 0)
    clonedScene.scale.set(scaleXZ, scaleY, scaleXZ)
    
    // Calculate bounding box after scaling
    const box = new THREE.Box3().setFromObject(clonedScene)
    
    // The pedestal is at y=-0.85 with height 0.1, so the top surface is exactly at y=-0.80
    // We shift the model down so its lowest point (box.min.y) sits exactly at -0.80
    clonedScene.position.set(0, -0.80 - box.min.y, 0)
    
  }, [clonedScene, height, weight, shoulder, bust, waist, hips])

  return <primitive object={clonedScene} />
}

useGLTF.preload('/models/Xbot.glb')

