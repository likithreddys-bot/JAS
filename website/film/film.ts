/* The JAS film: 20 seconds, 1920x1080. Every frame is a pure function of time t, so it can be
 * rendered frame by frame into a perfectly smooth video, and also played live.
 * Story (dramatised): Meera in HR must send an urgent report to her manager; her laptop is 40 km
 * away; she asks JAS on her phone; JAS confirms and sends it in seconds. */
import "@fontsource-variable/inter-tight";
import "@fontsource-variable/inter";

const W = 1920;
const H = 1080;
export const DURATION = 20;

const C = {
  bg: "#080706",
  coal: "#17130F",
  ink: "#F7F1E6",
  gold: "#E8BE76",
  ember: "#E2553F",
  leaf: "#A8CF78",
  muted: "#A69C8D",
};

// ---------- easing and timing helpers ----------
const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x: number) => 1 - Math.pow(1 - clamp(x), 3); // ease-out cubic
const inOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
/** 0 before `a`, eases to 1 over `d` seconds. */
const enter = (t: number, a: number, d = 0.6) => ease((t - a) / d);
/** 1 while inside [a, b], fading in and out over `f` seconds. */
const window_ = (t: number, a: number, b: number, f = 0.5) => Math.min(enter(t, a, f), 1 - enter(t, b - f, f));

// ---------- stage ----------
const stage = document.getElementById("stage")!;
document.documentElement.style.background = C.bg;
Object.assign(document.body.style, { margin: "0", background: C.bg, overflow: "hidden" });
Object.assign(stage.style, {
  position: "relative",
  width: `${W}px`,
  height: `${H}px`,
  background: `radial-gradient(1200px 700px at 50% 60%, #15110c 0%, ${C.bg} 70%)`,
  overflow: "hidden",
  fontFamily: '"Inter Variable", system-ui, sans-serif',
  color: C.ink,
  transformOrigin: "0 0",
});

function el<K extends keyof HTMLElementTagNameMap>(tag: K, css: Partial<CSSStyleDeclaration>, parent: HTMLElement = stage, text = "") {
  const e = document.createElement(tag);
  Object.assign(e.style, { position: "absolute", ...css });
  if (text) e.textContent = text;
  parent.appendChild(e);
  return e;
}
const display = '"Inter Tight Variable", system-ui, sans-serif';

// Captions (top-left, film-title style)
const capSmall = el("div", { left: "160px", top: "150px", fontSize: "30px", color: C.muted, fontFamily: display, letterSpacing: "0.02em" });
const capBig = el("div", { left: "160px", top: "200px", fontSize: "84px", fontWeight: "600", fontFamily: display, letterSpacing: "-0.035em", lineHeight: "1.02", width: "820px" });

// The phone
const phone = el("div", {
  left: "1150px", top: "110px", width: "430px", height: "880px", borderRadius: "64px",
  background: "#0d0b09", border: "2px solid #3a3128",
  boxShadow: "0 0 0 10px #15110d, 0 80px 160px -40px rgba(232,190,118,0.35)", overflow: "hidden",
});
el("div", { left: "155px", top: "18px", width: "120px", height: "34px", borderRadius: "20px", background: "#000" }, phone);
const clock = el("div", { left: "40px", top: "22px", fontSize: "20px", fontWeight: "600" }, phone, "6:40");
// notification
const notif = el("div", { left: "18px", top: "84px", width: "394px", padding: "20px 22px", borderRadius: "28px", background: "rgba(40,34,27,0.92)", boxSizing: "border-box" }, phone);
el("div", { position: "relative", fontSize: "17px", color: C.muted } as Partial<CSSStyleDeclaration>, notif, "Arjun Rao · Manager · now");
el("div", { position: "relative", marginTop: "6px", fontSize: "22px", lineHeight: "1.35" } as Partial<CSSStyleDeclaration>, notif, "Need the Q3 attrition report before the board call. 10 minutes?");
// JAS screen inside the phone
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
el("div", { position: "relative", fontSize: "14px", letterSpacing: "0.16em", color: C.gold } as Partial<CSSStyleDeclaration>, confirm, "JAS NEEDS YOUR YES");
el("div", { position: "relative", marginTop: "8px", fontSize: "21px", lineHeight: "1.35" } as Partial<CSSStyleDeclaration>, confirm, "Send Q3_Attrition_Report.xlsx to Arjun Rao?");
const yes = el("div", { position: "relative", marginTop: "16px", height: "56px", borderRadius: "18px", background: C.gold, color: C.bg, display: "grid", placeItems: "center", fontSize: "20px", fontWeight: "600" } as Partial<CSSStyleDeclaration>, confirm, "Yes, send it");
const sent = el("div", { left: "0", top: "540px", width: "430px", textAlign: "center", fontSize: "44px", fontWeight: "600", fontFamily: display, color: C.leaf }, phone, "Sent.");
const reply = el("div", { left: "60px", top: "640px", width: "310px", padding: "16px 20px", borderRadius: "24px 24px 24px 8px", background: "rgba(40,34,27,0.95)", fontSize: "20px", lineHeight: "1.35", boxSizing: "border-box" }, phone, "Arjun: Got it. Perfect timing.");

