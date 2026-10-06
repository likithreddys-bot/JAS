// VEM on the phone: the same glass orb and rings of light as the orb on the laptop.
// Everything here only draws — what it is doing comes from /state.

const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));

let pin = localStorage.getItem('jas-pin') || '';
if (!pin) { pin = prompt('PIN (shown on your laptop)') || ''; localStorage.setItem('jas-pin', pin); }

// How each look sits: light inside the glass (glow), glow around it (halo), light at the edge (rim),
// ring brightness (waves), how fast the rings revolve (spin), motes (orbit), a working arc, a paused
// dot, a swell while speaking (pulse). Kept in step with ui/theme.py (STATE_LOOKS) and
// ui/qml/GlassOrb.qml, which draw the same orb on the laptop.
const LOOKS = {
  waking:    {glow: 0.60, halo: 0.35, rim: 0.70, waves: 0.40, spin: 0.6, orbit: 0, arc: 0, dot: 0, pulse: 0},
  calm:      {glow: 1.00, halo: 0.60, rim: 0.90, waves: 0.75, spin: 1.0, orbit: 0, arc: 0, dot: 0, pulse: 0},
  alert:     {glow: 1.25, halo: 1.00, rim: 1.20, waves: 1.00, spin: 2.2, orbit: 0, arc: 0, dot: 0, pulse: 0},
  listening: {glow: 1.30, halo: 1.10, rim: 1.20, waves: 1.00, spin: 2.4, orbit: 0, arc: 0, dot: 0, pulse: 0},
  thinking:  {glow: 0.60, halo: 0.30, rim: 0.70, waves: 0.45, spin: 1.4, orbit: 1, arc: 0, dot: 0, pulse: 0},
  focused:   {glow: 0.90, halo: 0.60, rim: 1.00, waves: 0.55, spin: 1.7, orbit: 0, arc: 1, dot: 0, pulse: 0},
  warm:      {glow: 1.10, halo: 0.75, rim: 1.00, waves: 1.00, spin: 1.6, orbit: 0, arc: 0, dot: 0, pulse: 1},
  concerned: {glow: 1.00, halo: 0.80, rim: 1.20, waves: 0.65, spin: 2.6, orbit: 0, arc: 0, dot: 0, pulse: 0},
  asleep:    {glow: 0.30, halo: 0.12, rim: 0.45, waves: 0.15, spin: 0.0, orbit: 0, arc: 0, dot: 1, pulse: 0}
};
const LOOK_FOR = {
  starting: 'waking', standby: 'calm', wake_detected: 'alert', listening: 'listening',
  transcribing: 'thinking', thinking: 'thinking', planning: 'thinking',
  executing: 'focused', observing: 'focused', responding: 'warm',
  error: 'concerned', sleeping: 'asleep', resting: 'asleep'
};

let target = LOOKS.calm, cur = {...LOOKS.calm}, look = {x: 0, y: 0}, voice = 0, accentNow = '#E8BE76';

