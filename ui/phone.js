// JAS on the phone: the same face, moods and planets as the orb on the laptop.
// Everything here only draws — what JAS is doing comes from /state.

const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));

let pin = localStorage.getItem('jas-pin') || '';
if (!pin) { pin = prompt('PIN (shown on your laptop)') || ''; localStorage.setItem('jas-pin', pin); }

// How each mood sits: how open the eyes are, how the brows tilt, how big the pupils are.
// Kept in step with ui/theme.py and ui/qml/Face.qml.
const MOODS = {
  waking:    {open: 0.55, brow:   0, lift:  0, pupil: 0.95, curve:  6},
  calm:      {open: 1.00, brow:   0, lift:  0, pupil: 1.00, curve:  6},
  alert:     {open: 1.12, brow:  -5, lift:  6, pupil: 1.25, curve:  3},
  listening: {open: 1.06, brow:  -3, lift:  4, pupil: 1.18, curve:  3},
  thinking:  {open: 0.70, brow:  10, lift: -2, pupil: 0.85, curve:  8},
  focused:   {open: 0.80, brow:   7, lift: -1, pupil: 0.92, curve:  8},
  warm:      {open: 0.00, brow:  -6, lift:  5, pupil: 1.00, curve:-14},
  concerned: {open: 0.85, brow:  15, lift: -4, pupil: 0.72, curve: 10},
  asleep:    {open: 0.06, brow:   0, lift: -1, pupil: 0.80, curve:  7}
};
const FACE_FOR = {
  starting: 'waking', standby: 'calm', wake_detected: 'alert', listening: 'listening',
  transcribing: 'thinking', thinking: 'thinking', planning: 'thinking',
  executing: 'focused', observing: 'focused', responding: 'warm',
  error: 'concerned', sleeping: 'asleep', resting: 'asleep'
};

let mood = MOODS.calm, blink = 0, look = {x: 0, y: 0}, body = '';

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
  const skin = mix(accent, 255, 0.58);
  document.documentElement.style.setProperty('--accent', accent);
  document.documentElement.style.setProperty('--skin', skin);
  $('lit').setAttribute('stop-color', mix(accent, 255, 0.74));
  $('mid').setAttribute('stop-color', skin);
  $('dim').setAttribute('stop-color', shade(skin, 0.72));
  $('rim').setAttribute('stroke', mix(accent, 255, 0.25));
  for (const id of ['ring1', 'ring2']) $(id).setAttribute('stroke', mix(accent, 255, 0.35));
  for (const c of document.querySelectorAll('#craters circle')) c.setAttribute('fill', shade(skin, 0.88));
  for (const b of document.querySelectorAll('#bands ellipse')) b.setAttribute('fill', shade(skin, 0.86));
}

// The markings that make each body itself, drawn once and shown by mood.
(function markings() {
  const craters = [[62, 74, 15], [132, 60, 9], [140, 122, 18], [74, 138, 11], [100, 96, 7]];
  $('craters').innerHTML = craters.map(([x, y, r]) =>
    `<circle cx="${x}" cy="${y}" r="${r}"/>`).join('');
  const bands = [[48, 10], [74, 15], [118, 12], [146, 9]];
  $('bands').innerHTML = bands.map(([y, h]) =>
    `<ellipse cx="100" cy="${y}" rx="78" ry="${h / 2}"/>`).join('');
  $('seas').innerHTML = `
    <ellipse cx="62" cy="86" rx="24" ry="16" fill="#5FA86B"/>
    <ellipse cx="132" cy="70" rx="17" ry="12" fill="#5FA86B"/>
    <ellipse cx="140" cy="128" rx="23" ry="15" fill="#5FA86B"/>
    <ellipse cx="74" cy="140" rx="15" ry="11" fill="#5FA86B"/>`;
})();

function showBody(name) {
  if (name === body) return;
  body = name;
  const on = el => el.setAttribute('opacity', '1'), off = el => el.setAttribute('opacity', '0');
  (name === 'moon' || name === 'mercury' ? on : off)($('craters'));
  (['jupiter', 'neptune', 'uranus'].includes(name) ? on : off)($('bands'));
  (name === 'earth' ? on : off)($('seas'));
  $('rings').setAttribute('opacity', name === 'saturn' ? '1' : '0');
}

function draw() {
  const openNow = Math.max(0, mood.open * (1 - blink));
  const round = Math.min(1, openNow / 0.28);
  $('eyes').setAttribute('opacity', round.toFixed(2));
  $('shut').setAttribute('opacity', (1 - round).toFixed(2));
  for (const [eye, cx] of [['L', 72], ['R', 128]]) {
    const ry = Math.max(1.2, 21 * openNow);
    $('eye' + eye).firstElementChild.setAttribute('ry', ry.toFixed(1));
    const pr = Math.min(10.5 * mood.pupil, ry);
    const px = cx + look.x * 8, py = 103 + look.y * 6;
    const pup = $('pup' + eye), spark = $('spark' + eye);
    pup.setAttribute('r', pr.toFixed(1)); pup.setAttribute('cx', px.toFixed(1)); pup.setAttribute('cy', py.toFixed(1));
    spark.setAttribute('cx', (px - 4).toFixed(1)); spark.setAttribute('cy', (py - 4).toFixed(1));
    spark.setAttribute('opacity', pr > 5 ? '1' : '0');
    const dir = eye === 'L' ? 1 : -1;
    const bx = eye === 'L' ? 56 : 112, tilt = mood.brow * dir * 0.6, lift = -mood.lift;
    $('brow' + eye).setAttribute('d',
      `M${bx} ${62 + lift + tilt} Q${bx + 16} ${54 + lift} ${bx + 32} ${62 + lift - tilt}`);
    const sx = eye === 'L' ? 53 : 109;
    $('shut' + eye).setAttribute('d', `M${sx} 103 Q${sx + 19} ${103 + mood.curve} ${sx + 38} 103`);
  }
  $('brows').setAttribute('opacity', body === 'moon' ? '0' : '1');
}

// Blinking, on the same irregular rhythm as the laptop.
(function blinker() {
  const next = () => 2200 + Math.random() * 4200;
  setTimeout(function go() {
    if (mood.open > 0.2) {
      const start = performance.now();
      const step = now => {
        const t = (now - start) / 190;
        blink = t < 0.4 ? t / 0.4 : t < 1 ? 1 - (t - 0.4) / 0.6 : 0;
        draw();
        if (t < 1) requestAnimationFrame(step); else blink = 0;
      };
      requestAnimationFrame(step);
    }
    setTimeout(go, next());
  }, next());
})();

// The eyes follow the phone itself: tilt it and JAS looks the way you tilt.
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
  showBody(state.body);
  mood = MOODS[FACE_FOR[state.state] || 'calm'];
  draw();
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
  // While JAS is speaking through this phone, ignore the microphone or it hears itself.
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

draw();
poll();
setInterval(poll, 900);
