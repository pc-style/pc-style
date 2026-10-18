"""Render the dithered aurora from pcstyle.dev as a sprite sheet of frames.

Port of the Aurora class in homepage/src/components/Dither.astro, minus the
pointer and ripples. Runs locally (numpy + Pillow); the result is committed as
assets/aurora.png and profile.py animates it by stepping through the frames.

Usage: python3 scripts/aurora.py assets/aurora.png
"""

import sys

import numpy as np
from PIL import Image

W, H = 448, 190  # cells; one cell is 2px in the 896px header
FRAMES = 24
T0, SPAN = 11.0, 4.0  # seconds of the site's animation, played forward then back

CURTAINS, HEIGHT, SPREAD, SWAY, TURB = 5, 0.5, 0.08, 1.1, 0.6
RAYS, LENGTH, GLOW, INTENSITY, SHIMMER, DRIFT = 14, 0.55, 0.9, 0.95, 0.2, 0.35

B8 = [0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
      3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21]
TH = (np.array(B8, dtype=float).reshape(8, 8) + 0.5) / 64


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def mix(a, b, t):
    return a + (b - a) * t


PAPER, INK, TINT, DIM, WHITE = (hexrgb(c) for c in ("#0a0a0b", "#e45aa3", "#9d5cff", "#2a1a4d", "#ffffff"))
PALETTE = [PAPER, mix(DIM, PAPER, 0.1), mix(DIM, TINT, 0.38), mix(TINT, DIM, 0.12), mix(INK, PAPER, 0.06), mix(INK, WHITE, 0.65)]
N = len(PALETTE) - 1

glow_r, below_r = max(1.2, H * 0.012), max(1, H * 0.008)
GLOW_LUT = np.exp(-np.arange(int(np.ceil(glow_r * 6)) + 1) / glow_r)
BELOW_LUT = np.exp(-np.arange(int(np.ceil(below_r * 5)) + 1) / below_r)
RAY_LUTS = []
for c in range(CURTAINS):
    length = max(3, H * LENGTH * 0.36 * (1 + 0.2 * c))
    i = np.arange(int(np.ceil(length * 3.2)) + 1)
    RAY_LUTS.append(np.exp(-i / length) * (1 - 0.55 * np.exp(-i / 2)))

# fixed stars in the upper sky, same generator as the site
STARS = []
seed = 7
for _ in range(round(W * H / 420)):
    seed = seed * 16807 % 2147483647
    sx = seed % W
    seed = seed * 16807 % 2147483647
    sy = seed % max(1, int(H * 0.42))
    seed = seed * 16807 % 2147483647
    STARS.append((sy, sx, (seed % 628) / 100))


def draw(t):
    x = np.arange(W)
    un = x / W * 6.2 + t * DRIFT * 0.05
    col = np.zeros((H, W))
    sin = np.sin
    for i in range(CURTAINS):
        base = HEIGHT + i * SPREAD
        s = SWAY * (0.07 * sin(un * 0.85 + t * 0.11 + i * 1.9) + 0.035 * sin(un * 2.1 - t * 0.17 + i * 0.7))
        tb = TURB * (0.009 * sin(un * 8.5 + t * 0.8 + i * 2.1) + 0.005 * sin(un * 17 - t * 1.1 + i))
        er = np.floor((1 - (base + s + tb)) * H).astype(int)
        env = 0.5 + 0.5 * sin(un * 0.62 + i * 2.4 + t * 0.05)
        env = 0.22 + 0.78 * env * env * (3 - 2 * env)
        rp = un * RAYS + sin(un * 1.6 + t * 0.2 + i) * 1.6 + t * 0.12 * (1 if i % 2 else -1)
        r1, r2 = 0.5 + 0.5 * sin(rp), 0.5 + 0.5 * sin(rp * 2.3 + 1.3 + t * 0.3)
        ray = 0.08 + 0.92 * (r1 ** 4 * 0.7 + r2 ** 2 * 0.3)
        shim = 1 - SHIMMER * (0.5 + 0.5 * sin(un * 4 - t * 1.4 + i * 1.3))
        amp = INTENSITY * 0.66 ** i * env * shim
        g_a, r_a = GLOW * amp, ray * 0.7 * amp
        for dy in range(1, len(BELOW_LUT)):
            y = er + dy
            m = (y >= 0) & (y < H)
            col[y[m], x[m]] += g_a[m] * BELOW_LUT[dy]
        for dy, rv in enumerate(RAY_LUTS[i]):
            y = er - dy
            m = (y >= 0) & (y < H)
            col[y[m], x[m]] += r_a[m] * rv + (g_a[m] * GLOW_LUT[dy] if dy < len(GLOW_LUT) else 0)

    v = (1 - np.exp(-2 * col)) * N
    lv = np.floor(v).astype(int)
    th = np.tile(TH, (H // 8 + 1, W // 8 + 1))[:H, :W]
    lv += (v - lv) > th
    lv = np.clip(lv, 0, N)
    lv[col <= 0.004] = 0
    for sy, sx, ph in STARS:
        if lv[sy, sx] == 0:
            tw = np.sin(t * 0.7 + ph * 3)
            if tw > 0.2:
                lv[sy, sx] = N if tw > 0.92 else 1
    return lv.astype(np.uint8)


def main():
    # ease in and out at both ends so the forward/back loop never jerks
    k = np.arange(FRAMES) / (FRAMES - 1)
    times = T0 + SPAN * (1 - np.cos(np.pi * k)) / 2
    sheet = np.concatenate([draw(t) for t in times])
    img = Image.fromarray(sheet, mode="P")
    img.putpalette([int(c) for rgb in PALETTE for c in rgb])
    img.info["transparency"] = 0
    img.save(sys.argv[1], optimize=True, bits=4, transparency=0)
    print(f"{FRAMES} frames of {W}x{H} -> {sys.argv[1]}")


if __name__ == "__main__":
    main()