function mix(hex, white, t) {
  const n = parseInt(hex.slice(1), 16);
  const r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const f = c => Math.round(c + (white - c) * t);
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}
const shade = (hex, k) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${[n >> 16, (n >> 8) & 255, n & 255].map(c => Math.round(c * k)).join(',')})`;
};

function paint(accent) {
  accentNow = accent;
  const root = document.documentElement.style;
  root.setProperty('--accent', accent);
  const stop = (id, color, opacity) => { const e = $(id); e.setAttribute('stop-color', color); e.setAttribute('stop-opacity', opacity); };
  // the light inside the glass, then a second one turning the other way, then the rim
  stop('la0', mix(accent, 255, 0.45), 0.95); stop('la1', accent, 0.80);
  stop('la2', shade(accent, 0.45), 0.38);    stop('la3', accent, 0);
  stop('lb0', mix(accent, 0, 0), 0.34);      stop('lb1', accent, 0);
  stop('e0', accent, 0);                     stop('e1', accent, 0);
  stop('e2', mix(accent, 255, 0.2), 0.40);   stop('e3', mix(accent, 255, 0.5), 0.85);
  $('hair').setAttribute('stroke', mix(accent, 255, 0.5)); $('hair').setAttribute('stroke-opacity', '.35');
  $('arc').setAttribute('stroke', mix(accent, 255, 0.3));
  $('dot').setAttribute('fill', accent);
  for (const p of document.querySelectorAll('.bloom')) p.setAttribute('stroke', accent);
  for (const p of document.querySelectorAll('.line')) p.setAttribute('stroke', mix(accent, 255, 0.25));
  for (const c of document.querySelectorAll('.mote')) c.setAttribute('fill', mix(accent, 255, 0.5));
}

// --- the orb: three rings of light round a sphere of glass ------------------------------------
// The geometry is built once. Each ring is a circle seen at an angle (tilted, flattened) with a
// wave running round it, cut in two so the near half crosses in front of the glass and the far
// half passes behind it. Only rotations, opacities and a few positions change after that.

const SPHERE = 44, CENTRE = 100, TAU = Math.PI * 2;
const RINGS = [
  {f: 1.36, lobes: 6, tilt: -20, squash: 0.34, secs: 26, dir:  1},
  {f: 1.62, lobes: 8, tilt:  26, squash: 0.38, secs: 34, dir: -1},
  {f: 1.90, lobes: 4, tilt:  -6, squash: 0.26, secs: 44, dir:  1}
];
const phase = RINGS.map(() => 0);

function wavy(f, lobes) {
  const base = SPHERE * f, amp = base * 0.065;
  let d = '';
  for (let i = 0; i <= 240; i++) {
    const a = i / 240 * TAU, r = base + amp * Math.sin(lobes * a);
    d += (i ? 'L' : 'M') + (CENTRE + r * Math.cos(a)).toFixed(1) + ' ' + (CENTRE + r * Math.sin(a)).toFixed(1);
  }
  return d;
}
(function build() {
  const ring = (r, i, side) => `<g transform="translate(100 100) rotate(${r.tilt}) scale(1 ${r.squash}) translate(-100 -100)"
      clip-path="url(#${side})"><g class="spin" data-i="${i}">
      <path class="bloom" d="${wavy(r.f, r.lobes)}" fill="none" stroke-width="9" stroke-linecap="round" vector-effect="non-scaling-stroke" opacity=".2"/>
      <path class="line" d="${wavy(r.f, r.lobes)}" fill="none" stroke-width="1.6" stroke-linecap="round" vector-effect="non-scaling-stroke"/></g></g>`;
  $('back').innerHTML = RINGS.map((r, i) => ring(r, i, 'far')).join('');
  $('front').innerHTML = RINGS.map((r, i) => ring(r, i, 'near')).join('');
  // the motes that circle while it thinks: seven, each drawn twice, once behind and once in front
  const motes = side => Array.from({length: 7}, (_, k) =>
    `<circle class="mote ${side}" data-k="${k}" r="${2 + (k % 3) * 0.6}" opacity="0"/>`).join('');
  $('motesBack').innerHTML = `<g transform="rotate(-14 100 100)">${motes('far')}</g>`;
  $('motesFront').innerHTML = `<g transform="rotate(-14 100 100)">${motes('near')}</g>`;
  $('arc').setAttribute('d', arcPath(SPHERE * 1.27, -90, 105));
})();

function arcPath(r, from, sweep) {
  const p = a => [CENTRE + r * Math.cos(a * Math.PI / 180), CENTRE + r * Math.sin(a * Math.PI / 180)];
  const [x0, y0] = p(from), [x1, y1] = p(from + sweep);
  return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}

let last = performance.now();

// One frame: ease each number towards its target, then place everything. `draw()` is also called
// when the phone is tilted or touched, so the light inside leans at once.
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  const k = 1 - Math.exp(-dt * 5);
  for (const key of Object.keys(target)) cur[key] += (target[key] - cur[key]) * k;
  RINGS.forEach((r, i) => { phase[i] += r.dir * dt * 360 / r.secs * cur.spin; });
  draw(now / 1000);
  // a paused orb hardly changes, so it does not need sixty frames a second
  if (cur.dot > 0.9 && target.dot === 1) setTimeout(() => requestAnimationFrame(frame), 60);
  else requestAnimationFrame(frame);
}

function draw(t = performance.now() / 1000) {
  const breathe = 0.5 + 0.5 * Math.sin(t * (target.dot ? 1.2 : 2.0));
  const grow = 1 + breathe * (cur.pulse > 0.5 ? 0.045 : 0.02) + voice * 0.06;
  $('sphere').setAttribute('transform', `translate(100 100) scale(${grow.toFixed(3)}) translate(-100 -100)`);
  const lean = SPHERE * 0.30, drift = t * TAU / 24;
  const a = [look.x * lean + SPHERE * 0.12 * Math.sin(drift), look.y * lean + SPHERE * 0.10 * Math.cos(2 * drift) + SPHERE * 0.14];
  const b = [SPHERE * 0.38 * Math.cos(drift * 3 + 1.2), SPHERE * 0.30 * Math.sin(drift * 3 + 1.2) - SPHERE * 0.09];
  const glow = Math.min(1, cur.glow), size = 0.75 + 0.25 * cur.glow;
  $('lightGroupA').setAttribute('transform', `translate(${(100 + a[0]).toFixed(1)} ${(100 + a[1]).toFixed(1)}) scale(${size.toFixed(3)}) translate(-100 -100)`);
  $('lightGroupA').setAttribute('opacity', glow.toFixed(2));
  $('lightGroupB').setAttribute('transform', `translate(${(100 + b[0]).toFixed(1)} ${(100 + b[1]).toFixed(1)}) translate(-100 -100)`);
  $('lightGroupB').setAttribute('opacity', Math.min(1, cur.glow).toFixed(2));
  $('rim').setAttribute('opacity', Math.min(1, cur.rim).toFixed(2));

  document.querySelectorAll('.spin').forEach(g =>
    g.setAttribute('transform', `rotate(${phase[g.dataset.i].toFixed(2)} 100 100)`));
  const rs = 1 + voice * 0.10;
  document.querySelectorAll('#back > g, #front > g').forEach(g => g.style.opacity = Math.min(1, cur.waves).toFixed(2));
  $('back').style.transformOrigin = $('front').style.transformOrigin = '100px 100px';
  $('back').style.transform = $('front').style.transform = `scale(${rs.toFixed(3)})`;

  // thinking: motes circling
  const turn = t * TAU / 1.5;
  for (const c of document.querySelectorAll('.mote')) {
    const k = +c.dataset.k, ang = turn + k * TAU / 7, near = Math.sin(ang) > 0;
    c.setAttribute('cx', (100 + SPHERE * 1.34 * Math.cos(ang)).toFixed(1));
    c.setAttribute('cy', (100 + SPHERE * 1.34 * Math.sin(ang) * 0.42).toFixed(1));
    c.setAttribute('opacity', (c.classList.contains('near') === near ? cur.orbit * (0.35 + 0.65 * k / 6) : 0).toFixed(2));
  }
  // working: one clean arc turning
  $('arc').setAttribute('opacity', cur.arc.toFixed(2));
  $('arc').setAttribute('transform', `rotate(${(t * 211).toFixed(1)} 100 100)`);
  // paused: one dot
  $('dot').setAttribute('opacity', (cur.dot * 0.85).toFixed(2));

  // the glow around it
  const halo = Math.min(1, cur.halo * (0.55 + breathe * 0.35) + voice * 0.5);
  const h = $('halo'); h.style.opacity = halo.toFixed(2);
  h.style.transform = `scale(${(0.92 + breathe * 0.06 + voice * 0.14).toFixed(3)})`;
}
paint(accentNow);
requestAnimationFrame(frame);

// The light inside the glass follows the phone itself: tilt it and it leans the way you tilt.
// Touching the screen takes over while your thumb is down, then the tilt has it back.
let tilting = false, thumbUntil = 0;

function watchTilt() {
  addEventListener('deviceorientation', e => {
    if (e.gamma === null && e.beta === null) return;
    tilting = true;
    if (performance.now() < thumbUntil) return;
    // gamma is the left-right tilt, beta the front-back one. Level is beta ~45 when held up.
    const x = Math.max(-1, Math.min(1, (e.gamma || 0) / 34));
    const y = Math.max(-1, Math.min(1, ((e.beta || 45) - 45) / 34));
    look = {x, y};
    draw();
  }, {passive: true});
}

// iPhones only hand over motion after the user has asked for it, and only on a tap.
async function askForTilt() {
  const api = window.DeviceOrientationEvent;
  if (!api) return;
  if (typeof api.requestPermission === 'function') {
    try { if (await api.requestPermission() !== 'granted') return; } catch (e) { return; }
  }
  watchTilt();
}
addEventListener('pointerdown', askForTilt, {once: true});
if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission !== 'function') {
  watchTilt();   // Android needs no asking
}

// A thumb on the screen wins over the tilt for a moment, so looking at a tap still works.
addEventListener('pointermove', e => {
  thumbUntil = performance.now() + 2500;
  const box = $('svg').getBoundingClientRect();
  const dx = (e.clientX - (box.left + box.width / 2)) / (innerWidth * 0.55);
  const dy = (e.clientY - (box.top + box.height / 2)) / (innerHeight * 0.55);
  const len = Math.hypot(dx, dy) || 1;
  const pull = Math.min(1, len);
  look = {x: dx / len * pull, y: dy / len * pull};
  draw();
}, {passive: true});

// Installed as an app there is no address bar, so say so once.
if (matchMedia('(display-mode: standalone)').matches) document.body.dataset.app = 'yes';

// --- talking to the laptop ------------------------------------------------

let spokenId = 0, audioAllowed = false;
const player = new Audio();
const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=';

function allowAudio() {
  if (audioAllowed) return;
  player.src = SILENT;
  player.play().then(() => { audioAllowed = true; }).catch(() => {});
}
addEventListener('pointerdown', allowAudio);

async function speak(id) {
  if (id === spokenId) return;
  spokenId = id;
  try { player.src = `/voice?pin=${encodeURIComponent(pin)}&n=${id}`; await player.play(); }
  catch (e) { $('tip').textContent = 'tap once to let me speak'; }
}

function show(state) {
  paint(state.colour);
  target = LOOKS[LOOK_FOR[state.state] || 'calm'];
  $('label').textContent = state.label;
  const busy = state.busy || state.state === 'listening';
  document.documentElement.style.setProperty('--glow', busy ? '1' : '0');
  $('edge').classList.toggle('pulse', busy);

  const talk = $('talk');
  talk.innerHTML = '';
  if (state.heard) talk.insertAdjacentHTML('beforeend',
    `<div class="bubble you"><span class="who">YOU</span>${esc(state.heard)}</div>`);
  if (state.said) talk.insertAdjacentHTML('beforeend',
    `<div class="bubble"><span class="who">${NAME}</span>${esc(state.said)}</div>`);
  $('send').disabled = false;
  if (state.can_speak && state.said && !state.busy) speak(state.reply_id);
}

async function poll() {
  try {
    const r = await fetch(`/state?pin=${encodeURIComponent(pin)}`);
    if (r.status === 403) {
      $('label').textContent = 'wrong PIN — tap to change';
      $('label').onclick = () => { localStorage.removeItem('jas-pin'); location.reload(); };
      return;
    }
    show(await r.json());
  } catch (e) { $('label').textContent = 'laptop not reachable'; }
}

$('form').onsubmit = async e => {
  e.preventDefault();
  const text = $('text').value.trim();
  if (!text) return;
  $('text').value = ''; $('send').disabled = true; allowAudio(); spokenId = 0;
  $('talk').innerHTML = `<div class="bubble you"><span class="who">YOU</span>${esc(text)}</div>`;
  const r = await fetch(`/ask?pin=${encodeURIComponent(pin)}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
  const out = await r.json();
  if (out.error) $('tip').textContent = out.error;
};

