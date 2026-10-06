import { useEffect, useMemo, useRef, type RefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  AdditiveBlending,
  Color,
  type Group,
  type Mesh,
  MathUtils,
  type MeshBasicMaterial,
  ShaderMaterial,
  type Points,
  Vector2,
} from "three";
import { GLASS, LOOKS, TOKENS, type CoreState, type Look } from "./states";

/* ---------------------------------------------------------------------------
 * The VEM: a smoked-glass sphere with light moving inside it that drifts
 * toward the pointer, and rings of light that ripple as they revolve around it.
 * Everything animates through transforms and uniforms: no layout, no per-frame
 * allocation.
 * ------------------------------------------------------------------------- */

const NUM_KEYS = [
  "haloI", "rimI", "glow",
  "breathAmp", "breathPeriod", "pulseAmp", "pulsePeriod", "waves", "waveAmp", "waveSpeed", "orbit", "arc", "dot",
] as const satisfies readonly (keyof Look)[];
const COLOR_KEYS = ["core", "swirl", "rim", "halo"] as const satisfies readonly (keyof Look)[];

/** Cross-fade speed. 1 - exp(-lambda*dt) reaches ~98% in ~400 ms at lambda = 10 (spec §8). */
const FADE = 10;
const ORBIT_SECONDS = 1.2; // spec §6: particles orbit in a 1.2 s loop
const SUCCESS_RING_SECONDS = 0.6; // spec §6
const SUCCESS_HOLD_SECONDS = 1.6; // then back to standby

/** A believable stand-in for a voice level. The site never touches the mic. */
function simulatedLevel(t: number): number {
  const syllable = Math.max(0, Math.sin(t * 6.2));
  const phrase = Math.max(0, Math.sin(t * 1.7 + 0.6));
  return Math.min(1, syllable * phrase * 1.1 + 0.1 + 0.05 * Math.sin(t * 23));
}

/* 3D simplex noise (Ashima Arts / Stefan Gustavson, MIT). Drives the light inside the glass. */
const NOISE = /* glsl */ `
  vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
  vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
  vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
  vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
  float snoise(vec3 v){
    const vec2 C=vec2(1./6.,1./3.); const vec4 D=vec4(0.,.5,1.,2.);
    vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
    vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
    vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
    i=mod289(i);
    vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
    float n_=.142857142857; vec3 ns=n_*D.wyz-D.xzx;
    vec4 j=p-49.*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.*x_);
    vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.-abs(x)-abs(y);
    vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.+1.; vec4 s1=floor(b1)*2.+1.; vec4 sh=-step(h,vec4(0.));
    vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
    p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
    vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.); m=m*m;
    return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
  }
`;

