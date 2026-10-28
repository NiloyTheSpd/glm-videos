"""Build docs/cover.jpg: the README's wide style mosaic, re-skinned for GLM-Videos.

The upstream cover was a contact sheet of every style frame with an OPUSCAR wordmark.
Here the tiles are the same kind of asset (docs/frames/<slug>.jpg, one per style) and the
wordmark is GLM-Videos in the Z.ai palette, with the Zhipu mascot standing on it.

    python3 docs/mascot/make-cover.py
"""

import glob
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRAMES = os.path.join(ROOT, 'docs', 'frames')
OUT = os.path.join(ROOT, 'docs', 'cover.jpg')

W, H = 4868, 696          # keep upstream's 7:1 so the README layout does not shift
COLS = 24
ROWS = 2
TW = W // COLS
TH = H // ROWS

INK = (45, 45, 45)
ZAI = (31, 99, 236)
ZAI_D = (24, 73, 200)
WHITE = (255, 255, 255)
MUTED = (155, 147, 168)


def tiles():
    """One tile per style frame, ordered by slug."""
    frames = sorted(glob.glob(os.path.join(FRAMES, '*.jpg')))
    return frames[:COLS * ROWS]


def cover_crop(im, w, h):
    """Centre-crop to the tile aspect."""
    ta, ia = w / h, im.width / im.height
    if ia > ta:
        nw = int(im.height * ta)
        im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / ta)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    return im.resize((w, h), Image.LANCZOS)


def font(size, bold=False):
    """A bold or regular sans, whichever the system has. Falls back to PIL's default."""
    patterns = (
        '/usr/share/fonts/**/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/**/DejaVuSans.ttf',
        '/usr/share/fonts/**/*Sans*Bold*.ttf' if bold else '/usr/share/fonts/**/*Sans-Regular*.ttf',
        '/usr/share/fonts/**/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/**/LiberationSans-Regular.ttf',
    )
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            try:
                return ImageFont.truetype(hits[0], size)
            except OSError:
                continue
    return ImageFont.load_default()


def z_emblem(d, x, y, s):
    """The Z.ai mark: a top bar, a diagonal, a bottom bar. s is the bar thickness."""
    w = 10 * s          # overall width
    h = 15 * s          # overall height
    d.rectangle([x, y, x + w, y + s], fill=WHITE)                      # top bar
    d.polygon([(x + w - s, y), (x + w, y),
               (x + s, y + h - s), (x, y + h - s)], fill=WHITE)         # diagonal
    d.rectangle([x, y + h - s, x + w, y + h], fill=WHITE)              # bottom bar


def build():
    frames = tiles()
    if not frames:
        raise SystemExit('no frames in %s' % FRAMES)

    canvas = Image.new('RGB', (W, H), (10, 9, 13))
    for i, path in enumerate(frames):
        im = cover_crop(Image.open(path).convert('RGB'), TW, TH)
        canvas.paste(im, ((i % COLS) * TW, (i // COLS) * TH))

    d = ImageDraw.Draw(canvas)

    # the wordmark plate: a charcoal slab on the last four tiles, in the Z.ai palette
    px = W - TW * 4
    d.rectangle([px, 0, W, H], fill=INK)

    # mascot: the tile body is a shade lighter than the plate so it reads as a figure
    cx = px + TW // 2
    cy = H // 2
    body = (74, 74, 78)
    d.rounded_rectangle([cx - 78, cy - 112, cx + 78, cy + 100], radius=24, fill=body)
    d.ellipse([cx - 20, cy - 74, cx - 3, cy - 38], fill=WHITE)
    d.ellipse([cx + 3, cy - 74, cx + 20, cy - 38], fill=WHITE)
    d.ellipse([cx - 13, cy - 63, cx - 5, cy - 48], fill=ZAI)
    d.ellipse([cx + 5, cy - 63, cx + 13, cy - 48], fill=ZAI)
    d.arc([cx - 34, cy - 30, cx + 34, cy + 22], start=15, end=165, fill=WHITE, width=7)
    z_emblem(d, cx - 16, cy + 30, 3.2)
    # antenna
    d.rectangle([cx - 6, cy - 146, cx + 6, cy - 106], fill=ZAI_D)
    d.ellipse([cx - 18, cy - 162, cx + 18, cy - 126], fill=ZAI)
    d.ellipse([cx - 9, cy - 156, cx - 2, cy - 149], fill=WHITE)
    # feet
    d.rounded_rectangle([cx - 62, cy + 96, cx - 22, cy + 126], radius=12, fill=ZAI_D)
    d.rounded_rectangle([cx + 22, cy + 96, cx + 62, cy + 126], radius=12, fill=ZAI_D)

    # wordmark: sized to fit the plate exactly
    tx = px + TW + 34
    avail = W - tx - 40
    fm = font(104, bold=True)
    while d.textlength('GLM-VIDEOS', font=fm) > avail and fm.size > 40:
        fm = font(fm.size - 4, bold=True)
    d.text((tx, cy - 108), 'GLM-VIDEOS', font=fm, fill=WHITE)
    fs = font(38)
    while d.textlength('98 STYLES  ·  MADE IN CODE', font=fs) > avail and fs.size > 16:
        fs = font(fs.size - 2)
    d.text((tx + 4, cy - 6), '98 STYLES  ·  MADE IN CODE', font=fs, fill=ZAI)
    fu = font(30)
    while d.textlength('NiloyTheSpd.github.io/glm-videos', font=fu) > avail and fu.size > 14:
        fu = font(fu.size - 2)
    d.text((tx + 4, cy + 56), 'NiloyTheSpd.github.io/glm-videos', font=fu, fill=MUTED)

    canvas.save(OUT, quality=88, optimize=True)
    print('%s ← %d frames' % (OUT, len(frames)))


if __name__ == '__main__':
    build()