// --- always listening -------------------------------------------------------
// No button to hold. The microphone opens when the app does and stays open; a sentence is sent
// when you stop speaking, the way the laptop decides you have finished. Audio is turned into a
// 16 kHz WAV here and transcribed on the laptop, so nothing goes to a cloud.

const SPEAKING = 0.018;      // above this the microphone may be hearing a voice
const CLEARLY_SPEECH = 0.045;  // a real voice peaks well past that; a fan or traffic does not
const QUIET_MS = 1100;       // this much silence means the sentence is over
const MIN_MS = 350;          // of speech, not of clip - see heard()
const MAX_MS = 15000;

let ctx, source, node, stream;
let listening = false, paused = false, speaking = false;
let chunks = [], startedAt = 0, quietSince = 0, rate = 48000;
let spokenMs = 0, peak = 0;  // how much of this clip was actually speech, and how loud it got

const bars = [];
for (let i = 0; i < 9; i++) { const b = document.createElement('i'); $('level').append(b); bars.push(b); }

function meter(level) {
  const peak = Math.min(1, level / 0.25);
  voice = level > 0 ? peak : 0;   // the orb swells with your voice
  bars.forEach((b, i) => {
    const middle = 1 - Math.abs(i - 4) / 5;
    b.style.height = (4 + peak * 22 * middle).toFixed(0) + 'px';
  });
}