// The far-away laptop (scene 2)
const laptopWrap = el("div", { left: "1060px", top: "330px", width: "620px", height: "420px" });
const laptop = el("div", { left: "60px", top: "0", width: "500px", height: "320px", borderRadius: "22px", border: `3px solid #4a3f33`, background: "linear-gradient(180deg,#14110d,#0c0a08)", boxSizing: "border-box" }, laptopWrap);
el("div", { left: "0", top: "320px", width: "620px", height: "22px", borderRadius: "0 0 26px 26px", background: "#2a241d" }, laptopWrap);
el("div", { left: "50%", top: "50%", transform: "translate(-50%,-50%)", fontSize: "26px", color: C.muted, letterSpacing: "0.04em" }, laptop, "Locked");
const distance = el("div", { left: "1060px", top: "800px", width: "620px", textAlign: "center", fontSize: "34px", fontFamily: display, color: C.gold }, stage, "40 km away");

// Big statement + end card
const statement = el("div", { left: "0", top: "380px", width: `${W}px`, textAlign: "center", fontSize: "150px", fontWeight: "600", fontFamily: display, letterSpacing: "-0.05em" }, stage, "Done in seconds.");
const endOrb = el("canvas", { left: `${W / 2 - 260}px`, top: "120px", width: "520px", height: "520px" }) as HTMLCanvasElement;
endOrb.width = 1040;
endOrb.height = 1040;
const endName = el("div", { left: "0", top: "640px", width: `${W}px`, textAlign: "center", fontSize: "120px", fontWeight: "600", fontFamily: display, letterSpacing: "-0.04em" }, stage, "JAS");
const endLine = el("div", { left: "0", top: "790px", width: `${W}px`, textAlign: "center", fontSize: "44px", fontFamily: display, color: C.gold, letterSpacing: "-0.02em" }, stage, "Your laptop. From anywhere.");
const endSmall = el("div", { left: "0", top: "880px", width: `${W}px`, textAlign: "center", fontSize: "24px", color: C.muted }, stage, "Runs on your own PC. Asks before it sends.");

