import { Color } from "three";

export { CORE_STATES, STATE_LABEL, type CoreState } from "./labels";
import type { CoreState } from "./labels";

/** Colour tokens. Mirrors the @theme block in index.css: keep the two in sync. */
const T = {
  bg: new Color("#080706"),
  ink: new Color("#F7F1E6"),
  sun: new Color("#E8BE76"),
  alert: new Color("#E2553F"),
  earth: new Color("#A8CF78"),
  muted: new Color("#A69C8D"),
};
export const TOKENS = T;

/** Blend two token colours. Every colour in the core is a mix of the tokens. */
const mix = (a: Color, b: Color, t: number) => a.clone().lerp(b, t);

/** Smoked glass the sphere is made of: near-black with a warm cast. */
export const GLASS = mix(T.bg, T.sun, 0.07);

export interface Look {
  // colours
  core: Color; // bright heart of the light inside the glass
  swirl: Color; // darker, slower light that swirls around the heart
  rim: Color; // light caught at the edge of the glass
  halo: Color; // glow around the sphere
  // light
  haloI: number;
  rimI: number;
  glow: number; // how much the interior light fills the glass
  // motion
  breathAmp: number;
  breathPeriod: number;
  pulseAmp: number; // extra pulse for confirming / responding
  pulsePeriod: number;
  // the rings of light that revolve around the core
  waves: number; // opacity
  waveAmp: number; // how far the rings ripple
  waveSpeed: number;
  // overlays
  orbit: number; // thinking particles opacity
  arc: number; // executing arc opacity
  dot: number; // paused dot opacity
}

const base: Look = {
  core: T.sun,
  swirl: mix(T.sun, T.alert, 0.2),
  rim: T.sun,
  halo: T.sun,
  haloI: 0.6,
  rimI: 0.9,
  glow: 1.15,
  breathAmp: 0.03,
  breathPeriod: 4,
  pulseAmp: 0,
  pulsePeriod: 3,
  waves: 0.75,
  waveAmp: 0.07,
  waveSpeed: 0.35,
  orbit: 0,
  arc: 0,
  dot: 0,
};

const L = (o: Partial<Look>): Look => ({ ...base, ...o });

/** One look per state. Each must be recognisable without reading any text (spec §13). */
export const LOOKS: Record<CoreState, Look> = {
  // calm light, slow ripples
  standby: L({}),
  // brighter; the rings ripple with your voice
  listening: L({
    core: mix(T.sun, T.ink, 0.35),
    haloI: 1.1,
    rimI: 1.2,
    glow: 1.3,
    breathAmp: 0.012,
    waves: 1,
    waveAmp: 0.13,
    waveSpeed: 1.0,
  }),
  // light dims, particles orbit
  thinking: L({
    core: mix(T.sun, T.bg, 0.2),
    haloI: 0.3,
    rimI: 0.7,
    glow: 0.6,
    breathAmp: 0.012,
    breathPeriod: 2.4,
    waves: 0.4,
    waveSpeed: 0.7,
    orbit: 1,
  }),
  // green-gold, a steady arc tracks the work
  executing: L({
    core: mix(T.earth, T.sun, 0.4),
    swirl: mix(T.earth, T.bg, 0.3),
    rim: mix(T.earth, T.sun, 0.3),
    halo: mix(T.earth, T.sun, 0.45),
    haloI: 0.6,
    breathAmp: 0.01,
    waves: 0.5,
    waveSpeed: 0.9,
    arc: 1,
  }),
  // deeper amber, slow pulse
  confirming: L({
    core: mix(T.sun, T.alert, 0.25),
    swirl: mix(T.alert, T.bg, 0.2),
    rim: mix(T.sun, T.alert, 0.25),
    halo: mix(T.sun, T.alert, 0.2),
    haloI: 0.8,
    rimI: 1.1,
    glow: 1.05,
    breathAmp: 0,
    pulseAmp: 0.05,
    pulsePeriod: 2.8,
    waves: 0.7,
    waveAmp: 0.075,
    waveSpeed: 0.5,
  }),
  // light and rings pulse with its own voice
  responding: L({
    haloI: 0.75,
    glow: 1.1,
    breathAmp: 0.01,
    pulseAmp: 1,
    waves: 1,
    waveAmp: 0.11,
    waveSpeed: 0.9,
  }),
  // green-gold, one clean ring (JasCore returns to standby after 1.6 s)
  success: L({
    core: mix(T.sun, T.earth, 0.55),
    swirl: mix(T.earth, T.bg, 0.25),
    rim: T.earth,
    halo: mix(T.earth, T.sun, 0.4),
    haloI: 0.95,
    rimI: 1.2,
    glow: 1.15,
    breathAmp: 0.015,
    waves: 0.8,
  }),
  // ember red, rings ripple hard
  error: L({
    core: T.alert,
    swirl: mix(T.alert, T.bg, 0.45),
    rim: T.alert,
    halo: T.alert,
    haloI: 0.8,
    rimI: 1.2,
    glow: 1.0,
    breathAmp: 0.006,
    breathPeriod: 3,
    waves: 0.65,
    waveAmp: 0.1,
    waveSpeed: 1.5,
  }),
  // light almost out, rings still, one steady dot
  paused: L({
    core: T.muted,
    swirl: mix(T.muted, T.bg, 0.6),
    rim: T.muted,
    halo: T.muted,
    haloI: 0.12,
    rimI: 0.45,
    glow: 0.35,
    breathAmp: 0,
    waves: 0.15,
    waveAmp: 0,
    waveSpeed: 0,
    dot: 1,
  }),
};