function wavFrom(samples, sampleRate) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const put = (at, t) => { for (let i = 0; i < t.length; i++) view.setUint8(at + i, t.charCodeAt(i)); };
  put(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); put(8, 'WAVEfmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  put(36, 'data'); view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) view.setInt16(44 + i * 2, samples[i], true);
  return new Blob([view], {type: 'audio/wav'});
}

function toSixteenK(blocks, from) {
  const flat = new Float32Array(blocks.reduce((n, b) => n + b.length, 0));
  let at = 0;
  for (const b of blocks) { flat.set(b, at); at += b.length; }
  const step = from / 16000, out = new Int16Array(Math.floor(flat.length / step));
  for (let i = 0; i < out.length; i++) {
    const a = Math.floor(i * step), z = Math.min(flat.length, Math.floor((i + 1) * step));
    let sum = 0;
    for (let j = a; j < z; j++) sum += flat[j];
    out[i] = Math.max(-32768, Math.min(32767, (sum / Math.max(1, z - a)) * 32767));
  }
  return out;
}

async function send(blocks) {
  const wav = wavFrom(toSixteenK(blocks, rate), 16000);
  if (wav.size < 3000) return;
  $('tip').textContent = 'thinking…';
  spokenId = 0;
  try {
    const r = await fetch(`/listen?pin=${encodeURIComponent(pin)}`, {method: 'POST', body: wav});
    const out = await r.json();
    if (out.heard) $('talk').innerHTML =
      `<div class="bubble you"><span class="who">YOU</span>${esc(out.heard)}</div>`;
    $('tip').textContent = out.error || 'listening';
  } catch (e) { $('tip').textContent = 'laptop not reachable'; }
}

