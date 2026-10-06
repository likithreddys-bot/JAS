import cv2, numpy as np, sys
src, outdir = sys.argv[1], sys.argv[2]
img = cv2.imread(src); h, w = img.shape[:2]; print(w, h)
mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
# sure background: outer border strip, but bottom edge is the shirt
mask[:, :12] = cv2.GC_BGD; mask[:, -12:] = cv2.GC_BGD; mask[:12, :] = cv2.GC_BGD
# sure foreground: face/neck/chest core
cv2.ellipse(mask, (465, 450), (150, 210), 0, 0, 360, cv2.GC_FGD, -1)
cv2.rectangle(mask, (200, 820), (730, h-1), cv2.GC_FGD, -1)
cv2.ellipse(mask, (460, 230), (200, 110), 0, 0, 360, cv2.GC_PR_FGD, -1)
bgd, fgd = np.zeros((1,65)), np.zeros((1,65))
cv2.grabCut(img, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
fg = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
fg = (lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9,9),np.uint8))
alpha = cv2.GaussianBlur(fg.astype(np.float32), (5,5), 0)
# depth: body base + head dome + nose
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
body = cv2.GaussianBlur(fg.astype(np.float32), (0,0), 25) * 0.45
head = np.exp(-(((xx-462)/210)**2 + ((yy-400)/260)**2) * 1.6) * 0.5
nose = np.exp(-(((xx-465)/45)**2 + ((yy-470)/60)**2)) * 0.12
chest = np.exp(-(((xx-465)/330)**2 + ((yy-1000)/260)**2)) * 0.15
depth = np.clip((body + head * fg + nose + chest * fg) * fg, 0, 1)
depth = cv2.GaussianBlur(depth, (0,0), 6)
s = 760 / w; W, H = 760, int(h * s)
rgba = np.dstack([img, (alpha*255).astype(np.uint8)])
rgba = cv2.resize(rgba, (W, H), interpolation=cv2.INTER_AREA)
d8 = cv2.resize((depth/depth.max()*255).astype(np.uint8), (W, H), interpolation=cv2.INTER_AREA)
cv2.imwrite(f'{outdir}/likith-anime.webp', rgba, [cv2.IMWRITE_WEBP_QUALITY, 90])
cv2.imwrite(f'{outdir}/likith-anime-depth.png', d8)
prev = rgba.astype(np.float32); a = prev[...,3:]/255
cv2.imwrite(f'{outdir}/anime-preview.png', np.hstack([(prev[...,:3]*a + np.array([40,160,40])*(1-a)).astype(np.uint8), cv2.cvtColor(d8, cv2.COLOR_GRAY2BGR)]))
print(W, H)
