#!/usr/bin/env python3
"""VOX-style paper-cut ski loop: 5 stills -> stop-motion loop (GIF + MP4).

Usage:
  python make_loop.py --frames frames/        # frames/01.png ... 05.png
  python make_loop.py --demo                  # synthetic placeholder frames
"""
import argparse, math, random, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 720, 1280
BRANDS = [  # (label, category, (x, y) as fraction of canvas, tilt deg, paper colour)
    ("ONYONE",   "WEAR",  (0.30, 0.10), -4, (236, 232, 220)),
    ("MARKER",   "HELMET", (0.70, 0.22),  5, (120, 190, 200)),
    ("GABEL",    "POLES", (0.28, 0.46), -6, (226, 120, 110)),
    ("VOLKL",    "SKI",   (0.72, 0.70),  4, (236, 232, 220)),
    ("DALBELLO", "BOOTS", (0.34, 0.88), -3, (150, 140, 200)),
]
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def torn_poly(cx, cy, w, h, rng, rough=5, step=14):
    """Rectangle outline with ripped (noisy) edges, as a point list."""
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    pts = []
    for x in np.arange(x0, x1, step): pts.append((x, y0 + rng.uniform(-rough, rough)))
    for y in np.arange(y0, y1, step): pts.append((x1 + rng.uniform(-rough, rough), y))
    for x in np.arange(x1, x0, -step): pts.append((x, y1 + rng.uniform(-rough, rough)))
    for y in np.arange(y1, y0, -step): pts.append((x0 + rng.uniform(-rough, rough), y))
    return pts


