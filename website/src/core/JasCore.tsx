import { useEffect, useMemo, useRef, type RefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  AdditiveBlending,
  Color,
  DoubleSide,
  Euler,
  type Group,
  type Mesh,
  MathUtils,
  type MeshBasicMaterial,
  ShaderMaterial,
  type Points,
} from "three";
import { LOOKS, TOKENS, type CoreState, type Look } from "./states";

/* ---------------------------------------------------------------------------
 * The JAS core: a 3D sphere with a face (spec §5). Everything animates through
 * transform / opacity / uniforms: no layout, no per-frame allocation.
 * ------------------------------------------------------------------------- */

const NUM_KEYS = [
  "haloI", "rimI", "open", "pupil", "browLift", "browTilt", "lookX", "lookY", "follow",
  "breathAmp", "breathPeriod", "pulseAmp", "pulsePeriod", "ring", "orbit", "arc", "dot", "gyro",
] as const satisfies readonly (keyof Look)[];
const COLOR_KEYS = ["body", "edge", "rim", "halo"] as const satisfies readonly (keyof Look)[];

/** Cross-fade speed. 1 - exp(-lambda*dt) reaches ~98% in ~400 ms at lambda = 10 (spec §8). */
const FADE = 10;
const BLINK_MS = 0.18; // spec §8: 1.0 -> 0.06 -> 1.0 over 180 ms
const ORBIT_SECONDS = 1.2; // spec §6: particles orbit in a 1.2 s loop
const SUCCESS_RING_SECONDS = 0.6; // spec §6
const SUCCESS_HOLD_SECONDS = 1.6; // then back to standby

/** A believable stand-in for a voice level. The real site never touches the mic. */
function simulatedLevel(t: number): number {
  const syllable = Math.max(0, Math.sin(t * 6.2));
  const phrase = Math.max(0, Math.sin(t * 1.7 + 0.6));
  return Math.min(1, syllable * phrase * 1.1 + 0.1 + 0.05 * Math.sin(t * 23));
}

const BODY_VERT = /* glsl */ `
  varying vec3 vN;
  varying vec3 vV;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;
const BODY_FRAG = /* glsl */ `
  uniform vec3 uBody; uniform vec3 uEdge; uniform vec3 uRim;
  uniform float uRimI; uniform float uTime; uniform float uPulse;
  varying vec3 vN; varying vec3 vV;
  void main() {
    vec3 N = normalize(vN); vec3 V = normalize(vV);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    float f = pow(1.0 - ndv, 2.2);
    vec3 col = mix(uBody, uEdge, smoothstep(0.15, 1.0, 1.0 - ndv));
    float sw = 0.5 + 0.5 * sin(N.x * 3.0 + uTime * 0.4) * sin(N.y * 3.0 - uTime * 0.3);
    col *= 0.94 + 0.06 * sw;
    vec3 L = normalize(vec3(-0.5, 0.7, 0.6));
    float spec = pow(max(dot(reflect(-L, N), V), 0.0), 40.0) * 0.22;
    col += uRim * f * uRimI * 0.55 + vec3(spec);
    col *= 1.0 + uPulse;
    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
  }
`;
const HALO_VERT = /* glsl */ `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const HALO_FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uI;
  varying vec2 vUv;
  void main() {
    float r = length(vUv - 0.5) * 2.0;
    float a = smoothstep(1.0, 0.42, r);
    a = a * a * uI;
    gl_FragColor = vec4(uColor, a);
    #include <colorspace_fragment>
  }
`;
const ORBIT_VERT = /* glsl */ `
  attribute float aAngle; attribute float aRad; attribute float aJit; attribute float aSize;
  uniform float uTime;
  varying float vA;
  void main() {
    float a = aAngle + uTime * 6.28318530718 / ${ORBIT_SECONDS.toFixed(2)};
    vec3 p = vec3(cos(a) * aRad, aJit, sin(a) * aRad);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * 46.0 / -mv.z;
    vA = 0.55 + 0.45 * sin(a);
    gl_Position = projectionMatrix * mv;
  }