function heard(buffer) {
  // While it is speaking through this phone, ignore the microphone or it hears itself.
  if (paused || (!player.paused && !player.ended)) {
    chunks = []; speaking = false; spokenMs = 0; peak = 0; return;
  }

  let sum = 0;
  for (let i = 0; i < buffer.length; i++) sum += buffer[i] * buffer[i];
  const level = Math.sqrt(sum / buffer.length);
  meter(level);
  const now = performance.now();

  if (level > SPEAKING) {
    if (!speaking) {
      speaking = true; startedAt = now; chunks = []; spokenMs = 0; peak = 0;
      $('tip').textContent = 'listening…';
    }
    // Count only the time spent above the threshold, one frame at a time. Measuring from startedAt
    // would include the 1.1 s of silence that ends every clip, so any cough would clear MIN_MS and
    // wake Whisper - which then hallucinates "Thank you." on near-silence. Adding the frame's own
    // length rather than the gap since the last loud frame means a pause mid-sentence is not
    // counted as speech.
    spokenMs += buffer.length / rate * 1000;
    peak = Math.max(peak, level);
    quietSince = now;
  }
  if (!speaking) return;

  chunks.push(new Float32Array(buffer));
  const over = now - quietSince > QUIET_MS || now - startedAt > MAX_MS;
  if (!over) return;

  // Both tests are on the speech, not the clip: enough of it, and loud enough to be a voice.
  // Failing either, the clip is dropped here rather than sent - Whisper is never woken for a cough.
  const wasSpeech = spokenMs > MIN_MS && peak > CLEARLY_SPEECH;
  const done = chunks;
  chunks = []; speaking = false; spokenMs = 0; peak = 0;
  if (wasSpeech) send(done); else $('tip').textContent = 'listening';
}

async function listen() {
  if (listening) return;
  try { stream = await navigator.mediaDevices.getUserMedia({
    audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}}); }
  catch (e) { $('tip').textContent = 'let me use the microphone, then reopen'; return; }
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  await ctx.resume();
  rate = ctx.sampleRate;
  source = ctx.createMediaStreamSource(stream);
  node = ctx.createScriptProcessor(4096, 1, 1);
  node.onaudioprocess = e => heard(e.inputBuffer.getChannelData(0));
  source.connect(node); node.connect(ctx.destination);
  listening = true;
  $('tip').textContent = 'listening';
}

function stopListening() {
  if (!listening) return;
  try { node.disconnect(); source.disconnect(); stream.getTracks().forEach(t => t.stop()); ctx.close(); }
  catch (e) {}
  listening = false; speaking = false; chunks = [];
  meter(0);
}

$('pause').onclick = async () => {
  paused = !paused;
  $('pause').textContent = paused ? 'Resume' : 'Pause';
  $('pause').classList.toggle('off', paused);
  $('tip').textContent = paused ? 'paused — not listening' : 'listening';
  if (paused) stopListening(); else { allowAudio(); await listen(); }
};

$('hide').onclick = () => {
  document.body.style.transition = 'opacity .25s';
  document.body.style.opacity = document.body.style.opacity === '0.12' ? '1' : '0.12';
};

// Start listening the moment the app opens. Phones need one touch before they hand over the
// microphone, so if it is refused we say so rather than sitting there silently doing nothing.
async function begin() {
  allowAudio();
  await askForTilt();
  await listen();
}
addEventListener('pointerdown', begin, {once: true});
begin();

// Stop holding the microphone while the app is in the background; phones suspend it anyway.
addEventListener('visibilitychange', () => {
  if (document.hidden) stopListening();
  else if (!paused) listen();
});

poll();
setInterval(poll, 900);
