import { Color } from "three";

export { CORE_STATES, STATE_LABEL, type CoreState } from "./labels";
import type { CoreState } from "./labels";

/** Spec §4 tokens. Mirrors the @theme block in index.css: keep the two in sync. */
const T = {
  bg: new Color("#0B0E14"),
  ink: new Color("#FBFBF8"),
  sun: new Color("#FFC46B"),
  alert: new Color("#E85C54"),
  earth: new Color("#46C7B0"),
  muted: new Color("#8A94A8"),
};
export const TOKENS = T;

/** Blend two token colours. Every colour in the core is a mix of spec tokens. */
const mix = (a: Color, b: Color, t: number) => a.clone().lerp(b, t);

export interface Look {
  // colours
  body: Color; // lit centre of the sphere
  edge: Color; // sphere edge
  rim: Color; // fresnel glow
  halo: Color;
  // intensities
  haloI: number;
  rimI: number;
  // face
  open: number; // eye openness, 1 = fully open
  pupil: number; // pupil scale
  browLift: number;
  browTilt: number; // radians; > 0 knits (angry), < 0 raises the inner ends (concerned)
  lookX: number; // where the eyes look when not following the pointer, -1..1
  lookY: number;
  follow: number; // 0..1 how much the eyes follow the pointer
  // motion
  breathAmp: number;
  breathPeriod: number;
  pulseAmp: number; // extra pulse for confirming / responding
  pulsePeriod: number;
  // overlays
  ring: number; // listening ring opacity
  orbit: number; // thinking particles opacity
  arc: number; // executing arc opacity
  dot: number; // paused dot opacity
}

const creamHi = mix(T.ink, T.sun, 0.3);
const creamEdge = mix(T.ink, T.sun, 0.68);

const base: Look = {
  body: creamHi,
  edge: creamEdge,
  rim: T.sun,
  halo: T.sun,
  haloI: 0.55,
  rimI: 0.8,
  open: 0.55,
  pupil: 1,
  browLift: 0,
  browTilt: 0,
  lookX: 0,
  lookY: 0,
  follow: 1,
  breathAmp: 0.03,
  breathPeriod: 4,
  pulseAmp: 0,
  pulsePeriod: 3,
  ring: 0,
  orbit: 0,
  arc: 0,
  dot: 0,
};

const L = (o: Partial<Look>): Look => ({ ...base, ...o });

/** One look per state. Each must be recognisable without reading any text (spec §13). */
export const LOOKS: Record<CoreState, Look> = {
  // breathing, half-open eyes, blinking
  standby: L({}),
  // brighter, wide attentive eyes, audio-reactive ring
  listening: L({
    body: mix(T.ink, T.sun, 0.16),
    edge: mix(T.ink, T.sun, 0.5),
    haloI: 1.0,
    rimI: 1.2,
    open: 1.1,
    pupil: 1.3,
    browLift: 0.05,
    breathAmp: 0.012,
    ring: 1,
  }),
  // dimmer, eyes up and away, brows knit, particles orbit
  thinking: L({
    body: mix(creamHi, T.bg, 0.16),
    edge: mix(creamEdge, T.bg, 0.22),
    haloI: 0.32,
    rimI: 0.55,
    open: 0.8,
    pupil: 0.85,
    browTilt: 0.14,
    browLift: 0.02,
    lookX: 0.7,
    lookY: 0.75,
    follow: 0,
    breathAmp: 0.012,
    breathPeriod: 2.4,
    orbit: 1,
  }),
  // teal, eyes toward the checklist, steady scanning arc
  executing: L({
    body: mix(T.ink, T.earth, 0.28),
    edge: mix(T.sun, T.earth, 0.55),
    rim: T.earth,
    halo: mix(T.earth, T.sun, 0.22),
    haloI: 0.65,
    rimI: 1.0,
    open: 0.85,
    lookX: 0.65,
    lookY: -0.05,
    follow: 0.15,
    breathAmp: 0.01,
    arc: 1,
  }),
  // deeper amber, eyes on the question, slow pulse
  confirming: L({
    body: mix(T.sun, T.ink, 0.2),
    edge: mix(T.sun, T.alert, 0.32),
    rim: mix(T.sun, T.alert, 0.2),
    halo: mix(T.sun, T.alert, 0.2),
    haloI: 0.85,
    rimI: 1.0,
    open: 1.0,
    browTilt: -0.18,
    browLift: 0.04,
    lookX: 0.6,
    lookY: -0.45,
    follow: 0,
    breathAmp: 0,
    pulseAmp: 0.05,
    pulsePeriod: 2.8,
  }),
  // pulses with the voice output
  responding: L({
    haloI: 0.8,
    rimI: 1.0,
    open: 0.9,
    follow: 0.5,
    breathAmp: 0.01,
    pulseAmp: 1,
  }),
  // teal, eyes softly closed, one ring (see JasCore: returns to standby after 1.6 s)
  success: L({
    body: mix(T.ink, T.earth, 0.3),
    edge: T.earth,
    rim: T.earth,
    halo: T.earth,
    haloI: 0.95,
    rimI: 1.1,
    open: 0.1,
    follow: 0,
    breathAmp: 0.015,
  }),
  // red, brows knit and dropped
  error: L({
    body: mix(T.ink, T.alert, 0.36),
    edge: T.alert,
    rim: T.alert,
    halo: T.alert,
    haloI: 0.85,
    rimI: 1.1,
    open: 0.75,
    pupil: 0.8,
    browTilt: 0.42,
    browLift: -0.04,
    follow: 0.2,
    breathAmp: 0.006,
    breathPeriod: 3,
  }),
  // desaturated, motion stops, one steady dot
  paused: L({
    body: mix(T.muted, T.ink, 0.28),
    edge: T.muted,
    rim: T.muted,
    halo: T.muted,
    haloI: 0.14,
    rimI: 0.3,
    open: 0.06,
    follow: 0,
    breathAmp: 0,
    dot: 1,
  }),
};