`;
const ORBIT_FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uOpacity;
  varying float vA;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    float a = smoothstep(1.0, 0.1, d) * uOpacity * vA;
    gl_FragColor = vec4(uColor, a);
    #include <colorspace_fragment>
  }
`;

const EYE_X = 0.33; // yaw of each eye around the sphere, radians
const EYE_RADIUS = 0.2;
const PUPIL_RADIUS = 0.1;
const GAZE_RANGE = 0.07;
const FACE_ORDER = (yaw: number, pitch: number) => new Euler(pitch, yaw, 0, "YXZ");

interface EyeRefs {
  eye: Group | null;
  pupil: Group | null;
  brow: Group | null;
}

interface JasCoreProps {
  state: CoreState;
  /** Optional live voice level 0..1. Falls back to a simulated level. */
  levelRef?: RefObject<number>;
  reduced?: boolean;
}

export function JasCore({ state, levelRef, reduced = false }: JasCoreProps) {
  const invalidate = useThree((s) => s.invalidate);

  // --- materials (created once, uniforms mutated per frame) ---
  const body = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: BODY_VERT,
        fragmentShader: BODY_FRAG,
        uniforms: {
          uBody: { value: new Color() }, uEdge: { value: new Color() }, uRim: { value: new Color() },
          uRimI: { value: 1 }, uTime: { value: 0 }, uPulse: { value: 0 },
        },
      }),
    [],
  );
  const halo = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: HALO_VERT,
        fragmentShader: HALO_FRAG,
        uniforms: { uColor: { value: new Color() }, uI: { value: 0.5 } },
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
      }),
    [],
  );
  const orbitGeo = useMemo(() => {
    const n = 140;
    const g = new Float32Array(n * 3);
    const angle = new Float32Array(n), rad = new Float32Array(n), jit = new Float32Array(n), size = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      angle[i] = (i / n) * Math.PI * 2 + (Math.sin(i * 12.9898) * 0.5);
      rad[i] = 1.42 + 0.05 * Math.sin(i * 78.233);
      jit[i] = 0.03 * Math.sin(i * 37.719);
      size[i] = 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(i * 4.1));
    }
    return { n, g, angle, rad, jit, size };
  }, []);
  const orbitMat = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: ORBIT_VERT,
        fragmentShader: ORBIT_FRAG,
        uniforms: { uTime: { value: 0 }, uColor: { value: new Color() }, uOpacity: { value: 0 } },
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
      }),
    [],
  );

  // --- scene refs ---
  const breath = useRef<Group>(null);
  const head = useRef<Group>(null);
  const eyes = useRef<EyeRefs[]>([
    { eye: null, pupil: null, brow: null },
    { eye: null, pupil: null, brow: null },
  ]);
  const ringGroup = useRef<Group>(null);
  const ripples = useRef<(Mesh | null)[]>([]);
  const baseRing = useRef<Mesh>(null);
  const successRing = useRef<Mesh>(null);
  const arc = useRef<Mesh>(null);
  const orbit = useRef<Points>(null);
  const dot = useRef<Mesh>(null);
  const gyroA = useRef<Mesh>(null);
  const gyroB = useRef<Mesh>(null);

  // --- animation state (mutated each frame, never causes a re-render) ---
  const cur = useRef<Look>(structuredCloneLook(LOOKS.standby));
  const anim = useRef({
    time: 0,
    level: 0,
    prevState: state,
    enteredAt: 0,
    nextBlink: 3.5,
    blinkStart: -10,
    px: 0,
    py: 0,
  });

  useEffect(() => {
    const on = (e: PointerEvent) => {
      anim.current.px = (e.clientX / window.innerWidth) * 2 - 1;
      anim.current.py = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("pointermove", on, { passive: true });
    return () => window.removeEventListener("pointermove", on);
  }, []);

  // In reduced-motion mode the canvas only renders on demand: render when the state changes.
  useEffect(() => {
    if (reduced) invalidate();
  }, [state, reduced, invalidate]);

  useFrame((frame, dtRaw) => {
    const a = anim.current;
    const dt = Math.min(dtRaw, 0.05);
    const now = frame.clock.elapsedTime;
    if (!reduced) a.time += dt;
    const t = a.time;

    if (a.prevState !== state) {
      a.prevState = state;
      a.enteredAt = now;
    }
    // Success is a moment, not a place: ring, then back to standby (spec §6).
    const sinceEnter = now - a.enteredAt;
    const eff: CoreState = state === "success" && sinceEnter > SUCCESS_HOLD_SECONDS ? "standby" : state;
    const target = LOOKS[eff];

    // --- cross-fade current look toward the target ---
    const k = reduced ? 1 : 1 - Math.exp(-FADE * dt);
    const c = cur.current;
    for (const key of NUM_KEYS) c[key] += (target[key] - c[key]) * k;
    for (const key of COLOR_KEYS) c[key].lerp(target[key], k);

    // --- voice level (simulated unless the caller supplies a live one) ---
    const rawLevel = levelRef?.current ?? simulatedLevel(now);
    a.level += (rawLevel - a.level) * (reduced ? 1 : 1 - Math.exp(-18 * dt));
    const level = reduced ? 0 : a.level;

    // --- breathing + pulses on the whole body ---
    const breathe = reduced ? 0 : 0.5 - 0.5 * Math.cos((t * Math.PI * 2) / Math.max(0.5, c.breathPeriod));
    const slowPulse = reduced ? 0 : 0.5 - 0.5 * Math.cos((t * Math.PI * 2) / Math.max(0.5, c.pulsePeriod));
    const voicePulse = eff === "responding" ? level : 0;
    const listenPulse = eff === "listening" ? level * 0.035 : 0;
    const scale =
      1 + c.breathAmp * breathe + (eff === "confirming" ? c.pulseAmp * slowPulse : 0) + voicePulse * 0.05 * c.pulseAmp + listenPulse;
    breath.current?.scale.setScalar(scale);

    body.uniforms.uBody.value.copy(c.body);
    body.uniforms.uEdge.value.copy(c.edge);
    body.uniforms.uRim.value.copy(c.rim);
    body.uniforms.uRimI.value = c.rimI;
    body.uniforms.uTime.value = t;
    body.uniforms.uPulse.value = eff === "responding" ? voicePulse * 0.12 * c.pulseAmp : eff === "confirming" ? slowPulse * 0.06 : 0;
    halo.uniforms.uColor.value.copy(c.halo);
    halo.uniforms.uI.value =
      c.haloI * (1 + (eff === "listening" ? level * 0.35 : 0) + (eff === "responding" ? voicePulse * 0.4 : 0) + (eff === "confirming" ? slowPulse * 0.25 : 0));

    // --- gaze: pointer follows blend with the state's own look direction ---
    const follow = reduced ? 0 : c.follow;
    const lx = MathUtils.lerp(c.lookX, a.px, follow);
    const ly = MathUtils.lerp(c.lookY, a.py, follow);
    if (head.current) {
      head.current.rotation.y = lx * 0.16;
      head.current.rotation.x = -ly * 0.1;
    }

    // --- blink: 1 -> 0.06 -> 1 over 180 ms, every 3-7 s (spec §8) ---
    if (!reduced && now > a.nextBlink && c.open > 0.3) {
      a.blinkStart = now;
      a.nextBlink = now + 3 + Math.random() * 4;
    }
    const bp = (now - a.blinkStart) / BLINK_MS;
    const blink = bp >= 0 && bp <= 1 ? 1 - 0.94 * Math.sin(Math.PI * bp) : 1;
    const openness = Math.max(0.06, c.open * blink);

    for (let i = 0; i < 2; i++) {
      const e = eyes.current[i];
      const side = i === 0 ? -1 : 1;
      if (e.eye) e.eye.scale.y = openness;
      if (e.pupil) {
        e.pupil.position.set(lx * GAZE_RANGE, ly * GAZE_RANGE, 0.002);
        e.pupil.scale.setScalar(c.pupil);
      }
      if (e.brow) {
        e.brow.position.y = 0.33 + c.browLift;
        e.brow.rotation.z = side * c.browTilt;
      }
    }

    // --- listening ring: base ring follows the voice, three ripples travel outward ---
    const ringOn = c.ring;
    if (baseRing.current) {
      const s = 1.24 + level * 0.07 * ringOn;
      baseRing.current.scale.setScalar(s);
      (baseRing.current.material as MeshBasicMaterial).opacity = ringOn * (0.35 + level * 0.5);
    }
    for (let i = 0; i < 3; i++) {
      const m = ripples.current[i];
      if (!m) continue;
      const phase = reduced ? 0.35 + i * 0.25 : (t * 0.8 + i / 3) % 1;
      const reach = 0.45 + level * 0.5;
      m.scale.setScalar(1.24 + phase * reach);
      (m.material as MeshBasicMaterial).opacity = ringOn * (1 - phase) * (0.2 + level * 0.5);
    }
    (baseRing.current?.material as MeshBasicMaterial | undefined)?.color.copy(c.rim);

    // --- success ring: one clean ring, 600 ms, camera-facing ---
    if (successRing.current) {
      const p = state === "success" ? MathUtils.clamp(sinceEnter / SUCCESS_RING_SECONDS, 0, 1) : 1;
      const ease = 1 - Math.pow(1 - p, 3);
      const visible = state === "success" && p < 1;
      successRing.current.visible = visible || (reduced && state === "success");
      successRing.current.scale.setScalar(reduced ? 1.5 : 1.05 + ease * 0.75);
      (successRing.current.material as MeshBasicMaterial).opacity = reduced ? 0.7 : (1 - p) * 0.9;
    }

    // --- executing arc: steady scanning ring in the camera plane ---
    if (arc.current) {
      arc.current.rotation.z = reduced ? 0 : -t * 1.1;
      (arc.current.material as MeshBasicMaterial).opacity = c.arc * 0.85;
      arc.current.visible = c.arc > 0.01;
    }

    // --- thinking particles ---
    orbitMat.uniforms.uTime.value = reduced ? 0 : t;
    orbitMat.uniforms.uOpacity.value = c.orbit;
    orbitMat.uniforms.uColor.value.copy(TOKENS.sun);
    if (orbit.current) orbit.current.visible = c.orbit > 0.01;

    // --- gyroscope rings: two thin gold hoops turning slowly on different axes ---
    const g = c.gyro;
    for (const [m, sx, sy, base] of [
      [gyroA.current, 0.21, 0.33, 0.5],
      [gyroB.current, -0.17, 0.26, 0.38],
    ] as const) {
      if (!m) continue;
      m.visible = g > 0.01;
      m.rotation.x = 1.1 + t * sx;
      m.rotation.y = t * sy;
      (m.material as MeshBasicMaterial).opacity = g * base;
    }

    // --- paused dot ---
    if (dot.current) {
      (dot.current.material as MeshBasicMaterial).opacity = c.dot;
      dot.current.visible = c.dot > 0.01;
    }
  });

  return (
    <group>
      <mesh position={[0, 0, -0.8]} renderOrder={-2} material={halo}>
        <planeGeometry args={[4, 4]} />
      </mesh>

      {/* thinking: particles orbit in the XZ plane, tilted toward the camera; the far side hides behind the body */}
      <group rotation={[0.38, 0, 0.3]}>
        <points ref={orbit} material={orbitMat} renderOrder={20} frustumCulled={false}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[orbitGeo.g, 3]} />
            <bufferAttribute attach="attributes-aAngle" args={[orbitGeo.angle, 1]} />
            <bufferAttribute attach="attributes-aRad" args={[orbitGeo.rad, 1]} />
            <bufferAttribute attach="attributes-aJit" args={[orbitGeo.jit, 1]} />
            <bufferAttribute attach="attributes-aSize" args={[orbitGeo.size, 1]} />
          </bufferGeometry>
        </points>
      </group>

      {/* listening: equator ring + ripples */}
      <group ref={ringGroup} rotation={[-1.2, 0, 0]}>
        <mesh ref={baseRing}>
          <torusGeometry args={[1, 0.012, 8, 160]} />
          <meshBasicMaterial color={TOKENS.sun} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        {[0, 1, 2].map((i) => (
          <mesh key={i} ref={(m) => { ripples.current[i] = m; }}>
            <torusGeometry args={[1, 0.007, 8, 160]} />
            <meshBasicMaterial color={TOKENS.sun} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* success: single expanding ring, facing the camera */}
      <mesh ref={successRing} visible={false}>
        <torusGeometry args={[1, 0.016, 8, 160]} />
        <meshBasicMaterial color={TOKENS.earth} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      {/* executing: open arc that scans steadily */}
      <mesh ref={arc} scale={1.34} visible={false}>
        <torusGeometry args={[1, 0.012, 8, 160, Math.PI * 1.35]} />
        <meshBasicMaterial color={TOKENS.earth} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      <group ref={breath}>
        <mesh material={body}>
          <sphereGeometry args={[1, 64, 48]} />
        </mesh>

        {/* face: glued to the sphere, tilts toward where it is looking */}
        <group ref={head}>
          {[0, 1].map((i) => {
            const side = i === 0 ? -1 : 1;
            return (
              <group key={i} rotation={FACE_ORDER(side * EYE_X, -0.02)}>
                <group position={[0, 0, 1.0]}>
                  <group ref={(g) => { eyes.current[i].eye = g; }}>
                    <mesh renderOrder={10}>
                      <circleGeometry args={[EYE_RADIUS, 40]} />
                      <meshBasicMaterial color={TOKENS.ink} depthTest={false} toneMapped={false} />
                    </mesh>
                    <group ref={(g) => { eyes.current[i].pupil = g; }}>
                      <mesh renderOrder={11}>
                        <circleGeometry args={[PUPIL_RADIUS, 32]} />
                        <meshBasicMaterial color={TOKENS.bg} depthTest={false} toneMapped={false} />
                      </mesh>
                      <mesh position={[0.036, 0.036, 0.001]} renderOrder={12}>
                        <circleGeometry args={[0.028, 16]} />
                        <meshBasicMaterial color={TOKENS.ink} depthTest={false} toneMapped={false} />
                      </mesh>
                    </group>
                  </group>
                  <group ref={(g) => { eyes.current[i].brow = g; }}>
                    <mesh rotation={[0, 0, Math.PI / 2]} renderOrder={10}>
                      <capsuleGeometry args={[0.018, 0.34, 4, 12]} />
                      <meshBasicMaterial color={TOKENS.bg} depthTest={false} toneMapped={false} side={DoubleSide} />
                    </mesh>
                  </group>
                </group>
              </group>
            );
          })}
        </group>
      </group>

      {/* standby: gyroscope rings */}
      <mesh ref={gyroA} scale={1.55} visible={false}>
        <torusGeometry args={[1, 0.0045, 6, 200]} />
        <meshBasicMaterial color={TOKENS.sun} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh ref={gyroB} scale={1.78} visible={false}>
        <torusGeometry args={[1, 0.0035, 6, 200]} />
        <meshBasicMaterial color={TOKENS.sun} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      {/* paused: one steady dot */}
      <mesh ref={dot} position={[0, -1.5, 0]} visible={false}>
        <circleGeometry args={[0.04, 24]} />
        <meshBasicMaterial color={TOKENS.muted} transparent opacity={0} toneMapped={false} />
      </mesh>
    </group>
  );
}

function structuredCloneLook(l: Look): Look {
  return {
    ...l,
    body: l.body.clone(), edge: l.edge.clone(), rim: l.rim.clone(), halo: l.halo.clone(),
  };
}