const BODY_VERT = /* glsl */ `
  varying vec3 vN; varying vec3 vV; varying vec3 vObj;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    vObj = position;
    gl_Position = projectionMatrix * mv;
  }
`;
/* Smoked glass: dark at the edge, light glowing from inside, studio reflections on the surface. */
const BODY_FRAG = /* glsl */ `
  uniform vec3 uCore; uniform vec3 uSwirl; uniform vec3 uRim; uniform vec3 uGlass;
  uniform float uRimI; uniform float uGlow; uniform float uTime; uniform float uPulse; uniform vec2 uLook;
  varying vec3 vN; varying vec3 vV; varying vec3 vObj;
  ${NOISE}
  void main() {
    vec3 N = normalize(vN); vec3 V = normalize(vV);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    float fres = pow(1.0 - ndv, 3.0);

    // Light inside the glass: strongest at the heart, slowly swirling.
    float n1 = snoise(vObj * 1.5 + vec3(0.0, uTime * 0.13, uTime * 0.07));
    float n2 = snoise(vObj * 3.2 - vec3(uTime * 0.09, 0.0, uTime * 0.05));
    // The heart of the light sits where the orb is "looking".
    float aim = clamp(dot(N, normalize(vec3(uLook, 1.0))), 0.0, 1.0);
    float depth = pow(mix(ndv, aim, 0.55), 1.35);
    float plasma = clamp(depth * (0.86 + 0.16 * n1 + 0.06 * n2), 0.0, 1.2);
    vec3 inner = mix(uSwirl, uCore, smoothstep(0.12, 0.7, plasma));
    float fill = clamp(plasma * uGlow * (1.0 + uPulse), 0.0, 1.35);
    vec3 col = mix(uGlass, inner, smoothstep(0.0, 1.0, fill));
    col += uCore * pow(depth, 4.0) * 0.5 * uGlow;             // hot centre

    // Glass surface: a sky/floor reflection, a soft key highlight and a small kicker.
    vec3 R = reflect(-V, N);
    float sky = smoothstep(-0.15, 0.9, R.y);
    col += vec3(1.0, 0.95, 0.86) * sky * fres * 0.32;
    vec3 L1 = normalize(vec3(-0.55, 0.78, 0.58));
    float k = max(dot(R, L1), 0.0);
    col += vec3(1.0, 0.97, 0.9) * (pow(k, 120.0) * 1.1 + pow(k, 14.0) * 0.1);
    vec3 L2 = normalize(vec3(0.75, -0.4, 0.5));
    col += uRim * pow(max(dot(R, L2), 0.0), 36.0) * 0.35;
    col += uRim * fres * uRimI * 1.1;                         // light caught at the edge

    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
  }
`;

/* Soft radial glow. Used for the halo and the pool of light beneath the core. */
const GLOW_VERT = /* glsl */ `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const GLOW_FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uI; uniform float uInner;
  varying vec2 vUv;
  void main() {
    float r = length(vUv - 0.5) * 2.0;
    float a = smoothstep(1.0, uInner, r);
    gl_FragColor = vec4(uColor, a * a * uI);
    #include <colorspace_fragment>
  }
`;

