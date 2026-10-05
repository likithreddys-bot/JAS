/* The Luffy film: 20 seconds, 1920x1080. Every frame is a pure function of time t, so it can be
 * rendered frame by frame into a perfectly smooth video, and also played live.
 * Story (dramatised): Meera in HR must send an urgent report to her manager; her laptop is 40 km
 * away; she asks Luffy on her phone; Luffy confirms and sends it in seconds.
 * Style: washi paper and sumi ink outside the phone; the phone is black lacquer. */
import "@fontsource/shippori-mincho-b1/latin-700.css";
import "@fontsource/shippori-mincho-b1/latin-800.css";
import "@fontsource/zen-kaku-gothic-new/latin-400.css";
import "@fontsource/zen-kaku-gothic-new/latin-500.css";
import "../src/fonts/jp.css";
import { paintEnso } from "../src/core/enso";

const W = 1920;
const H = 1080;
export const DURATION = 20;

const C = {
  // the paper
  bg: "#F3ECDF",
  sumi: "#1C1915",
  kin: "#8E6A2C",
  shu: "#C4432B",
  muted: "#5F574D",
  // the phone (black lacquer)
  ink: "#EFE7D8",
  gold: "#D2A75A",
  leaf: "#93AE5A",
  dim: "#A99F90",
};

// ---------- easing and timing helpers ----------
const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x: number) => 1 - Math.pow(1 - clamp(x), 3); // ease-out cubic
const inOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
/** 0 before `a`, eases to 1 over `d` seconds. */
const enter = (t: number, a: number, d = 0.6) => ease((t - a) / d);
/** 1 while inside [a, b], fading in and out over `f` seconds. */
const window_ = (t: number, a: number, b: number, f = 0.5) => Math.min(enter(t, a, f), 1 - enter(t, b - f, f));

// Canvas text needs its font loaded first: the 済 seal (document.fonts.ready then covers it).
void document.fonts.load('800 40px "Luffy JP Display"', "済ルフィ");

// ---------- stage ----------
const stage = document.getElementById("stage")!;
document.documentElement.style.background = C.bg;
Object.assign(document.body.style, { margin: "0", background: C.bg, overflow: "hidden" });
Object.assign(stage.style, {
  position: "relative",
  width: `${W}px`,
  height: `${H}px`,
  backgroundColor: C.bg,
  backgroundImage: "radial-gradient(rgba(28,25,21,0.07) 1px, transparent 1.3px)",
  backgroundSize: "7px 9px",
  overflow: "hidden",
  fontFamily: '"Zen Kaku Gothic New", "Luffy JP Body", system-ui, sans-serif',
  color: C.sumi,
  transformOrigin: "0 0",
});

function el<K extends keyof HTMLElementTagNameMap>(tag: K, css: Partial<CSSStyleDeclaration>, parent: HTMLElement = stage, text = "") {
  const e = document.createElement(tag);
  Object.assign(e.style, { position: "absolute", ...css });
  if (text) e.textContent = text;
  parent.appendChild(e);
  return e;
}
const display = '"Shippori Mincho B1", "Luffy JP Display", Georgia, serif';

// Captions (top-left, film-title style)
const capSmall = el("div", { left: "160px", top: "150px", fontSize: "30px", color: C.muted, fontFamily: display, letterSpacing: "0.02em" });
const capBig = el("div", { left: "160px", top: "200px", fontSize: "84px", fontWeight: "800", fontFamily: display, letterSpacing: "-0.01em", lineHeight: "1.02", width: "820px" });

