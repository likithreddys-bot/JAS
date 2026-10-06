import cv2, numpy as np, sys
src, out = sys.argv[1], sys.argv[2]
img = cv2.imread(src)  # BGR
h, w = img.shape[:2]

# 1) background mask: wall is bright & low-saturation; flood from border
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
bg = ((hsv[...,2] > 150) & (hsv[...,1] < 70)).astype(np.uint8)
n, lab = cv2.connectedComponents(bg)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:,0], lab[:,-1]])))
bgm = np.isin(lab, [l for l in border if l != 0] ).astype(np.uint8)
fg = 1 - bgm
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15,15),np.uint8))
# keep largest component, fill holes
n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
big = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]); fg = (lab == big).astype(np.uint8)
inv = 1 - fg; n, lab = cv2.connectedComponents(inv)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:,0], lab[:,-1]])))
fg = (~np.isin(lab, list(border))).astype(np.uint8) | fg
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5,5),np.uint8))
fg = cv2.erode(fg, np.ones((7,7),np.uint8))
alpha = cv2.GaussianBlur(fg.astype(np.float32), (5,5), 0)

# 2) caricature warp: magnify head with smooth falloff
cx, cy, R, k = 575, 400, 470, 0.33
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
dx, dy = xx - cx, yy - cy; r = np.sqrt(dx*dx + dy*dy) / R
f = np.where(r < 1, 1 - k * (1 - r**2)**2, 1.0).astype(np.float32)
mapx, mapy = cx + dx * f, cy + dy * f
# shrink shoulders a bit toward centre for big-head look
below = np.clip((yy - 650) / 500, 0, 1)
mapx = cx + (mapx - cx) * (1 + 0.18 * below)
img = cv2.remap(img, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
alpha = cv2.remap(alpha, mapx, mapy, cv2.INTER_LINEAR, borderValue=0)

# 3) cel shading: smooth, quantize in Lab, ink lines
sm = img.copy()
for _ in range(5): sm = cv2.bilateralFilter(sm, 9, 35, 7)
labi = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
mask_idx = alpha.reshape(-1) > 0.5
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
_, lbl, ctr = cv2.kmeans(labi[mask_idx], 13, None, crit, 4, cv2.KMEANS_PP_CENTERS)
q = labi.copy(); q[mask_idx] = ctr[lbl.flatten()]
q = cv2.cvtColor(q.reshape(h, w, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)
q = cv2.medianBlur(q, 5)
# punch up: saturation & warmth
qh = cv2.cvtColor(q, cv2.COLOR_BGR2HSV).astype(np.float32)
qh[...,1] = np.clip(qh[...,1] * 1.12, 0, 255); qh[...,2] = np.clip(qh[...,2] * 1.06 + 6, 0, 255)
q = cv2.cvtColor(qh.astype(np.uint8), cv2.COLOR_HSV2BGR)
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); g = cv2.medianBlur(g, 5)
edges = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 6)
inkm = (edges < 128).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(inkm, connectivity=8)
keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 60
ink = keep[lab] & (alpha > 0.5)
q[ink] = (q[ink] * 0.18).astype(np.uint8)
# silhouette outline
a8 = (alpha > 0.5).astype(np.uint8)
outline = cv2.dilate(a8, np.ones((9,9),np.uint8)) - a8
rgba = np.dstack([q, (alpha * 255).astype(np.uint8)])
rgba[outline.astype(bool)] = (12, 10, 10, 255)
# crop to content
ys, xs = np.where(rgba[...,3] > 10)
y0, y1, x0, x1 = max(ys.min()-10,0), h, max(xs.min()-10,0), min(xs.max()+10,w)
rgba = rgba[y0:y1, x0:x1]
real = np.dstack([img, (alpha*255).astype(np.uint8)])[y0:y1, x0:x1]
s = 760 / rgba.shape[1]
rgba = cv2.resize(rgba, (760, int(rgba.shape[0]*s)), interpolation=cv2.INTER_AREA)
cv2.imwrite(out, rgba, [cv2.IMWRITE_WEBP_QUALITY, 88])
real = cv2.resize(real, (760, rgba.shape[0]), interpolation=cv2.INTER_AREA)
cv2.imwrite(out.replace('.webp','-real.webp'), real, [cv2.IMWRITE_WEBP_QUALITY, 85])
prev = rgba.copy().astype(np.float32); a = prev[...,3:]/255
bgc = np.array([16,11,10], np.float32)
cv2.imwrite(out.replace('.webp','-preview.png'), (prev[...,:3]*a + bgc*(1-a)).astype(np.uint8))
print(rgba.shape)
