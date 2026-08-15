"use client"

import { useEffect, useMemo, useRef } from "react"
import { AdaptiveDpr, CameraControls, Line, Preload, Stars } from "@react-three/drei"
import { Canvas, useFrame } from "@react-three/fiber"
import { Bloom, EffectComposer } from "@react-three/postprocessing"
import { useReducedMotion } from "motion/react"
import type { Group } from "three"

import type { CameraPose, InvestigationPresentationState } from "./model/presentation-state"

type Point3 = [number, number, number]

const TARGET_STAR_RADIUS = 0.64

const CAMERA_POSES: Record<
  CameraPose,
  { position: Point3; target: Point3; fov: number }
> = {
  field: { position: [0, 2.7, 8.8], target: [0, 1.25, 0], fov: 46 },
  candidate: { position: [0.4, 2.55, 7.1], target: [0, 1.25, 0], fov: 43 },
  transit: { position: [1.7, 1.7, 4.7], target: [0, 1.25, 0], fov: 39 },
  measurement: { position: [2.1, 2.3, 6.2], target: [0, 1.1, 0], fov: 42 },
  alternatives: { position: [0.2, 3.45, 8.1], target: [0, 1.25, 0], fov: 45 },
  lock: { position: [0, 2.4, 7.4], target: [0, 1.25, 0], fov: 42 },
}

function circlePoints(radius: number, segments = 128): Point3[] {
  return Array.from({ length: segments + 1 }, (_, index) => {
    const angle = (index / segments) * Math.PI * 2
    return [Math.cos(angle) * radius, 0, Math.sin(angle) * radius]
  })
}

function InvestigationCamera({ pose }: { pose: CameraPose }) {
  const controls = useRef<CameraControls>(null)
  const shouldReduceMotion = useReducedMotion()

  useEffect(() => {
    const next = CAMERA_POSES[pose]
    void controls.current?.setLookAt(
      ...next.position,
      ...next.target,
      !shouldReduceMotion,
    )
  }, [pose, shouldReduceMotion])

  return (
    <CameraControls
      ref={controls}
      makeDefault
      minDistance={4.2}
      maxDistance={10}
      minPolarAngle={Math.PI * 0.28}
      maxPolarAngle={Math.PI * 0.64}
      azimuthRotateSpeed={0.22}
      polarRotateSpeed={0.18}
      dollySpeed={0.15}
      truckSpeed={0}
    />
  )
}

function TargetStar({ quiet }: { quiet: boolean }) {
  return (
    <group>
      <mesh>
        <sphereGeometry args={[TARGET_STAR_RADIUS, 64, 64]} />
        <meshStandardMaterial
          color="#d9f6f3"
          emissive="#70ccd0"
          emissiveIntensity={quiet ? 1.1 : 2.1}
          roughness={0.72}
        />
      </mesh>
      <mesh scale={1.16}>
        <sphereGeometry args={[TARGET_STAR_RADIUS, 48, 48]} />
        <meshBasicMaterial color="#70ccd0" transparent opacity={quiet ? 0.045 : 0.08} />
      </mesh>
    </group>
  )
}