// The phone
const phone = el("div", {
  left: "1150px", top: "110px", width: "430px", height: "880px", borderRadius: "64px",
  background: "#0f0d0b", border: "2px solid #3a3128", color: C.ink,
  boxShadow: "0 0 0 10px #1c1915, 0 80px 140px -50px rgba(28,25,21,0.6)", overflow: "hidden",
});
el("div", { left: "155px", top: "18px", width: "120px", height: "34px", borderRadius: "20px", background: "#000" }, phone);
const clock = el("div", { left: "40px", top: "22px", fontSize: "20px", fontWeight: "600" }, phone, "6:40");
// notification
const notif = el("div", { left: "18px", top: "84px", width: "394px", padding: "20px 22px", borderRadius: "28px", background: "rgba(40,34,27,0.92)", boxSizing: "border-box" }, phone);
el("div", { position: "relative", fontSize: "17px", color: C.dim } as Partial<CSSStyleDeclaration>, notif, "Arjun Rao · Manager · now");
el("div", { position: "relative", marginTop: "6px", fontSize: "22px", lineHeight: "1.35" } as Partial<CSSStyleDeclaration>, notif, "Need the Q3 attrition report before the board call. 10 minutes?");
// Luffy inside the phone
const orbCanvas = el("canvas", { left: "15px", top: "120px", width: "400px", height: "400px" }, phone) as HTMLCanvasElement;
orbCanvas.width = 800;
orbCanvas.height = 800;
const said = el("div", { left: "36px", top: "520px", width: "358px", fontSize: "27px", lineHeight: "1.3", fontFamily: display, textAlign: "center" }, phone);
const steps = el("div", { left: "34px", top: "600px", width: "362px" }, phone);
const stepRows = ["Found Q3_Attrition_Report.xlsx", "Arjun Rao · arjun@company.com"].map((label) => {
  const row = el("div", { position: "relative", display: "flex", alignItems: "center", gap: "14px", fontSize: "20px", marginBottom: "14px" } as Partial<CSSStyleDeclaration>, steps);
  const tick = el("span", { position: "relative", width: "28px", height: "28px", borderRadius: "50%", background: "rgba(168,207,120,0.18)", color: C.leaf, display: "grid", placeItems: "center", fontSize: "17px", flex: "none" } as Partial<CSSStyleDeclaration>, row, "✓");
  el("span", { position: "relative" } as Partial<CSSStyleDeclaration>, row, label);
  return { row, tick };
});
const confirm = el("div", { left: "18px", top: "690px", width: "394px", padding: "22px", borderRadius: "28px", background: "rgba(40,34,27,0.96)", border: `1px solid rgba(232,190,118,0.35)`, boxSizing: "border-box" }, phone);
el("div", { position: "relative", fontSize: "14px", letterSpacing: "0.16em", color: C.gold } as Partial<CSSStyleDeclaration>, confirm, "LUFFY NEEDS YOUR YES");
el("div", { position: "relative", marginTop: "8px", fontSize: "21px", lineHeight: "1.35" } as Partial<CSSStyleDeclaration>, confirm, "Send Q3_Attrition_Report.xlsx to Arjun Rao?");
const yes = el("div", { position: "relative", marginTop: "16px", height: "56px", borderRadius: "18px", background: C.gold, color: "#0f0d0b", display: "grid", placeItems: "center", fontSize: "20px", fontWeight: "600" } as Partial<CSSStyleDeclaration>, confirm, "Yes, send it");
const sent = el("div", { left: "0", top: "540px", width: "430px", textAlign: "center", fontSize: "44px", fontWeight: "600", fontFamily: display, color: C.leaf }, phone, "Sent.");
const reply = el("div", { left: "60px", top: "640px", width: "310px", padding: "16px 20px", borderRadius: "24px 24px 24px 8px", background: "rgba(40,34,27,0.95)", fontSize: "20px", lineHeight: "1.35", boxSizing: "border-box" }, phone, "Arjun: Got it. Perfect timing.");

// The far-away laptop (scene 2)
const laptopWrap = el("div", { left: "1060px", top: "330px", width: "620px", height: "420px" });
const laptop = el("div", { left: "60px", top: "0", width: "500px", height: "320px", borderRadius: "22px", border: `3px solid #4a3f33`, background: "linear-gradient(180deg,#14110d,#0c0a08)", boxSizing: "border-box" }, laptopWrap);
el("div", { left: "0", top: "320px", width: "620px", height: "22px", borderRadius: "0 0 26px 26px", background: "#2a241d" }, laptopWrap);
el("div", { left: "50%", top: "50%", transform: "translate(-50%,-50%)", fontSize: "26px", color: C.dim, letterSpacing: "0.04em" }, laptop, "Locked");
const distance = el("div", { left: "1060px", top: "800px", width: "620px", textAlign: "center", fontSize: "36px", fontWeight: "700", fontFamily: display, color: C.kin }, stage, "40 km away");

// Big statement + end card
const statement = el("div", { left: "0", top: "380px", width: `${W}px`, textAlign: "center", fontSize: "150px", fontWeight: "800", fontFamily: display, letterSpacing: "-0.02em" }, stage, "Done in seconds.");
const endOrb = el("canvas", { left: `${W / 2 - 260}px`, top: "120px", width: "520px", height: "520px" }) as HTMLCanvasElement;
endOrb.width = 1040;
endOrb.height = 1040;
const endName = el("div", { left: "0", top: "630px", width: `${W}px`, display: "flex", justifyContent: "center", alignItems: "center", gap: "34px", fontSize: "120px", fontWeight: "800", fontFamily: display, letterSpacing: "0.02em" }, stage);
el("span", { position: "relative", display: "grid", placeItems: "center", writingMode: "vertical-rl", width: "62px", height: "128px", background: C.shu, color: C.bg, borderRadius: "5px", fontSize: "34px", fontWeight: "800", letterSpacing: "0", transform: "rotate(-3deg)" } as Partial<CSSStyleDeclaration>, endName, "ルフィ");
el("span", { position: "relative" } as Partial<CSSStyleDeclaration>, endName, "Luffy");
const endLine = el("div", { left: "0", top: "800px", width: `${W}px`, textAlign: "center", fontSize: "44px", fontWeight: "700", fontFamily: display, color: C.kin }, stage, "Your laptop. From anywhere.");
const endSmall = el("div", { left: "0", top: "880px", width: `${W}px`, textAlign: "center", fontSize: "24px", color: C.muted }, stage, "Runs on your own PC. Asks before it sends.");

