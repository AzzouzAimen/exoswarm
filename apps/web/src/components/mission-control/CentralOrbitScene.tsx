"use client";

import { Canvas } from "@react-three/fiber";

export function CentralOrbitScene() {
  return (
    <section className="panel min-h-72 overflow-hidden p-0" aria-label="Mission-control scene">
      <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
        <ambientLight intensity={0.3} />
        <pointLight position={[3, 3, 3]} intensity={18} color="#67e8f9" />
        <mesh>
          <icosahedronGeometry args={[0.72, 2]} />
          <meshStandardMaterial color="#0f172a" emissive="#155e75" wireframe />
        </mesh>
      </Canvas>
      <p className="pointer-events-none relative -mt-10 pb-4 text-center text-xs text-slate-500">
        Scene awaiting investigation state
      </p>
    </section>
  );
}