// ---------- the orb (same language as the site: glass, inner light, revolving waves) ----------
function hexRgb(h: string) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function drawOrb(cv: HTMLCanvasElement, t: number, color: string, energy: number, ringAlpha = 1) {
  const g = cv.getContext("2d")!;
  const S = cv.width;
  const cx = S / 2, cy = S / 2, R = S * 0.24;
  const [r, gg, b] = hexRgb(color);
  g.clearRect(0, 0, S, S);
  g.globalCompositeOperation = "lighter";
  // halo
  const halo = g.createRadialGradient(cx, cy, R * 0.6, cx, cy, S * 0.5);
  halo.addColorStop(0, `rgba(${r},${gg},${b},${0.45 + energy * 0.25})`);
  halo.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = halo;
  g.fillRect(0, 0, S, S);
  // waves behind
  drawWaves(g, cx, cy, R, t, energy, `${r},${gg},${b}`, ringAlpha, false);
  g.globalCompositeOperation = "source-over";
  // glass body with inner light
  const body = g.createRadialGradient(cx - R * 0.15, cy - R * 0.2, R * 0.05, cx, cy, R);
  body.addColorStop(0, `rgba(255,244,222,1)`);
  body.addColorStop(0.35, `rgba(${r},${gg},${b},1)`);
  body.addColorStop(0.8, `rgba(${Math.round(r * 0.45)},${Math.round(gg * 0.38)},${Math.round(b * 0.3)},1)`);
  body.addColorStop(1, `rgba(${Math.round(r * 0.25)},${Math.round(gg * 0.2)},${Math.round(b * 0.15)},1)`);
  g.fillStyle = body;
  g.beginPath();
  g.arc(cx, cy, R, 0, Math.PI * 2);
  g.fill();
  // swirl inside
  g.save();
  g.beginPath();
  g.arc(cx, cy, R, 0, Math.PI * 2);
  g.clip();
  g.globalCompositeOperation = "lighter";
  for (let i = 0; i < 3; i++) {
    const a = t * (0.35 + i * 0.12) + i * 2.1;
    const sw = g.createRadialGradient(cx + Math.cos(a) * R * 0.35, cy + Math.sin(a) * R * 0.3, 0, cx + Math.cos(a) * R * 0.35, cy + Math.sin(a) * R * 0.3, R * 0.7);
    sw.addColorStop(0, `rgba(${r},${gg},${b},0.22)`);
    sw.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = sw;
    g.fillRect(0, 0, S, S);
  }
  // rim light
  g.globalCompositeOperation = "lighter";
  const rim = g.createRadialGradient(cx, cy, R * 0.82, cx, cy, R);
  rim.addColorStop(0, "rgba(0,0,0,0)");
  rim.addColorStop(1, `rgba(${r},${gg},${b},0.55)`);
  g.fillStyle = rim;
  g.fillRect(0, 0, S, S);
  // specular highlight
  const hl = g.createRadialGradient(cx - R * 0.38, cy - R * 0.45, 0, cx - R * 0.38, cy - R * 0.45, R * 0.22);
  hl.addColorStop(0, "rgba(255,255,255,0.85)");
  hl.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = hl;
  g.fillRect(0, 0, S, S);
  g.restore();
  // waves in front
  g.globalCompositeOperation = "lighter";
  drawWaves(g, cx, cy, R, t, energy, `${r},${gg},${b}`, ringAlpha, true);
  g.globalCompositeOperation = "source-over";
}
function drawWaves(g: CanvasRenderingContext2D, cx: number, cy: number, R: number, t: number, energy: number, rgb: string, alpha: number, front: boolean) {
  const rings = [
    { rad: 1.36, tilt: -0.35, squash: 0.3, freq: 6, speed: 0.7, phase: 0 },
    { rad: 1.62, tilt: 0.45, squash: 0.36, freq: 8, speed: -0.5, phase: 2.1 },
    { rad: 1.9, tilt: -0.1, squash: 0.24, freq: 4, speed: 0.4, phase: 4.2 },
  ];
  for (const ring of rings) {
    for (const pass of [{ w: 26, a: 0.12 }, { w: 3.5, a: 0.9 }]) {
      g.lineWidth = pass.w;
      g.lineCap = "round";
      const N = 220;
      for (let i = 0; i < N; i++) {
        const u0 = (i / N) * Math.PI * 2;
        const u1 = ((i + 1) / N) * Math.PI * 2;
        // only draw the half of the ring that is in front of / behind the sphere
        const inFront = Math.sin(u0) > 0;
        if (inFront !== front) continue;
        const p = (u: number) => {
          const amp = (0.05 + energy * 0.09) * R;
          const w = Math.sin(u * ring.freq + ring.phase + t * 3 * (0.4 + energy)) * amp;
          const rr = ring.rad * R + w;
          const x = Math.cos(u) * rr;
          const y = Math.sin(u) * rr * ring.squash;
          return [cx + x * Math.cos(ring.tilt) - y * Math.sin(ring.tilt), cy + x * Math.sin(ring.tilt) + y * Math.cos(ring.tilt)];
        };
        const head = ((u0 / (Math.PI * 2) - t * ring.speed * 0.25) % 1 + 1) % 1;
        const a = (0.15 + 0.85 * Math.pow(head, 2.4)) * pass.a * alpha;
        const [x0, y0] = p(u0);
        const [x1, y1] = p(u1);
        g.strokeStyle = `rgba(${rgb},${a})`;
        g.beginPath();
        g.moveTo(x0, y0);
        g.lineTo(x1, y1);
        g.stroke();
      }
    }
  }
}

// ---------- the timeline ----------
function typed(text: string, t: number, a: number, cps = 26) {
  const n = Math.floor(clamp((t - a) * cps, 0, text.length));
  return text.slice(0, n);
}
const LINE = "“JAS, email the Q3 attrition report to Arjun.”";

export function render(t: number) {
  // Scene 1 (0-3.6): the message lands.
  const s1 = window_(t, 0, 3.8, 0.5);
  // Scene 2 (3.6-6.8): her laptop is far away.
  const s2 = window_(t, 3.6, 6.9, 0.5);
  // Scenes 3-5 (6.6-15.4): JAS on her phone.
  const sJ = window_(t, 6.6, 15.6, 0.5);
  // Scene 6 (15.2-17.6): the statement. Scene 7 (17.4-20): end card.
  const s6 = window_(t, 15.3, 17.7, 0.45);
  const s7 = enter(t, 17.5, 0.8);

  // captions
  let small = "", big = "";
  if (t < 3.7) { small = "6:40 PM · Meera, HR lead"; big = "The board call starts in ten minutes."; }
  else if (t < 6.8) { small = "The report is on her work laptop."; big = "Her laptop is at the office."; }
  else if (t < 10.4) { small = "So she asks JAS."; big = "One sentence."; }
  else if (t < 13.2) { small = "JAS finds it, and asks first."; big = "Nothing sends without a yes."; }
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

  // scenes 3-5: JAS on the phone
  const listening = t >= 6.8 && t < 10.0;
  const thinking = t >= 10.0 && t < 10.6;
  const success = t >= 12.6;
  const color = success ? C.leaf : t >= 11.2 ? C.gold : C.gold;
  const energy = listening ? 0.6 + 0.4 * Math.abs(Math.sin(t * 7)) * Math.abs(Math.sin(t * 2.3)) : thinking ? 0.2 : success ? 0.5 : 0.3;
  orbCanvas.style.opacity = String(window_(t, 6.6, 15.6, 0.5));
  if (sJ > 0) drawOrb(orbCanvas, t, color, energy);
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
  if (s7 > 0) drawOrb(endOrb, t, C.gold, 0.35 + 0.15 * Math.sin(t * 1.5));
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