// ---------- the ensō (the same brush stroke as the site and the real lock screen) ----------
const inkCache = new Map<string, HTMLCanvasElement>();
function inked(color: string, size: number, upto: number) {
  const key = `${color}|${size}|${upto.toFixed(2)}`;
  let c = inkCache.get(key);
  if (!c) {
    c = document.createElement("canvas");
    c.width = c.height = size;
    paintEnso(c.getContext("2d")!, size, color, upto);
    if (upto >= 1) inkCache.set(key, c); // keep only finished strokes; draw-in frames are one-offs
  }
  return c;
}
function rgbaOf(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
/** One frame of the circle: drawn in to `upto`, breathing, with ripples while listening, turning
 *  while thinking, and the 済 seal once sent. */
function drawEnso(cv: HTMLCanvasElement, t: number, color: string, o: { upto?: number; ripple?: number; spin?: number; seal?: number; glow?: number }) {
  const g = cv.getContext("2d")!;
  const S = cv.width, c = S / 2;
  g.clearRect(0, 0, S, S);
  const glow = g.createRadialGradient(c, c, S * 0.05, c, c, S * 0.5);
  glow.addColorStop(0, rgbaOf(color, o.glow ?? 0.14));
  glow.addColorStop(1, rgbaOf(color, 0));
  g.fillStyle = glow;
  g.fillRect(0, 0, S, S);
  for (let i = 0; i < 3 && (o.ripple ?? 0) > 0; i++) {
    const p = (t * 0.5 + i / 3) % 1;
    g.strokeStyle = rgbaOf(color, (1 - p) * 0.5 * (o.ripple ?? 0));
    g.lineWidth = S * 0.004;
    g.beginPath();
    g.arc(c, c, S * (0.36 + p * 0.14), 0, Math.PI * 2);
    g.stroke();
  }
  const upto = clamp(o.upto ?? 1);
  const ink = inked(color, S, upto * upto * (3 - 2 * upto));
  g.save();
  g.translate(c, c);
  g.rotate(o.spin ?? 0);
  const breath = 1 + 0.012 * Math.sin(t * 1.6);
  g.scale(breath, breath);
  g.drawImage(ink, -c, -c);
  g.restore();
  const seal = o.seal ?? 0;
  if (seal > 0) {
    const s = S * 0.13 * (1.4 - 0.4 * seal);
    g.save();
    g.globalAlpha = seal;
    g.translate(c, c);
    g.rotate(-0.06);
    g.fillStyle = C.shu;
    g.fillRect(-s / 2, -s / 2, s, s);
    g.fillStyle = "#F7EFE2";
    g.font = `800 ${s * 0.5}px ${display}`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("済", 0, s * 0.03);
    g.restore();
  }
}

// ---------- the timeline ----------
function typed(text: string, t: number, a: number, cps = 26) {
  const n = Math.floor(clamp((t - a) * cps, 0, text.length));
  return text.slice(0, n);
}
const LINE = "“Luffy, email the Q3 attrition report to Arjun.”";

export function render(t: number) {
  // Scene 1 (0-3.6): the message lands.
  const s1 = window_(t, 0, 3.8, 0.5);
  // Scene 2 (3.6-6.8): her laptop is far away.
  const s2 = window_(t, 3.6, 6.9, 0.5);
  // Scenes 3-5 (6.6-15.4): Luffy on her phone.
  const sJ = window_(t, 6.6, 15.6, 0.5);
  // Scene 6 (15.2-17.6): the statement. Scene 7 (17.4-20): end card.
  const s6 = window_(t, 15.3, 17.7, 0.45);
  const s7 = enter(t, 17.5, 0.8);

  // captions
  let small = "", big = "";
  if (t < 3.7) { small = "6:40 PM · Meera, HR lead"; big = "The board call starts in ten minutes."; }
  else if (t < 6.8) { small = "The report is on her work laptop."; big = "Her laptop is at the office."; }
  else if (t < 10.4) { small = "So she asks Luffy."; big = "One sentence."; }
  else if (t < 13.2) { small = "Luffy finds it, and asks first."; big = "Nothing sends without a yes."; }
  else { small = "From her phone, to her own PC."; big = "Sent."; }
  const capA = Math.max(s1, s2, sJ) * (1 - s6) * (1 - s7);
  capSmall.textContent = small;
  capBig.textContent = big;
  capSmall.style.opacity = String(capA);
  capBig.style.opacity = String(capA);
  const capShift = (1 - enter(t % 100, [0, 3.7, 6.8, 10.4, 13.2].filter((x) => x <= t).pop() ?? 0, 0.5)) * 18;
  capBig.style.transform = `translateY(${capShift}px)`;

  // phone presence
  const phoneA = Math.max(s1, sJ) * (1 - s6);
  phone.style.opacity = String(phoneA);
  phone.style.transform = `translateY(${(1 - enter(t, 0.1, 0.9)) * 60}px) scale(${1 - s2 * 0.04})`;
  clock.textContent = t < 13.5 ? "6:40" : "6:41";

  // scene 1: notification
  notif.style.opacity = String(enter(t, 0.7, 0.4) * (1 - enter(t, 6.6, 0.4)));
  notif.style.transform = `translateY(${(1 - enter(t, 0.7, 0.5)) * -40}px)`;

  // scene 2: the laptop, far away
  laptopWrap.style.opacity = String(s2);
  laptopWrap.style.transform = `scale(${0.9 + enter(t, 3.6, 3) * 0.06})`;
  distance.style.opacity = String(s2 * enter(t, 4.3, 0.5));
  if (s2 > 0) phone.style.opacity = String(phoneA * (1 - s2));

  // scenes 3-5: Luffy on the phone
  const listening = t >= 6.8 && t < 10.0;
  const thinking = t >= 10.0 && t < 10.6;
  const success = t >= 12.6;
  const color = success ? C.leaf : listening ? C.gold : C.ink;
  orbCanvas.style.opacity = String(window_(t, 6.6, 15.6, 0.5));
  if (sJ > 0)
    drawEnso(orbCanvas, t, color, {
      upto: enter(t, 6.7, 1.3),
      ripple: listening ? 1 : 0,
      spin: thinking || (t >= 10.6 && t < 12.6) ? (t - 10) * 0.9 : 0,
      seal: success ? enter(t, 12.6, 0.35) : 0,
      glow: listening ? 0.22 : 0.12,
    });
  said.textContent = typed(LINE, t, 7.1);
  said.style.opacity = String(window_(t, 7.0, 11.4, 0.4));
  steps.style.opacity = String(window_(t, 10.5, 12.8, 0.3));
  stepRows.forEach((s, i) => {
    const a = enter(t, 10.6 + i * 0.5, 0.35);
    s.row.style.opacity = String(a);
    s.row.style.transform = `translateX(${(1 - a) * -16}px)`;
  });
  const confirmA = window_(t, 11.4, 12.8, 0.3);
  confirm.style.opacity = String(confirmA);
  confirm.style.transform = `translateY(${(1 - enter(t, 11.4, 0.4)) * 40}px)`;
  const press = t > 12.2 && t < 12.45;
  yes.style.transform = press ? "scale(0.96)" : "scale(1)";
  yes.style.filter = press ? "brightness(1.15)" : "none";
  sent.style.opacity = String(window_(t, 12.8, 15.6, 0.3));
  sent.style.transform = `scale(${0.9 + enter(t, 12.8, 0.5) * 0.1})`;
  reply.style.opacity = String(window_(t, 13.8, 15.6, 0.35));
  reply.style.transform = `translateY(${(1 - enter(t, 13.8, 0.5)) * 24}px)`;

  // scene 6: statement
  statement.style.opacity = String(s6);
  statement.style.transform = `translateY(${(1 - enter(t, 15.3, 0.7)) * 30}px)`;

  // scene 7: end card
  endOrb.style.opacity = String(s7);
  if (s7 > 0) drawEnso(endOrb, t, C.sumi, { upto: enter(t, 17.5, 1.4), glow: 0.06 });
  endName.style.opacity = String(enter(t, 17.8, 0.7));
  endLine.style.opacity = String(enter(t, 18.2, 0.7));
  endSmall.style.opacity = String(enter(t, 18.6, 0.7));
  endOrb.style.transform = `scale(${0.92 + inOut(clamp((t - 17.5) / 2.5)) * 0.08})`;
}

// Fit the 1920x1080 stage to the window when played live.
const capture = new URLSearchParams(location.search).has("capture");
function fit() {
  if (capture) return;
  const s = Math.min(innerWidth / W, innerHeight / H);
  stage.style.transform = `scale(${s})`;
}
fit();
addEventListener("resize", fit);

declare global {
  interface Window {
    __render: (t: number) => void;
    __duration: number;
  }
}
window.__render = render;
window.__duration = DURATION;

if (!capture) {
  const start = performance.now();
  const loop = (now: number) => {
    render(((now - start) / 1000) % DURATION);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
} else {
  render(0);
}