function CandidateSystem({
  visible,
  transitVisible,
  alternativesVisible,
  locked,
}: {
  visible: boolean
  transitVisible: boolean
  alternativesVisible: boolean
  locked: boolean
}) {
  const orbitingGroup = useRef<Group>(null)
  const shouldReduceMotion = useReducedMotion()
  const orbit = useMemo(() => circlePoints(2.35), [])
  const innerAlternative = useMemo(() => circlePoints(1.58), [])
  const outerAlternative = useMemo(() => circlePoints(3.12), [])

  useFrame((_, delta) => {
    if (orbitingGroup.current && visible && !locked && !shouldReduceMotion) {
      orbitingGroup.current.rotation.y += delta * 0.075
    }
  })

  if (!visible) return null

  return (
    <group rotation={[0.08, 0.12, -0.12]}>
      <Line points={orbit} color="#65dce4" lineWidth={0.72} transparent opacity={0.66} />
      <group ref={orbitingGroup}>
        <mesh position={[2.35, 0, 0]}>
          <sphereGeometry args={[0.115, 32, 32]} />
          <meshStandardMaterial color="#b7d6d9" roughness={0.92} metalness={0.08} />
        </mesh>
      </group>

      {transitVisible ? (
        <group rotation={[0, 0, 0.12]}>
          <Line
            points={[
              [-1.18, 0.18, 0.79],
              [1.18, 0.18, 0.79],
            ]}
            color="#8fe5e9"
            lineWidth={1.15}
            transparent
            opacity={0.9}
          />
          <mesh position={[0.44, 0.18, 0.83]}>
            <sphereGeometry args={[0.11, 24, 24]} />
            <meshBasicMaterial color="#071116" />
          </mesh>
        </group>
      ) : null}

      {alternativesVisible ? (
        <group rotation={[0, 0.08, 0]}>
          <Line
            points={innerAlternative}
            color="#eeb862"
            lineWidth={0.62}
            dashed
            dashSize={0.09}
            gapSize={0.07}
            transparent
            opacity={0.48}
          />
          <Line
            points={outerAlternative}
            color="#eeb862"
            lineWidth={0.58}
            dashed
            dashSize={0.09}
            gapSize={0.08}
            transparent
            opacity={0.35}
          />
        </group>
      ) : null}

      {locked ? (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[3.48, 0.012, 8, 180]} />
          <meshBasicMaterial color="#eeb862" transparent opacity={0.62} />
        </mesh>
      ) : null}
    </group>
  )
}

function InvestigationWorld({ state }: { state: InvestigationPresentationState }) {
  const candidateVisible = state.phase !== "observing"
  const transitVisible = ["characterizing", "measuring"].includes(state.phase)
  const alternativesVisible = ["challenging", "reviewing", "testing"].includes(state.phase)
  const locked = state.phase === "locked"
  const quiet = state.phase === "measuring" || state.phase === "locked"

  return (
    <>
      <color attach="background" args={["#02070a"]} />
      <fog attach="fog" args={["#02070a", 8, 28]} />
      <ambientLight intensity={0.28} />
      <pointLight position={[2.2, 2.5, 3]} intensity={22} color="#b8eceb" />
      <Stars
        radius={65}
        depth={24}
        count={700}
        factor={2.1}
        saturation={0}
        fade
        speed={locked ? 0 : 0.08}
      />
      <group position={[0, 1.25, 0]}>
        <TargetStar quiet={quiet} />
        <CandidateSystem
          visible={candidateVisible}
          transitVisible={transitVisible}
          alternativesVisible={alternativesVisible}
          locked={locked}
        />
      </group>
      <InvestigationCamera pose={state.cameraPose} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.32} luminanceThreshold={0.94} mipmapBlur />
      </EffectComposer>
      <AdaptiveDpr pixelated />
      <Preload all />
    </>
  )
}

export function CentralOrbitScene({ state }: { state: InvestigationPresentationState }) {
  const candidateVisible = state.phase !== "observing"
  const alternativesVisible = ["challenging", "reviewing", "testing"].includes(state.phase)

  return (
    <section
      className="investigation-canvas"
      aria-label="Schematic investigation geometry. The target star is shown first; candidate and alternative geometry appear only after matching evidence is introduced."
    >
      <Canvas
        aria-hidden="true"
        camera={{ position: CAMERA_POSES.field.position, fov: CAMERA_POSES.field.fov }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      >
        <InvestigationWorld state={state} />
      </Canvas>

      <div className="scene-caption" aria-live="polite">
        <span className="scene-caption-label">
          {alternativesVisible
            ? "Other orbits being tested"
            : candidateVisible
              ? "Possible orbit"
              : "Brightness only"}
        </span>
        <span>
          {candidateVisible
            ? "orbit sketch from measured timing · not a direct image"
            : "no orbit has been inferred yet"}
        </span>
      </div>
    </section>
  )
}