def torn_label(text, cat, color, seed):
    """Torn-paper brand tag with a white fibre rim and soft shadow (RGBA)."""
    rng = random.Random(seed)
    f, fs = font(54), font(20)
    tw = int(f.getlength(text)) + 70
    th = 130
    pad = 24
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    cx, cy = img.width / 2, img.height / 2
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon(torn_poly(cx + 6, cy + 8, tw, th, rng), fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(img)
    d.polygon(torn_poly(cx, cy, tw + 8, th + 8, rng, rough=6), fill=(250, 248, 240, 255))  # fibre rim
    d.polygon(torn_poly(cx, cy, tw, th, rng, rough=4), fill=color + (255,))
    ink = (28, 30, 60, 255)
    d.text((cx, cy - 22), cat, font=fs, fill=ink, anchor="mm")
    d.text((cx, cy + 14), text, font=f, fill=ink, anchor="mm")
    return img


def grain_texture(rng):
    """Horizontal paper-fibre grain, tiled to canvas size, values around 1.0."""
    n = rng.normal(0, 1, (H, W)).astype(np.float32)
    im = Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8))
    im = im.resize((W // 6, H)).resize((W, H), Image.BILINEAR)  # stretch -> horizontal fibres
    g = np.asarray(im, dtype=np.float32) / 255.0
    return 1.0 + (g - 0.5) * 0.22


def apply_grain(img, grain):
    a = np.asarray(img.convert("RGB"), dtype=np.float32) * grain[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def jitter(img, rng, amp=3, rot=0.5):
    """Stop-motion 'boil': small random shift/rotation each displayed frame."""
    return img.rotate(rng.uniform(-rot, rot), resample=Image.BICUBIC,
                      translate=(rng.randint(-amp, amp), rng.randint(-amp, amp)),
                      fillcolor=(14, 16, 28))


def demo_frames(out):
    """Placeholder torn-paper skier in 5 turn poses (replace with generated art)."""
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    leans = [-28, -12, 0, 12, 28]
    for i, lean in enumerate(leans, 1):
        im = Image.new("RGB", (W, H), (14, 16, 28))
        d = ImageDraw.Draw(im)
        for k, c in enumerate([(40, 70, 120), (90, 150, 170), (230, 232, 235)]):  # snow slope layers
            d.polygon(torn_poly(W / 2, H * (0.78 + k * 0.08), W * 1.1, 360, rng, rough=14, step=30), fill=c)
        sk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sk)
        cx, cy = W // 2 + lean * 3, int(H * 0.52)
        sd.polygon(torn_poly(cx, cy, 190, 300, rng, 7), fill=(100, 190, 200, 255))        # jacket
        sd.polygon(torn_poly(cx - 10, cy + 230, 130, 220, rng, 6), fill=(110, 90, 160, 255))  # legs
        sd.polygon(torn_poly(cx, cy - 210, 110, 120, rng, 5), fill=(235, 190, 160, 255))  # head
        sd.polygon(torn_poly(cx, cy - 250, 130, 60, rng, 5), fill=(226, 70, 60, 255))     # helmet
        sd.polygon(torn_poly(cx + lean * 2, cy + 380, 430, 26, rng, 4), fill=(230, 120, 110, 255))  # ski
        sk = sk.rotate(-lean * 0.6, center=(cx, cy + 200), resample=Image.BICUBIC)
        im.paste(sk, (0, 0), sk)
        im.save(out / f"{i:02d}.png")


def load_frames(folder):
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    if len(files) != 5:
        sys.exit(f"need exactly 5 images in {folder}, found {len(files)}")
    out = []
    for p in files:
        im = Image.open(p).convert("RGB")
        scale = max(W / im.width, H / im.height)  # cover-crop to 9:16
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2
        out.append(im.crop((l, t, l + W, t + H)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=Path, default=Path("frames"))
    ap.add_argument("--demo", action="store_true", help="generate placeholder frames first")
    ap.add_argument("--fps", type=int, default=8, help="stop-motion rate (poses per second)")
    ap.add_argument("--loops", type=int, default=6)
    ap.add_argument("--pingpong", action="store_true", help="1-2-3-4-5-4-3-2 instead of 1-2-3-4-5")
    ap.add_argument("--no-brands", action="store_true", help="skip Python brand overlay (art already has them)")
    ap.add_argument("--out", type=Path, default=Path("out"))
    a = ap.parse_args()

    if a.demo:
        demo_frames(a.frames)
    frames = load_frames(a.frames)
    order = list(range(5)) + (list(range(3, 0, -1)) if a.pingpong else [])
    rng = random.Random(1)
    grain = grain_texture(np.random.default_rng(3))
    labels = [torn_label(t, c, col, i) for i, (t, c, _, _, col) in enumerate(BRANDS)]

    out_frames, tick = [], 0
    for _ in range(a.loops):
        for idx in order:
            base = frames[idx].copy()
            if not a.no_brands:
                for i, (_, _, (fx, fy), tilt, _) in enumerate(BRANDS):
                    appear = i * 2  # brands pop in one by one during the first cycle, then stay
                    if tick < appear:
                        continue
                    lab = labels[i].rotate(tilt + rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, expand=True)
                    pop = min(1.0, 0.6 + 0.2 * (tick - appear))
                    if pop < 1.0:
                        lab = lab.resize((int(lab.width * pop), int(lab.height * pop)), Image.BICUBIC)
                    base.paste(lab, (int(fx * W - lab.width / 2) + rng.randint(-2, 2),
                                     int(fy * H - lab.height / 2) + rng.randint(-2, 2)), lab)
            out_frames.append(apply_grain(jitter(base, rng), grain))
            tick += 1

    a.out.mkdir(parents=True, exist_ok=True)
    dur = round(1000 / a.fps)
    out_frames[0].save(a.out / "ski_loop.gif", save_all=True, append_images=out_frames[1:],
                       duration=dur, loop=0, optimize=True)
    tmp = a.out / "_f"
    tmp.mkdir(exist_ok=True)
    for i, f in enumerate(out_frames):
        f.save(tmp / f"{i:04d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(tmp / "%04d.png"),
                    "-vf", "fps=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(a.out / "ski_loop.mp4")], check=True)
    for p in tmp.iterdir(): p.unlink()
    tmp.rmdir()
    print(f"{len(out_frames)} frames -> {a.out}/ski_loop.gif, ski_loop.mp4")


if __name__ == "__main__":
    main()