/* A ring of light that ripples like a sound wave and revolves: the bright head leads a fading tail. */
const WAVE_VERT = /* glsl */ `
  uniform float uTime; uniform float uAmp; uniform float uFreq; uniform float uPhase; uniform float uSpeed;
  varying float vA; varying float vFacing;
  void main() {
    vec3 p = position;
    float a = atan(p.y, p.x);
    float w = sin(a * uFreq + uPhase + uTime * uSpeed * 3.0) * 0.65
            + sin(a * (uFreq * 0.5 + 1.0) - uTime * uSpeed * 2.1 + uPhase) * 0.35;
    p.xy *= 1.0 + uAmp * w;
    p.z += uAmp * 0.7 * cos(a * (uFreq * 0.5) + uTime * uSpeed * 2.0 + uPhase);
    vA = a;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vFacing = abs(dot(normalize(normalMatrix * normal), normalize(-mv.xyz)));
    gl_Position = projectionMatrix * mv;
  }
`;
const WAVE_FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uOpacity; uniform float uTime; uniform float uRot; uniform float uPhase;
  uniform float uSoft; // 0 = crisp line, higher = softer glow that fades toward the tube's edges
  varying float vA; varying float vFacing;
  void main() {
    float u = fract(vA / 6.2831853 + 0.5 - uTime * uRot + uPhase * 0.1);
    float head = pow(u, 2.6);
    float head2 = pow(fract(u + 0.5), 2.6) * 0.55;
    float a = (0.12 + 0.88 * max(head, head2)) * uOpacity * pow(vFacing, uSoft);
    gl_FragColor = vec4(uColor * (0.8 + 0.6 * head), a);
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

/** Three revolving wave rings: [radius, tilt, frequency, phase, revolutions per second].
 *  Frequencies must be even so every harmonic in WAVE_VERT is a whole number: an odd or fractional
 *  one breaks the ring where the angle wraps from +pi to -pi. */
const WAVES: [number, [number, number, number], number, number, number][] = [
  [1.36, [1.2, 0.0, 0.35], 6, 0.0, 0.11],
  [1.62, [0.95, 0.65, -0.5], 8, 2.1, -0.08],
  [1.9, [1.45, -0.55, 0.9], 4, 4.2, 0.06],
];

interface JasCoreProps {
  state: CoreState;
  /** Optional live voice level 0..1. Falls back to a simulated level. */
  levelRef?: RefObject<number>;
  reduced?: boolean;
  /** Optional fixed clock in seconds. When set, time comes from here (not the wall clock), so frames
   *  can be rendered deterministically for exported stills and loops (see studio/). */
  clockRef?: RefObject<number>;
}

export function JasCore({ state, levelRef, reduced = false, clockRef }: JasCoreProps) {
  const invalidate = useThree((s) => s.invalidate);

  // --- materials (created once, uniforms mutated per frame) ---
  const body = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: BODY_VERT,
        fragmentShader: BODY_FRAG,
        uniforms: {
          uCore: { value: new Color() }, uSwirl: { value: new Color() }, uRim: { value: new Color() },
          uGlass: { value: GLASS.clone() }, uLook: { value: new Vector2() }, uRimI: { value: 1 }, uGlow: { value: 1 }, uTime: { value: 0 }, uPulse: { value: 0 },
        },
      }),
    [],
  );
  const makeGlow = (inner: number) =>
    new ShaderMaterial({
      vertexShader: GLOW_VERT,
      fragmentShader: GLOW_FRAG,
      uniforms: { uColor: { value: new Color() }, uI: { value: 0.5 }, uInner: { value: inner } },
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
  const halo = useMemo(() => makeGlow(0.25), []);
  const pool = useMemo(() => makeGlow(0.0), []);
  // Each ring is drawn twice: a crisp line, and a wide soft tube around it that reads as glow.
  const makeWaveMats = (soft: number) =>
      WAVES.map(
        ([, , freq, phase, rot]) =>
          new ShaderMaterial({
            vertexShader: WAVE_VERT,
            fragmentShader: WAVE_FRAG,
            uniforms: {
              uTime: { value: 0 }, uAmp: { value: 0 }, uFreq: { value: freq }, uPhase: { value: phase },
              uSpeed: { value: 0 }, uColor: { value: new Color() }, uOpacity: { value: 0 }, uRot: { value: rot },
              uSoft: { value: soft },
            },
            transparent: true,
            depthWrite: false,
            blending: AdditiveBlending,
          }),
      );
  const waveMats = useMemo(() => makeWaveMats(0.3), []);
  const bloomMats = useMemo(() => makeWaveMats(2.2), []);
  const orbitGeo = useMemo(() => {
    const n = 140;
    const g = new Float32Array(n * 3);
    const angle = new Float32Array(n), rad = new Float32Array(n), jit = new Float32Array(n), size = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      angle[i] = (i / n) * Math.PI * 2 + Math.sin(i * 12.9898) * 0.5;
      rad[i] = 1.42 + 0.05 * Math.sin(i * 78.233);
      jit[i] = 0.03 * Math.sin(i * 37.719);
      size[i] = 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(i * 4.1));
    }
    return { g, angle, rad, jit, size };
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
  const waveGroup = useRef<Group>(null);
  const successRing = useRef<Mesh>(null);
  const arc = useRef<Mesh>(null);
  const orbit = useRef<Points>(null);
  const dot = useRef<Mesh>(null);

  // --- animation state (mutated each frame, never causes a re-render) ---
  const cur = useRef<Look>(cloneLook(LOOKS.standby));
  const anim = useRef({ time: 0, level: 0, prevState: state, enteredAt: 0, px: 0, py: 0 });

  useEffect(() => {
    const on = (e: PointerEvent) => {
      anim.current.px = (e.clientX / window.innerWidth) * 2 - 1;
      anim.current.py = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("pointermove", on, { passive: true });
    return () => window.removeEventListener("pointermove", on);
  }, []);

  // Overlays (thinking particles, executing arc, paused dot) are always drawn, transparent until
  // needed, so their shaders are compiled and linked during the first frames of page load. Hiding
  // them made the browser compile on first use instead, which stalled the page the first time VEM
  // started thinking (seconds on a software GPU, a visible hitch on a real one).

  // In reduced-motion mode the canvas only renders on demand: render when the state changes.
  useEffect(() => {
    if (reduced) invalidate();
  }, [state, reduced, invalidate]);

  useFrame((frame, dtRaw) => {
    const a = anim.current;
    const fixed = clockRef?.current;
    const dt = fixed !== undefined ? 1 / 30 : Math.min(dtRaw, 0.05);
    const now = fixed ?? frame.clock.elapsedTime;
    if (fixed !== undefined) a.time = fixed;
    else if (!reduced) a.time += dt;
    const t = a.time;

    if (a.prevState !== state) {
      a.prevState = state;
      a.enteredAt = now;
    }
    // Success is a moment, not a place: ring, then back to standby (spec §6).
    const sinceEnter = now - a.enteredAt;
    const eff: CoreState = state === "success" && sinceEnter > SUCCESS_HOLD_SECONDS ? "standby" : state;
    const target = LOOKS[eff];

    // --- cross-fade the current look toward the target ---
    const k = reduced ? 1 : 1 - Math.exp(-FADE * dt);
    const c = cur.current;
    for (const key of NUM_KEYS) c[key] += (target[key] - c[key]) * k;
    for (const key of COLOR_KEYS) c[key].lerp(target[key], k);

    // --- voice level (simulated unless the caller supplies a live one) ---
    const rawLevel = levelRef?.current ?? simulatedLevel(now);
    a.level += (rawLevel - a.level) * (reduced ? 1 : 1 - Math.exp(-18 * dt));
    const level = reduced ? 0 : a.level;
    const voice = eff === "listening" || eff === "responding" ? level : 0;

    // --- breathing and pulses ---
    const breathe = reduced ? 0 : 0.5 - 0.5 * Math.cos((t * Math.PI * 2) / Math.max(0.5, c.breathPeriod));
    const slowPulse = reduced ? 0 : 0.5 - 0.5 * Math.cos((t * Math.PI * 2) / Math.max(0.5, c.pulsePeriod));
    const confirmPulse = eff === "confirming" ? slowPulse : 0;
    breath.current?.scale.setScalar(1 + c.breathAmp * breathe + c.pulseAmp * confirmPulse + voice * 0.03);

    const bu = body.uniforms;
    bu.uCore.value.copy(c.core);
    bu.uSwirl.value.copy(c.swirl);
    bu.uRim.value.copy(c.rim);
    bu.uRimI.value = c.rimI;
    bu.uGlow.value = c.glow;
    bu.uTime.value = t;
    bu.uPulse.value = voice * 0.35 + confirmPulse * 0.12;
    halo.uniforms.uColor.value.copy(c.halo);
    halo.uniforms.uI.value = c.haloI * (1.25 + voice * 0.55 + confirmPulse * 0.3);
    pool.uniforms.uColor.value.copy(c.halo);
    pool.uniforms.uI.value = c.haloI * 0.5;

    // --- the light inside drifts toward the pointer, so the orb feels aware without a face ---
    const follow = reduced ? 0 : 1;
    bu.uLook.value.set(
      bu.uLook.value.x + (a.px * 0.35 * follow - bu.uLook.value.x) * 0.06,
      bu.uLook.value.y + (a.py * 0.3 * follow - bu.uLook.value.y) * 0.06,
    );

    // --- revolving wave rings ---
    const amp = c.waveAmp * (1 + voice * 2.4);
    for (let i = 0; i < waveMats.length; i++) {
      const opacity = c.waves * (0.8 + voice * 0.4) * (i === 0 ? 1 : 0.85);
      for (const [mats, mul] of [[waveMats, 1], [bloomMats, 0.32]] as const) {
        const u = mats[i].uniforms;
        u.uTime.value = t;
        u.uAmp.value = amp;
        u.uSpeed.value = c.waveSpeed;
        u.uOpacity.value = opacity * mul;
        u.uColor.value.copy(c.rim);
      }
    }
    if (waveGroup.current) waveGroup.current.rotation.y = reduced ? 0 : t * 0.05;

    // --- success ring: one clean ring, 600 ms, facing the camera ---
    if (successRing.current) {
      const p = state === "success" ? MathUtils.clamp(sinceEnter / SUCCESS_RING_SECONDS, 0, 1) : 1;
      const ease = 1 - Math.pow(1 - p, 3);
      successRing.current.visible = (state === "success" && p < 1) || (reduced && state === "success");
      successRing.current.scale.setScalar(reduced ? 1.5 : 1.05 + ease * 0.75);
      (successRing.current.material as MeshBasicMaterial).opacity = reduced ? 0.7 : (1 - p) * 0.9;
    }

    // --- executing arc: steady scanning ring in the camera plane ---
    if (arc.current) {
      arc.current.rotation.z = reduced ? 0 : -t * 1.1;
      (arc.current.material as MeshBasicMaterial).opacity = c.arc * 0.85;
    }

    // --- thinking particles ---
    orbitMat.uniforms.uTime.value = reduced ? 0 : t;
    orbitMat.uniforms.uOpacity.value = c.orbit;
    orbitMat.uniforms.uColor.value.copy(TOKENS.sun);

    // --- paused dot ---
    if (dot.current) {
      (dot.current.material as MeshBasicMaterial).opacity = c.dot;
    }
  });

  return (
    <group>
      <mesh position={[0, 0, -0.8]} renderOrder={-2} material={halo}>
        <planeGeometry args={[5.4, 5.4]} />
      </mesh>
      {/* a pool of light beneath the core grounds it in space */}
      <mesh position={[0, -1.42, -0.4]} scale={[2.8, 0.42, 1]} renderOrder={-1} material={pool}>
        <planeGeometry args={[1, 1]} />
      </mesh>

      {/* revolving wave rings; depth-tested so the far side passes behind the glass */}
      <group ref={waveGroup}>
        {WAVES.map(([radius, tilt], i) => (
          <group key={i} scale={radius} rotation={tilt}>
            <mesh material={waveMats[i]} renderOrder={5}>
              <torusGeometry args={[1, 0.009, 6, 320]} />
            </mesh>
            <mesh material={bloomMats[i]} renderOrder={4}>
              <torusGeometry args={[1, 0.06, 10, 320]} />
            </mesh>
          </group>
        ))}
      </group>

      {/* thinking: particles orbit in the XZ plane, tilted toward the camera */}
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

      {/* success: single expanding ring, facing the camera */}
      <mesh ref={successRing} visible={false}>
        <torusGeometry args={[1, 0.016, 8, 160]} />
        <meshBasicMaterial color={TOKENS.earth} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      {/* executing: open arc that scans steadily */}
      <mesh ref={arc} scale={1.34}>
        <torusGeometry args={[1, 0.012, 8, 160, Math.PI * 1.35]} />
        <meshBasicMaterial color={TOKENS.earth} transparent opacity={0} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      <group ref={breath}>
        <mesh material={body}>
          <sphereGeometry args={[1, 96, 64]} />
        </mesh>
      </group>

      {/* paused: one steady dot */}
      <mesh ref={dot} position={[0, -1.5, 0]}>
        <circleGeometry args={[0.04, 24]} />
        <meshBasicMaterial color={TOKENS.muted} transparent opacity={0} toneMapped={false} />
      </mesh>
    </group>
  );
}

function cloneLook(l: Look): Look {
  return { ...l, core: l.core.clone(), swirl: l.swirl.clone(), rim: l.rim.clone(), halo: l.halo.clone() };
}
