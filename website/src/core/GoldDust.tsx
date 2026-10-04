import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { AdditiveBlending, type Group, ShaderMaterial } from "three";
import { TOKENS } from "./states";

const COUNT = 420;
const SPAN_Y = 12; // world units the dust wraps over vertically

const VERT = /* glsl */ `
  attribute float aSize; attribute float aPhase;
  uniform float uTime; uniform float uScroll;
  varying float vTwinkle;
  void main() {
    vec3 p = position;
    // Slow upward drift; scrolling moves near dust faster than far dust (parallax).
    float depth = clamp((p.z + 6.0) / 8.0, 0.0, 1.0);
    p.y = mod(p.y + uTime * 0.06 + uScroll * (0.4 + depth * 1.4) + ${SPAN_Y / 2}.0, ${SPAN_Y}.0) - ${SPAN_Y / 2}.0;
    p.x += sin(uTime * 0.2 + aPhase * 6.0) * 0.08;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * (22.0 + depth * 30.0) / -mv.z;
    vTwinkle = 0.45 + 0.55 * sin(uTime * (0.6 + aPhase) + aPhase * 40.0);
    gl_Position = projectionMatrix * mv;
  }
`;
const FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uOpacity;
  varying float vTwinkle;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    float a = smoothstep(1.0, 0.0, d);
    gl_FragColor = vec4(uColor, a * a * uOpacity * vTwinkle);
    #include <colorspace_fragment>
  }
`;

/** Fine gold dust floating in depth behind the whole page. Drifts, twinkles, parallaxes with scroll and pointer. */
export function GoldDust({ reduced, dim }: { reduced: boolean; dim: number }) {
  const group = useRef<Group>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const { positions, sizes, phases } = useMemo(() => {
    // Deterministic pseudo-random so every visit looks the same.
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
    const positions = new Float32Array(COUNT * 3);
    const sizes = new Float32Array(COUNT);
    const phases = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) {
      positions[i * 3] = (rnd() - 0.5) * 16;
      positions[i * 3 + 1] = (rnd() - 0.5) * SPAN_Y;
      positions[i * 3 + 2] = -6 + rnd() * 8;
      sizes[i] = 0.4 + rnd() * rnd() * 2.2;
      phases[i] = rnd();
    }
    return { positions, sizes, phases };
  }, []);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        uniforms: {
          uTime: { value: 0 },
          uScroll: { value: 0 },
          uColor: { value: TOKENS.sun.clone() },
          uOpacity: { value: 0.55 },
        },
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
      }),
    [],
  );

  useEffect(() => {
    const on = (e: PointerEvent) => {
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("pointermove", on, { passive: true });
    return () => window.removeEventListener("pointermove", on);
  }, []);

  useFrame((_, dt) => {
    const u = material.uniforms;
    if (!reduced) u.uTime.value += Math.min(dt, 0.05);
    u.uScroll.value = window.scrollY / window.innerHeight;
    u.uOpacity.value += (0.55 * dim - u.uOpacity.value) * (reduced ? 1 : 0.05);
    if (group.current && !reduced) {
      group.current.position.x += (pointer.current.x * 0.25 - group.current.position.x) * 0.03;
      group.current.position.y += (pointer.current.y * 0.15 - group.current.position.y) * 0.03;
    }
  });

  return (
    <group ref={group}>
      <points material={material} frustumCulled={false} renderOrder={-5}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
          <bufferAttribute attach="attributes-aPhase" args={[phases, 1]} />
        </bufferGeometry>
      </points>
    </group>
  );
}
