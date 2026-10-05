/* The ensō: Luffy's face, a Zen brush circle drawn as bristle dabs.
 *
 * strokeDabs() is mirrored in app/lockart.py (enso_dabs) — same LCG, same order of draws — so the
 * website and the real Windows lock screen draw the identical stroke. Change both or neither. */

/** One bristle dab: angle, radius factor, dab size (fraction of canvas), alpha, progress 0-1. */
export type Dab = [number, number, number, number, number];

export function strokeDabs(seed = 7): Dab[] {
  let s = seed >>> 0;
  const rnd = () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0), s / 4294967296);
  const steps = 520, bristles = 26, start = -Math.PI * 0.58, sweep = Math.PI * 1.86;
  const wob = [rnd() * 6, rnd() * 6, rnd() * 6];
  const dry = Array.from({ length: bristles }, () => 0.55 + rnd() * 0.45); // where each bristle runs dry
  const dabs: Dab[] = [];
  for (let i = 0; i < steps; i++) {
    const u = i / (steps - 1), a = start + u * sweep;
    // heavy press at the start, thinning and lifting at the end
    const press = Math.min(1, u * 14) * (1 - Math.pow(u, 2.4) * 0.82);
    const w = 0.085 * press + 0.012;
    const rr = 1 + 0.018 * Math.sin(a * 2 + wob[0]) + 0.01 * Math.sin(a * 5 + wob[1]);
    for (let b = 0; b < bristles; b++) {
      if (u > dry[b] && rnd() < (u - dry[b]) * 5) continue; // dry-brush streaks
      const off = (b / (bristles - 1) - 0.5) * w * 2;
      const alpha = (0.55 + rnd() * 0.45) * (u > 0.9 ? 1 - (u - 0.9) * 6 : 1);
      dabs.push([a, rr + off, 0.0042 + rnd() * 0.0035, Math.max(0, alpha), u]);
    }
  }
  return dabs;
}

export const DABS = strokeDabs(7);

/** Paint the stroke up to `upto` (0-1) into a square canvas context of side `size`. */
export function paintEnso(ctx: CanvasRenderingContext2D, size: number, color: string, upto = 1) {
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = color;
  const c = size / 2, rad = size * 0.34;
  for (const [a, r, d, al, u] of DABS) {
    if (u > upto) break;
    ctx.globalAlpha = al;
    ctx.beginPath();
    ctx.arc(c + Math.cos(a) * rad * r, c + Math.sin(a) * rad * r, d * size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

/** Paint only dabs [from, to) on top of what is already there: for drawing the stroke in, a few
 *  hundred dabs per frame instead of repainting all of them. Returns `to`. */
export function paintEnsoRange(ctx: CanvasRenderingContext2D, size: number, color: string, from: number, to: number) {
  ctx.fillStyle = color;
  const c = size / 2, rad = size * 0.34;
  const end = Math.min(to, DABS.length);
  for (let i = from; i < end; i++) {
    const [a, r, d, al] = DABS[i];
    ctx.globalAlpha = al;
    ctx.beginPath();
    ctx.arc(c + Math.cos(a) * rad * r, c + Math.sin(a) * rad * r, d * size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  return end;
}
