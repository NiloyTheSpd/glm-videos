"""Re-skin the 98 GLM-Videos stylebook frames: the old Clawd becomes the new Zhipu.

Upstream's GLM-Videos 98 feature starred a terracotta box character ("the Clawd") in
every one of its 98 style frames. This fork's mascot is Zhipu: the same box silhouette,
but in Z.ai's charcoal, white and signal blue, with round white eyes and a smile.

Each frame is re-skinned:
  1. find the Clawd's face (its two eyes) in the frame,
  2. erase it and restore the film behind it (inpaint from the surrounding pixels),
  3. composite the Zhipu sprite in its place, matched to the Clawd's size and position,
  4. re-apply the film's own grain/grade over the whole frame, so the mascot sits inside
     the film's look rather than on top of it.

    python3 docs/mascot/reskin-frames.py            # all 98
    python3 docs/mascot/reskin-frames.py 42 55      # only these
"""

import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRAMES = os.path.join(ROOT, 'styleboard', 'img', 'glm98')
SPRITE = os.path.join(ROOT, 'docs', 'mascot', 'zhipu-flat.svg')
TMP = '/tmp/zhipu-sprite.png'

# How much of the frame the mascot may take up, so a big sky does not become a mascot.
MIN_BODY_PX = 1500

# The Clawd is the only warm, saturated orange in these films, and its eyes are the
# only pair of twin dark marks standing on that orange.
EYE_HUE_LO, EYE_HUE_HI = 5, 35
EYE_SAT_MIN = 0.28
MIN_EYE_H = 9


# --------------------------------------------------------------------------- colour

def rgb2hsv(arr):
    """Hue (0-360), saturation and value for an RGB float array."""
    a = np.clip(arr / 255.0, 0, 1)
    mx = a.max(-1)
    mn = a.min(-1)
    d = mx - mn
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    idx = m & (mx == r)
    h[idx] = ((g - b)[idx] / d[idx]) % 6
    idx = m & (mx == g)
    h[idx] = ((b - r)[idx] / d[idx]) + 2
    idx = m & (mx == b)
    h[idx] = ((r - g)[idx] / d[idx]) + 4
    h *= 60.0
    s = np.zeros_like(mx)
    s[mx > 1e-6] = d[mx > 1e-6] / mx[mx > 1e-6]
    return h, s, mx


def warm_mask(arr):
    """The Clawd's terracotta: a warm, saturated orange."""
    h, s, _ = rgb2hsv(arr)
    return (h >= EYE_HUE_LO) & (h <= EYE_HUE_HI) & (s >= EYE_SAT_MIN)


# ---------------------------------------------------------------------- eye finding

def _cc_bars(arr, thr, er, amin, amax, hmin, wmax):
    """Dark blobs: the eyes, as connected components.

    Precise, but an eye that touches the body's outline merges with it and is lost.
    """
    g = arr.mean(-1)
    dark = g < thr
    if er:
        dark = ndimage.binary_erosion(dark, np.ones((er, er)))
    dark = ndimage.binary_opening(dark, np.ones((3, 3)))
    lab, n = ndimage.label(dark)
    out = []
    for i in range(1, n + 1):
        blob = lab == i
        a = int(blob.sum())
        if a < amin or a > amax:
            continue
        ys, xs = np.nonzero(blob)
        x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bh < hmin or bw > wmax or bh > wmax:
            continue
        if a / float(bw * bh) < 0.35:
            continue
        out.append((x0, y0, x1, y1, a))
    return out


def _row_runs(dark):
    """Every horizontal run of dark pixels, with the row it sits in."""
    runs = []
    h, w = dark.shape
    for y in range(h):
        row = dark[y]
        if not row.any():
            continue
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        for x0, x1 in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1):
            runs.append((y, int(x0), int(x1)))
    return runs


def _bars_from_runs(runs, min_w=3, max_w=44, gap=3):
    """Stack neighbouring rows' runs into vertical bars.

    A Clawd's eye is a vertical dark bar. When it overlaps other geometry it stops
    being its own component, but row by row it is still a run of dark columns.
    """
    byrow = {}
    for y, x0, x1 in runs:
        byrow.setdefault(y, []).append((x0, x1))
    active, out = [], []
    for y in sorted(byrow):
        rs = [(a, b) for a, b in byrow[y] if min_w <= b - a + 1 <= max_w]
        nxt = []
        for x0, x1, y0, _ in active:
            hit = None
            for a, b in rs:
                if a <= x1 + gap and b >= x0 - gap and min(b, x1) - max(a, x0) >= -2:
                    hit = (a, b)
                    break
            if hit is not None:
                rs.remove(hit)
                nxt.append((min(x0, hit[0]), max(x1, hit[1]), y0, y))
            else:
                out.append((x0, x1, y0, y))
        for a, b in rs:
            nxt.append((a, b, y, y))
        active = nxt
    out.extend(active)
    res = []
    for x0, x1, y0, y1 in out:
        bh = y1 - y0 + 1
        bw = x1 - x0 + 1
        if bh < MIN_EYE_H or bw > max_w:
            continue
        res.append((x0, y0, x1, y1, bw * bh))
    return res


def _twin_pairs(bars, width):
    """Two bars of the same size, at the same height, standing side by side.

    The eyes do not have to be identical -- in some styles one of them is
    partly in shadow, or the body is drawn in perspective -- so the match is
    generous on size and strict on position.
    """
    pairs = []
    for i in range(len(bars)):
        for j in range(i + 1, len(bars)):
            a, b = bars[i], bars[j]
            aw, ah = a[2] - a[0] + 1, a[3] - a[1] + 1
            bw, bh = b[2] - b[0] + 1, b[3] - b[1] + 1
            if abs(aw - bw) > max(4, aw * 0.75):
                continue
            if abs(ah - bh) > max(6, ah * 0.65):
                continue
            if abs((a[1] + a[3]) - (b[1] + b[3])) > max(10, ah * 0.60):
                continue
            if min(aw, ah) < 3:
                continue
            gap = abs(((a[0] + a[2]) - (b[0] + b[2])) / 2.0)
            if gap < max(8, aw * 0.9) or gap > width * 0.42:
                continue
            pairs.append((a, b, gap))
    return pairs


def _body_support(arr, a, b, hsv=None):
    """How much of the strip between and just below the eyes is the Clawd's orange.

    This is what separates a Clawd from any other pair of dark marks in the film:
    a real Clawd stands on its own warm colour, and nothing else in these films
    does.
    """
    if hsv is None:
        hsv = rgb2hsv(arr)
    h, s, _ = hsv
    height, width = arr.shape[:2]
    x0, x1 = min(a[0], b[0]), max(a[2], b[2])
    y0, y1 = min(a[1], b[1]), max(a[3], b[3])
    band = np.zeros((height, width), dtype=bool)
    band[max(0, y0):min(height, y1 + 1), max(0, x0):min(width, x1 + 1)] = True
    for e in (a, b):
        band[max(0, e[1] - 2):min(height, e[3] + 3), max(0, e[0] - 2):min(width, e[2] + 3)] = False
    warm = band & (h >= EYE_HUE_LO) & (h <= EYE_HUE_HI) & (s >= EYE_SAT_MIN)
    return float(warm.sum()) / max(1.0, band.sum()), int(band.sum())


# --------------------------------------------------------------- body proposals

# The Clawd's body is a flat fill of saturated orange. The grade moves it around
# (dim, dusty, hot) but it always stays in the same corner of the colour wheel,
# so a small ladder of saturation/value thresholds catches it in every style.
BODY_HSV = [
    (0.35, 0.50), (0.45, 0.35), (0.35, 0.35), (0.45, 0.20),
    (0.35, 0.20), (0.55, 0.20), (0.35, 0.62), (0.55, 0.35), (0.65, 0.30),
]

BODY_HUE_LO, BODY_HUE_HI = 0, 32
MIN_BODY_AREA = 700
BODY_AR_LO, BODY_AR_HI = 0.95, 4.5
BODY_FILL_MIN = 0.42
# A Clawd is a character in the shot, not the scenery: it never fills the frame,
# and it is never a sliver. These bounds keep a sunset or a sepia wall from
# being mistaken for the mascot.
BODY_MAX_W_FRAC = 0.52
BODY_MAX_H_FRAC = 0.62
BODY_MIN_W_FRAC = 0.045
BODY_MIN_H_FRAC = 0.055


def body_proposals(arr, hsv=None):
    """Boxes that could be the Clawd's body: wide, solid blocks of orange.

    A Clawd is a wide box standing on its own colour. The eye scan below is
    precise but blind in dim or sepia styles, so the body proposes and the eyes
    confirm.
    """
    if hsv is None:
        hsv = rgb2hsv(arr)
    h, s, v = hsv
    height, width = arr.shape[:2]
    out = []
    for smin, vmin in BODY_HSV:
        m = (h >= BODY_HUE_LO) & (h <= BODY_HUE_HI) & (s >= smin) & (v >= vmin)
        m = ndimage.binary_closing(m, np.ones((7, 7)))
        m = ndimage.binary_fill_holes(m)
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            comp = lab == i
            area = int(comp.sum())
            if area < MIN_BODY_AREA:
                continue
            ys, xs = np.nonzero(comp)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            if not (BODY_AR_LO <= bw / float(bh) <= BODY_AR_HI):
                continue
            if area / float(bw * bh) < BODY_FILL_MIN:
                continue
            # a Clawd is a character in the shot, not the scenery
            if bw > width * BODY_MAX_W_FRAC or bh > height * BODY_MAX_H_FRAC:
                continue
            if bw < width * BODY_MIN_W_FRAC or bh < height * BODY_MIN_H_FRAC:
                continue
            out.append(((x0, y0, x1, y1), area, (smin, vmin)))
    return _dedupe_proposals(out)


def _dedupe_proposals(props, iou=0.55):
    """Collapse proposals that describe the same blob across thresholds."""
    props.sort(key=lambda t: -t[1])
    keep = []
    for box, area, cfg in props:
        clash = False
        for kb, _, _ in keep:
            ix = max(0, min(box[2], kb[2]) - max(box[0], kb[0]) + 1)
            iy = max(0, min(box[3], kb[3]) - max(box[1], kb[1]) + 1)
            inter = ix * iy
            union = ((box[2] - box[0] + 1) * (box[3] - box[1] + 1)
                     + (kb[2] - kb[0] + 1) * (kb[3] - kb[1] + 1) - inter)
            if inter / float(max(1, union)) > iou:
                clash = True
                break
        if not clash:
            keep.append((box, area, cfg))
    return keep


# The Clawd is not always orange. Across the 98 styles its body is terracotta,
# salmon, tan or even a dusty blue, so the colour cannot be the primary signal.
# What is always true is that the body is a FLAT fill: one colour, held across
# a wide rectangle. Quantising the picture and looking for big blocks of a
# single quantised colour finds the body whatever colour the grade gave it.
FLAT_STEP = 26
FLAT_SCALE = 2
FLAT_MIN_AREA = 1100
FLAT_FILL_MIN = 0.52

PANEL_STEP = 26         # the colour quantisation used for the face panel

# The Clawd is the same character in all 98 styles, so the body can be worked
# out from the eyes alone. Measured across the stylebook: the pair of eyes
# spans about half the width of the body, the body is a little wider than it
# is tall, and the eyes sit about a fifth of the way down from the top.
EYE_SPAN_TO_BODY = 0.50
BODY_ASPECT = 1.55
EYE_TOP_TO_BODY = 0.18
WARM_SHARE_MIN = 0.30   # how much of the body must be the mascot's colour
BODY_COLOUR_TOL = 46    # how close a pixel must be to the mascot's own fill


def flat_proposals(arr):
    """Boxes that could be the Clawd's body: big blocks of one flat colour.

    The picture is quantised and looked for on a half-size copy -- the shape
    of the body is what matters, not the exact shade, and the half-size pass
    is several times quicker.
    """
    height, width = arr.shape[:2]
    scale = FLAT_SCALE
    small = ndimage.median_filter(arr[::scale, ::scale], size=(3, 3, 1))
    q = small.astype(np.int32) // FLAT_STEP
    key = q[:, :, 0] * 100 + q[:, :, 1] * 10 + q[:, :, 2]
    out = []
    for k in np.unique(key):
        m = ndimage.binary_closing(key == k, np.ones((3, 3)))
        m = ndimage.binary_fill_holes(m)
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            comp = lab == i
            area = int(comp.sum())
            if area < 150:                 # half-size pixels
                continue
            ys, xs = np.nonzero(comp)
            x0, x1 = int(xs.min()) * scale, int(xs.max()) * scale
            y0, y1 = int(ys.min()) * scale, int(ys.max()) * scale
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            if not (BODY_AR_LO <= bw / float(bh) <= BODY_AR_HI):
                continue
            sw, sh = int(xs.max()) - int(xs.min()) + 1, int(ys.max()) - int(ys.min()) + 1
            if area / float(sw * sh) < FLAT_FILL_MIN:
                continue
            if bw > width * BODY_MAX_W_FRAC or bh > height * BODY_MAX_H_FRAC:
                continue
            if bw < width * BODY_MIN_W_FRAC or bh < height * BODY_MIN_H_FRAC:
                continue
            out.append(((x0, y0, x1, y1), area * scale * scale, ('flat', int(k))))
    return _dedupe_proposals(out)


PANEL_MIN_AREA = 2500    # the smallest face panel worth looking at
PANEL_FILL_LO = 0.62     # the panel must be mostly one colour
PANEL_FILL_HI = 0.94     # ... but not a blank slab with nothing in it


def _quantise(arr):
    """The picture, reduced to one colour key per pixel."""
    q = arr.astype(np.int32) // PANEL_STEP
    return q[:, :, 0] * 100 + q[:, :, 1] * 10 + q[:, :, 2]


def panel_proposals(arr):
    """Boxes that could be the Clawd's face: a flat slab with two eyes in it.

    This is the Clawd's true shape -- one colour, held across a wide
    rectangle, with exactly two dark marks punched into it -- and it is the
    one thing the scenery never has. A window frame or a banner may well hold
    two dark marks side by side, but it is never a flat slab with nothing
    else in it.

    The picture is quantised and looked for on a half-size copy: the shape of
    the face is what matters, not the exact shade, and the half-size pass is
    several times quicker.
    """
    height, width = arr.shape[:2]
    scale = FLAT_SCALE
    small = ndimage.median_filter(arr[::scale, ::scale], size=(3, 3, 1))
    key = _quantise(small)
    out = []
    for k in np.unique(key):
        m = ndimage.binary_closing(key == k, np.ones((3, 3)))
        m = ndimage.binary_fill_holes(m)
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            comp = lab == i
            area = int(comp.sum())
            if area < PANEL_MIN_AREA // (scale * scale):
                continue
            ys, xs = np.nonzero(comp)
            x0, x1 = int(xs.min()) * scale, int(xs.max()) * scale
            y0, y1 = int(ys.min()) * scale, int(ys.max()) * scale
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            if not (BODY_AR_LO <= bw / float(bh) <= BODY_AR_HI):
                continue
            fill = area / float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
            if fill < PANEL_FILL_LO or fill > PANEL_FILL_HI:
                continue          # a blank slab has nothing punched into it
            if bw > width * BODY_MAX_W_FRAC or bh > height * BODY_MAX_H_FRAC:
                continue
            if bw < width * BODY_MIN_W_FRAC or bh < height * BODY_MIN_H_FRAC:
                continue
            out.append(((x0, y0, x1, y1), area * scale * scale, ('panel', int(k))))
    return _dedupe_proposals(out)


def eyes_in_box(arr, box, hsv=None):
    """The Clawd's eyes, read inside a known body box.

    The eyes are two marks punched into the body's own colour, side by side,
    the same size and the same height. Knowing where the body is removes all
    the guesswork.

    The marks are found by COLOUR DISTANCE from the body, not by how dark they
    are. That matters: in the warm, dim styles the eyes are only a little
    darker than the terracotta body, and they are often a different hue
    entirely -- dark green against orange, say. A test on brightness alone
    misses them, or finds the shadow under the brim instead.
    """
    if hsv is None:
        hsv = rgb2hsv(arr)
    x0, y0, x1, y1 = box
    height, width = arr.shape[:2]
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bw < 12 or bh < 12:
        return []

    # the face sits in the upper part of the body
    fy0 = max(0, y0)
    fy1 = min(height, y0 + int(bh * 0.62))
    sx0, sx1 = max(0, x0), min(width, x1 + 1)
    if fy0 >= fy1 or sx0 >= sx1:
        return []
    sub = arr[fy0:fy1, sx0:sx1]
    if sub.size == 0:
        return []

    # the body's own colour: the most common quantised colour in the face area
    ref = _modal_colour(sub)
    if ref is None:
        return []
    dist = np.abs(sub - ref).max(axis=2)

    cands = []
    for cut in (30, 42, 55, 70, 90, 110):
        off = dist > cut
        lab, n = ndimage.label(off)
        bars = []
        for i in range(1, n + 1):
            comp = lab == i
            a = int(comp.sum())
            if a < 10 or a > bw * bh * 0.30:
                continue
            ys, xs = np.nonzero(comp)
            ex0, ex1 = int(xs.min()) + sx0, int(xs.max()) + sx0
            ey0, ey1 = int(ys.min()) + fy0, int(ys.max()) + fy0
            ew, eh = ex1 - ex0 + 1, ey1 - ey0 + 1
            if eh < 4 or ew > bw * 0.40 or eh > bh * 0.7:
                continue
            if a / float(ew * eh) < 0.25:
                continue
            bars.append((ex0, ey0, ex1, ey1, a))
        for a, b, gap in _twin_pairs(bars, width):
            support = _strip_support(arr, a, b)
            if support < 0.35:
                continue
            if not panel_is_face(arr, a, b):
                continue
            eh = max(a[3] - a[1], b[3] - b[1]) + 1
            aw = min(a[2] - a[0], b[2] - b[0]) + 1
            shape = 1.0 if 0.4 <= eh / float(max(1, aw)) <= 8.0 else 0.8
            cands.append((round(support, 2) * shape, min(a[4], b[4]), eh, a, b))
    cands.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return cands


def _modal_colour(sub):
    """The most common quantised colour in a patch, as an RGB triple."""
    q = sub.astype(np.int32) // PANEL_STEP
    key = q[:, :, 0] * 100 + q[:, :, 1] * 10 + q[:, :, 2]
    vals, counts = np.unique(key, return_counts=True)
    dom_k = vals[counts.argmax()]
    return np.array([dom_k // 100, (dom_k // 10) % 10, dom_k % 10], dtype=np.float32) * PANEL_STEP + PANEL_STEP // 2


def _strip_support(arr, a, b):
    """How much of the strip between the eyes shares the body's own colour.

    The Clawd's face is one flat fill with two dark marks punched into it, so
    the strip between the eyes is the same colour as the body. This holds for
    every colour the mascot comes in, which is why it is compared with the
    surrounding body rather than with a fixed hue.
    """
    height, width = arr.shape[:2]
    x0, x1 = min(a[0], b[0]), max(a[2], b[2])
    y0, y1 = min(a[1], b[1]), max(a[3], b[3])
    band = np.zeros((height, width), dtype=bool)
    band[max(0, y0):min(height, y1 + 1), max(0, x0):min(width, x1 + 1)] = True
    for e in (a, b):
        band[max(0, e[1] - 2):min(height, e[3] + 3), max(0, e[0] - 2):min(width, e[2] + 3)] = False
    if not band.any():
        return 0.0
    strip = arr[band]
    # the body's own colour: the most common colour in the whole box
    body = arr[max(0, y0 - 40):min(height, y1 + 60), max(0, x0 - 40):min(width, x1 + 40)]
    if body.size == 0:
        return 0.0
    ref = np.median(body.reshape(-1, 3), axis=0)
    d = np.abs(strip - ref).max(axis=1)
    return float((d <= 34).sum()) / float(len(strip))


PANEL_TOL = 34          # how far a pixel may stray from the panel's colour
PANEL_MIN_FILL = 0.42   # how much of the panel must be one colour
PANEL_DARK_MAX = 0.42   # how much of the panel may be the eyes themselves


def _face_panel(arr, a, b):
    """The flat panel the two eyes are punched into.

    This is the Clawd's true signature, and the one thing the scenery never
    has: a large, single-colour area with exactly two small dark marks in it.
    A window frame, a banner or a suit in the background may well hold two
    dark marks side by side, but it is never one flat slab with nothing else
    in it.

    The panel is measured around the eyes themselves -- a little wider than
    the pair, and a little taller -- so the two eyes come out as holes in it.
    Its colour is the median of the patch rather than the most common
    quantised colour, because the body is usually lit from one side and its
    fill drifts a little across the face.

    Returns (fill, dark_share) for the panel that holds both eyes, or None.
    """
    height, width = arr.shape[:2]
    x0, x1 = min(a[0], b[0]), max(a[2], b[2])
    y0, y1 = min(a[1], b[1]), max(a[3], b[3])
    ew = max(1, x1 - x0 + 1)
    eh = max(1, y1 - y0 + 1)

    # the panel reaches a little beyond the eyes on every side: the face is
    # bigger than the pair of marks in it
    pad_x = max(4, int(ew * 0.20))
    pad_y = max(4, int(eh * 0.35))
    px0, px1 = max(0, x0 - pad_x), min(width, x1 + pad_x + 1)
    py0, py1 = max(0, y0 - pad_y), min(height, y1 + pad_y + 1)
    if px1 - px0 < 8 or py1 - py0 < 8:
        return None
    sub = arr[py0:py1, px0:px1]

    # the panel's colour: the median of the patch
    ref = np.median(sub.reshape(-1, 3), axis=0)
    d = np.abs(sub - ref).max(axis=2)
    within = d <= PANEL_TOL
    fill = float(within.sum()) / float(within.size)
    if fill < PANEL_MIN_FILL:
        return None
    dark_share = 1.0 - fill
    # the two eyes are holes in the panel, so the panel is mostly intact --
    # but how much of it the eyes take depends on how big the eyes are. A pair
    # of small eyes in a wide face leaves the panel nearly whole; a pair of
    # big eyes in a close-up takes a good deal of it.
    eye_area = ((a[2] - a[0] + 1) * (a[3] - a[1] + 1)
                + (b[2] - b[0] + 1) * (b[3] - b[1] + 1))
    panel_area = float(sub.shape[0] * sub.shape[1])
    expected = min(0.9, eye_area / max(1.0, panel_area))
    if dark_share > max(PANEL_DARK_MAX, expected * 1.9 + 0.10):
        return None
    return fill, dark_share


def panel_is_face(arr, a, b):
    """True when the two marks sit in a flat panel: the mascot's face."""
    p = _face_panel(arr, a, b)
    return p is not None


CC_LADDER = [
    dict(thr=100, er=3, amin=25, amax=2500, hmin=7, wmax=40),
    dict(thr=110, er=2, amin=18, amax=2500, hmin=6, wmax=44),
    dict(thr=120, er=0, amin=14, amax=2500, hmin=5, wmax=52),
    dict(thr=130, er=0, amin=10, amax=2500, hmin=4, wmax=60),
]
RUN_LADDER = [
    dict(thr=100, min_w=3, max_w=44),
    dict(thr=115, min_w=3, max_w=50),
    dict(thr=130, min_w=4, max_w=56),
]

# The Clawd's eyes are near-black vertical bars. Scanning for those directly --
# a dark blob that is taller than it is wide -- finds them in every style,
# including the ones where the body colour merges with the background.
BAR_CUTS = (45, 60, 80, 100, 120)
BAR_MIN_AREA = 12
BAR_MAX_AREA = 4000
BAR_MIN_H = 8
BAR_MAX_W = 90
BAR_MAX_H = 200
BAR_MIN_FILL = 0.30


def _dark_bars(grey, cut):
    """Dark blobs that are taller than they are wide: the shape of a Clawd's eye."""
    dark = grey < cut
    lab, n = ndimage.label(dark)
    out = []
    for i in range(1, n + 1):
        comp = lab == i
        a = int(comp.sum())
        if a < BAR_MIN_AREA or a > BAR_MAX_AREA:
            continue
        ys, xs = np.nonzero(comp)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bh < BAR_MIN_H or bw > BAR_MAX_W or bh > BAR_MAX_H:
            continue
        if a / float(bw * bh) < BAR_MIN_FILL:
            continue
        if bw > bh * 1.2:            # not a vertical bar
            continue
        out.append((x0, y0, x1, y1, a))
    return out


def _score(arr, a, b, hsv):
    """How good a look this is for a pair of Clawd eyes."""
    eh = max(a[3] - a[1], b[3] - b[1]) + 1
    if eh < MIN_EYE_H:
        return None
    aw = min(a[2] - a[0], b[2] - b[0]) + 1
    support, band = _body_support(arr, a, b, hsv)
    if band < 12 or support < 0.30:
        return None
    span = max(a[2], b[2]) - min(a[0], b[0]) + 1
    if span < eh * 1.2 or span > eh * 26:
        return None
    # a Clawd's eye is taller than it is wide
    shape = 1.0 if 1.2 <= eh / float(aw) <= 6.0 else 0.75
    return (round(support, 2) * shape, min(a[4], b[4]), eh)


def eye_pairs(arr):
    """Every plausible pair of Clawd eyes in the frame, best first.

    The scan is a direct one: find dark vertical bars, then look for twins --
    two bars of the same size at the same height, standing side by side, with
    the Clawd's orange between them.
    """
    height, width = arr.shape[:2]
    hsv = rgb2hsv(arr)
    grey = arr.mean(-1)
    cands = []
    for cut in BAR_CUTS:
        for a, b, _gap in _twin_pairs(_dark_bars(grey, cut), width):
            support, band = _body_support(arr, a, b, hsv)
            if band < 12 or support < 0.35:
                continue
            if not panel_is_face(arr, a, b):
                continue
            eh = max(a[3] - a[1], b[3] - b[1]) + 1
            aw = min(a[2] - a[0], b[2] - b[0]) + 1
            shape = 1.0 if 0.4 <= eh / float(max(1, aw)) <= 8.0 else 0.8
            cands.append(((round(support, 2) * shape, min(a[4], b[4]), eh), a, b))
    cands.sort(key=lambda t: (t[0][0], t[0][1]), reverse=True)
    return cands


def face_boxes(arr):
    """The Clawd's body rectangle.

    The eyes come first. A Clawd is a pair of dark vertical marks standing
    side by side, and nothing else in these films has that; the body is then
    found by growing the flat panel around them. Working from the eyes
    outwards is what makes the detector survive the styles where the mascot
    is salmon, tan or dusty blue, and the styles where it stands against a
    background of the same colour.

    Two routes, in order:

      1. eyes first -- a twin pair of dark marks, then the body grown from
         the flat panel they are punched into.
      2. body first -- a wide block of colour proposes where the Clawd is
         and its eyes are read inside that block. This catches the rare
         style where the eyes are too soft to be found on their own.

    Whatever the routes find is merged, and overlapping boxes are collapsed.
    """
    h, w = arr.shape[:2]
    hsv = rgb2hsv(arr)
    hue, sat, _ = hsv
    warm = (hue >= EYE_HUE_LO) & (hue <= EYE_HUE_HI) & (sat >= EYE_SAT_MIN)

    # ---- route 1: the eyes anchor, the body grows around them
    boxes = _bodies_from_eyes(arr, hsv, warm)
    out = filter_sizes(dedupe(boxes))
    if out:
        return out

    # ---- route 2: a block of colour proposes, the eyes confirm
    for box, area, _cfg in (panel_proposals(arr) + body_proposals(arr, hsv) + flat_proposals(arr)):
        found = eyes_in_box(arr, box, hsv)
        if not found:
            continue
        # the eyes must sit where the mascot's eyes sit, or the block is scenery
        if any(_eyes_fit_body(f[3], f[4], box) for f in found):
            boxes.append(box)

    out = filter_sizes(dedupe(boxes))
    if out:
        return out

    # ---- route 3: the body alone. In a few styles the Clawd wears something
    # over its eyes -- a diving mask, a helmet -- and the eyes cannot be read
    # at all. Its body is still a big block of its own colour, wide and solid,
    # and that on its own is enough to recognise it.
    for box, area, _cfg in body_proposals(arr, hsv):
        bw, bh = box[2] - box[0] + 1, box[3] - box[1] + 1
        if bw * bh < MIN_BODY_AREA * 4:
            continue
        if not (BODY_AR_LO <= bw / float(bh) <= BODY_AR_HI):
            continue
        if _warm_share(arr, box, warm) >= 0.55 and _body_in_frame(arr, box):
            boxes.append(box)
            break

    return filter_sizes(dedupe(boxes))


def _warm_share(arr, box, warm):
    """How much of a box is the mascot's own warm colour.

    The Clawd fills most of its own rectangle. A table, a wall or a window
    frame in the same warm colour fills only part of it, and that is what
    tells the two apart.
    """
    x0, y0, x1, y1 = box
    h, w = arr.shape[:2]
    bx0, by0 = max(0, x0), max(0, y0)
    bx1, by1 = min(w, x1), min(h, y1)
    if bx1 <= bx0 or by1 <= by0:
        return 0.0
    sub = warm[by0:by1, bx0:bx1]
    return float(sub.sum()) / float(sub.size)


def _bodies_from_eyes(arr, hsv, warm):
    """The body boxes that grow from the pairs of eyes found in the frame.

    The Clawd is the same character in all 98 styles, so the body is worked
    out from its proportions rather than from the colour around it: the pair
    of eyes spans about half the width of the body, and sits about a fifth of
    the way down from the top.

    Working this way is what keeps the detector honest. The Clawd's terracotta
    is the same colour as the walls and floors it stands in front of, so a
    body found by growing the colour outwards runs straight into the scenery
    and swallows the shot. The eyes do not have that problem: they are the one
    thing about the mascot that nothing in the background imitates.

    Every pair of eyes in the frame is given a body by those proportions, and
    the body that is most convincingly the mascot -- filled with its own
    colour, solid, inside the picture -- is the one that is kept.
    """
    h, w = arr.shape[:2]
    pairs = _distinct_pairs(eye_pairs(arr))
    best = None
    for sc, a, b in pairs:
        box = _body_from_pair(a, b)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw < 12 or bh < 12:
            continue
        # the body must stand in the picture. It may be cropped by the top of
        # the shot -- the Clawd is often close to the camera -- but it must not
        # run off the sides or the bottom, which is what a pair of marks in
        # the scenery does.
        if not _body_in_frame(arr, box, min_share=0.80, allow_top=True):
            continue
        # and it must be filled with the mascot's own colour: a Clawd is a
        # solid slab of terracotta, while a pair of eyes standing on a wall
        # leaves most of the rectangle to the wall
        fill = _warm_share(arr, box, warm)
        if fill < WARM_SHARE_MIN:
            continue
        # the eyes must actually be inside the body they gave
        if not _eyes_fit_body(a, b, box):
            continue
        # the body may fill a good part of the shot -- the Clawd is the
        # protagonist and sometimes stands close to the camera -- but it must
        # not be the whole frame, which would mean the eyes were read off a
        # piece of scenery
        if bw * bh > w * h * 0.45:
            continue
        # among the candidates that pass, the biggest body is the mascot: it
        # is a character standing in the shot, and a smaller pair of marks in
        # the same picture is scenery
        score = (bw * bh, fill)
        if best is None or score > best[0]:
            best = (score, box)
    if best is None:
        return []
    return [best[1]]


def _body_from_pair(a, b):
    """The body rectangle that a pair of eyes implies.

    The Clawd is the same character in all 98 styles, so its body is measured
    off its eyes: the pair spans about half the width of the body, the body is
    a little wider than it is tall, and the eyes sit about a fifth of the way
    down from the top.
    """
    ex0, ex1 = min(a[0], b[0]), max(a[2], b[2])
    ey0, ey1 = min(a[1], b[1]), max(a[3], b[3])
    span = ex1 - ex0 + 1
    if span < 4:
        return None
    bw = int(span / EYE_SPAN_TO_BODY)
    bh = int(bw / BODY_ASPECT)
    if bw < 12 or bh < 12:
        return None
    cx = (ex0 + ex1) / 2.0
    x0 = int(round(cx - bw / 2))
    y0 = int(round(ey0 - bh * EYE_TOP_TO_BODY))
    return (x0, y0, x0 + bw, y0 + bh)


def _body_in_frame(arr, box, min_share=0.55, allow_top=False):
    """Is the body inside the picture?

    The Clawd is a character standing in the shot: it is never bigger than the
    frame, and a body worked out from a pair of marks in the scenery often
    runs off the side, which is how it gives itself away.

    It may be cropped by the top of the frame, though. The Clawd is the
    protagonist, and the shots where it stands close to the camera cut its
    head off.
    """
    x0, y0, x1, y1 = box
    h, w = arr.shape[:2]
    bw, bh = max(1, x1 - x0 + 1), max(1, y1 - y0 + 1)
    if allow_top:
        # the top of the body may sit above the frame, but only a little
        over = max(0, -y0)
        if over > bh * 0.5:
            return False
        y0 = max(0, y0)
        bh = max(1, y1 - y0 + 1)
    inside = (max(0, min(w, x1) - max(0, x0)) * max(0, min(h, y1) - max(0, y0)))
    return inside / float(bw * bh) >= min_share


def _eyes_fit_body(a, b, box):
    """Do the eyes sit where the mascot's eyes sit?

    A Clawd's face is a wide slab: the eyes are in its upper half, they are
    roughly the same distance from the body's left and right edges, and the
    pair is not squeezed against one side. Scenery fails all three.

    The margins are generous, because a Clawd is often tilted: its body is
    turned, its hat is on, and the box that holds it is square to the frame
    rather than to the mascot.
    """
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bw < 12 or bh < 12:
        return False
    ex0, ex1 = min(a[0], b[0]), max(a[2], b[2])
    ey0, ey1 = min(a[1], b[1]), max(a[3], b[3])
    # the eyes are in the upper part of the body
    if not (-0.10 <= (ey0 - y0) / float(bh) <= 0.46):
        return False
    if not (-0.10 <= (ey1 - y0) / float(bh) <= 0.68):
        return False
    # the pair is not jammed against one edge
    left = (ex0 - x0) / float(bw)
    right = (x1 - ex1) / float(bw)
    if left < -0.02 or right < -0.02:
        return False
    # the eyes are not tiny specks and not the whole body
    if (ex1 - ex0 + 1) / float(bw) < 0.10:
        return False
    if (ey1 - ey0 + 1) / float(bh) > 0.80:
        return False
    return True


def _distinct_pairs(pairs, tol=0.6):
    """The eye pairs that are not just the same pair found again.

    One pair of eyes is found many times over -- at every darkness threshold,
    and for every slightly different blob boundary. Only the best of each
    cluster is kept, so one Clawd gives one pair.
    """
    out = []
    for sc, a, b in pairs:
        ex0, ex1 = min(a[0], b[0]), max(a[2], b[2])
        ey0, ey1 = min(a[1], b[1]), max(a[3], b[3])
        dup = False
        for osc, oa, ob in out:
            oex0, oex1 = min(oa[0], ob[0]), max(oa[2], ob[2])
            oey0, oey1 = min(oa[1], ob[1]), max(oa[3], ob[3])
            ix = max(0, min(ex1, oex1) - max(ex0, oex0) + 1)
            iy = max(0, min(ey1, oey1) - max(ey0, oey0) + 1)
            inter = ix * iy
            union = ((ex1 - ex0 + 1) * (ey1 - ey0 + 1)
                     + (oex1 - oex0 + 1) * (oey1 - oey0 + 1) - inter)
            if union > 0 and inter / float(union) > tol:
                dup = True
                break
        if not dup:
            out.append((sc, a, b))
    return out


def filter_sizes(boxes, min_rel=0.55, min_abs=2200):
    """Drop mascot-sized boxes that are much smaller than the main one.

    A frame has one Clawd, occasionally two of much the same size. A box well
    below the biggest one is the detector latching onto some other pair of
    marks, so it goes. The threshold is generous because a frame can really
    carry a second, smaller Clawd.
    """
    if not boxes:
        return []
    areas = [(b[2] - b[0] + 1) * (b[3] - b[1] + 1) for b in boxes]
    biggest = max(areas)
    out = []
    for b, a in zip(boxes, areas):
        if a < min_abs:
            continue
        if a < biggest * min_rel:
            continue
        out.append(b)
    return out


def dedupe(boxes, overlap=0.35):
    """Drop boxes that sit on top of each other, keeping the larger one.

    Two boxes clash when they overlap much, or when one sits inside the other:
    a panorama and the mascot standing in front of it describe the same thing.
    """
    out = []
    for x0, y0, x1, y1 in sorted(boxes, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        clash = False
        for k0, k1, k2, k3 in out:
            ix = max(0, min(x1, k2) - max(x0, k0) + 1)
            iy = max(0, min(y1, k3) - max(y0, k1) + 1)
            inter = ix * iy
            if inter > overlap * min(area, (k2 - k0 + 1) * (k3 - k1 + 1)):
                clash = True
                break
            # one box wholly inside the other: the smaller is the real mascot
            if inter >= 0.85 * area and area <= (k2 - k0 + 1) * (k3 - k1 + 1):
                clash = True
                break
        if not clash:
            out.append((x0, y0, x1, y1))
    return out


# ------------------------------------------------------------------- re-skinning

def sprite_rgba():
    """Render the Zhipu master to a transparent PNG, once."""
    if not os.path.exists(TMP):
        subprocess.run(['rsvg-convert', '-w', '520', '-h', '600', SPRITE, '-o', TMP], check=True)
    return Image.open(TMP).convert('RGBA')


def sprite_bounds(sprite):
    """The Zhipu's body within the sprite canvas.

    The drawing is more than the body: an antenna sticks up above it, arms
    reach out at the sides and feet hang below. The body is the wide slab in
    the middle, and it is the body that stands in for the Clawd's body, so it
    is the body that has to be lined up with the hole that was cleared.

    The slab is the run of rows that share the same, common width. The antenna
    is narrow, the arms are wider, the feet are narrow again.
    """
    a = np.asarray(sprite)[:, :, 3]
    height, width = a.shape[:2]
    opaque = a > 8
    spans = []
    for y in range(height):
        xs = np.nonzero(opaque[y])[0]
        spans.append((int(xs.min()), int(xs.max())) if len(xs) else None)

    widths = [s[1] - s[0] + 1 for s in spans if s is not None]
    if not widths:
        return (0, 0, width, height)
    counts = {}
    for x in widths:
        counts[x] = counts.get(x, 0) + 1
    slab_w = max(counts, key=lambda k: (counts[k], k))

    # the rows of the slab, and the rows of anything wider (the arms)
    body_rows = [y for y, s in enumerate(spans)
                 if s is not None and s[1] - s[0] + 1 == slab_w]
    if not body_rows:
        ys, xs = np.nonzero(opaque)
        return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    top, bot = body_rows[0], body_rows[-1]
    # the body is taller than it is wide by roughly the same amount as the
    # Clawd's; the rows between the antenna and the feet are all body
    return (spans[top][0], top, spans[bot][1], bot)


def sprite_eyes(sprite):
    """Where the Zhipu's eyes are, in the sprite canvas.

    The eyes are the blue pupils: two small blobs of a strong blue set in
    white. They are the one feature that lines up with the Clawd's own eyes,
    so they are what the two mascots are matched on.

    The feet are blue as well, so only the blue in the upper half of the body
    is counted.
    """
    a = np.asarray(sprite.convert('RGB')).astype(np.float32)
    alpha = np.asarray(sprite)[:, :, 3]
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    # a strong blue: much more blue than red
    blue = (b > 120) & (b > r + 45) & (alpha > 128)
    if not blue.any():
        return None
    body = sprite_bounds(sprite)
    top = body[1]
    mid = top + (body[3] - body[1]) * 0.55
    ys, xs = np.nonzero(blue)
    keep = (ys > top) & (ys < mid)
    ys, xs = ys[keep], xs[keep]
    if len(xs) == 0:
        return None
    # the middle of the pair, and the line they sit on
    return (float(xs.min() + xs.max()) / 2.0, float(ys.min() + ys.max()) / 2.0)


def fill_hole(arr, hole, iterations=400):
    """Fill a hole with the colours diffusing in from its rim.

    The diffusion is weighted by how close each known pixel is to the hole, so the
    fill comes from the film around the figure rather than smearing one edge across.

    Only the hole's own bounding box is touched: the figure covers a fraction of
    the frame, so there is no sense in diffusing the whole picture.
    """
    img = arr.astype(np.float32).copy()
    known = (~hole).astype(np.float32)
    ys, xs = np.nonzero(hole)
    if len(xs) == 0:
        return img
    pad = 4
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(arr.shape[0], int(ys.max()) + pad + 1)
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(arr.shape[1], int(xs.max()) + pad + 1)
    sub_img = img[y0:y1, x0:x1]
    sub_known = known[y0:y1, x0:x1]
    sub_hole = hole[y0:y1, x0:x1]
    for _ in range(iterations):
        up = np.roll(sub_img, 1, axis=0)
        dn = np.roll(sub_img, -1, axis=0)
        lf = np.roll(sub_img, 1, axis=1)
        rt = np.roll(sub_img, -1, axis=1)
        ku = np.roll(sub_known, 1, axis=0)[:, :, None]
        kd = np.roll(sub_known, -1, axis=0)[:, :, None]
        kl = np.roll(sub_known, 1, axis=1)[:, :, None]
        kr = np.roll(sub_known, -1, axis=1)[:, :, None]
        w = ku + kd + kl + kr
        avg = (up * ku + dn * kd + lf * kl + rt * kr) / np.maximum(w, 1e-6)
        sub_img = np.where(sub_hole[:, :, None] > 0, avg, sub_img)
        sub_known = np.maximum(sub_known, 1.0 - sub_hole)
    img[y0:y1, x0:x1] = sub_img
    return img


def grain_profile(arr, hole):
    """The film's own high-frequency texture, measured outside the hole.

    Used to put the film's grain back over the mascot, so it is not a clean sticker
    on a noisy picture. The 75th percentile of the local gradient is used, and the
    result is scaled down hard: a gradient magnitude is several times the size of
    a single grain step, so taking it as the sigma directly buries the picture.
    """
    gy = ndimage.sobel(arr.mean(-1), axis=0)
    gx = ndimage.sobel(arr.mean(-1), axis=1)
    g = np.hypot(gx, gy)
    outside = g[~hole]
    if outside.size == 0:
        return 0.0
    return float(np.percentile(outside, 75)) * 0.16


def reskin(path, sprite, out_path=None):
    im = Image.open(path).convert('RGB')
    arr = np.asarray(im).astype(np.float32)
    h, w = arr.shape[:2]

    found = face_boxes(arr)
    if not found:
        return 'no Clawd'

    dark = arr.mean(-1) < 90
    hue, sat, _ = rgb2hsv(arr)
    warm = (hue >= EYE_HUE_LO) & (hue <= EYE_HUE_HI) & (sat >= EYE_SAT_MIN)

    # The hole is the Clawd itself: its terracotta body, the dark outline that draws
    # it and its eyes. It is grown from the terracotta outwards, so the film's
    # background is never eaten.
    hole = np.zeros((h, w), dtype=bool)
    for x0, y0, x1, y1 in found:
        bx0, by0 = max(0, x0), max(0, y0)
        bx1, by1 = min(w, x1), min(h, y1)
        if bx1 <= bx0 or by1 <= by0:
            continue
        box = np.zeros((h, w), dtype=bool)
        box[by0:by1, bx0:bx1] = True
        terr = box & warm
        if not terr.any():
            continue
        # the mascot's own blob: the biggest block of terracotta in the box
        lab, n = ndimage.label(ndimage.binary_closing(terr, np.ones((9, 9))))
        best = None
        for i in range(1, n + 1):
            comp = lab == i
            ys, xs = np.nonzero(comp)
            if len(xs) == 0:
                continue
            area = int(comp.sum())
            if best is None or area > best[0]:
                best = (area, int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        if best is None:
            continue
        _, tx0, ty0, tx1, ty1 = best
        blob = np.zeros((h, w), dtype=bool)
        blob[ty0:ty1 + 1, tx0:tx1 + 1] = True
        terr = terr & blob

        # the outline: dark pixels right against the terracotta
        grown = ndimage.binary_dilation(terr, np.ones((5, 5)))
        rim = grown & ~ndimage.binary_erosion(terr, np.ones((5, 5)))
        piece = terr | (rim & dark)
        # the eyes: dark blobs well inside the body
        piece |= ndimage.binary_erosion(terr, np.ones((7, 7))) & dark
        # the hat and the limbs reach outside the terracotta; take the dark pixels
        # just above and below the body too
        piece |= (box & dark & ndimage.binary_dilation(terr, np.ones((15, 15))))
        hole |= piece
    hole = ndimage.binary_closing(hole, np.ones((5, 5)))
    hole = ndimage.binary_dilation(hole, np.ones((3, 3)))

    # 1. restore the film behind the Clawd
    canvas = fill_hole(arr, hole)

    # 2. a Zhipu for each Clawd, sized to the Clawd's actual body
    #
    # The size comes from the body rectangle, which is worked out from the
    # mascot's own eyes: the pair of eyes spans about half the width of the
    # body, so the body is twice the span of the eyes across.
    #
    # The placement is measured off the sprite rather than guessed. The
    # Zhipu's drawing sits inside its canvas with a margin, and that margin
    # has to be scaled along with the drawing, or the mascot drifts out of the
    # hole that was cleared for it.
    sb = sprite_bounds(sprite)
    sw, sh = sprite.size
    fx0, fy0, fx1, fy1 = sb
    # the Zhipu's eyes, as a fraction of its body: the eyes of the sprite are
    # the one feature that lines up with the Clawd's
    seye = sprite_eyes(sprite)
    for x0, y0, x1, y1 in found:
        bx0, by0 = max(0, x0), max(0, y0)
        bx1, by1 = min(w, x1), min(h, y1)
        if bx1 <= bx0 or by1 <= by0:
            continue
        body_w = bx1 - bx0 + 1
        body_h = by1 - by0 + 1
        if body_w * body_h < MIN_BODY_PX:
            continue

        # scale the whole sprite so its body matches the Clawd's body
        scale = body_w / float(max(1, fx1 - fx0))
        sp_w = max(8, min(w * 2, int(round(sw * scale))))
        sp_h = max(8, min(h * 2, int(round(sh * scale))))
        sp = sprite.resize((sp_w, sp_h), Image.LANCZOS)
        sp_arr = np.asarray(sp).astype(np.float32)
        alpha = (sp_arr[:, :, 3] / 255.0)[:, :, None]

        # the body of the sprite, now that it is scaled
        sbx0 = int(round(fx0 * scale))
        sby0 = int(round(fy0 * scale))
        sbx1 = int(round(fx1 * scale))
        sby1 = int(round(fy1 * scale))

        # line the two up by their eyes: the Zhipu's eyes sit a fixed way
        # down its body, and so do the Clawd's
        if seye is not None:
            ex, ey = seye
            eye_x = int(round(ex * scale))
            eye_y = int(round(ey * scale))
            # the Clawd's own eye line, a fifth of the way down its body
            claw_eye_x = (bx0 + bx1) / 2.0
            claw_eye_y = by0 + body_h * EYE_TOP_TO_BODY
            ox = int(round(claw_eye_x - eye_x))
            oy = int(round(claw_eye_y - eye_y))
        else:
            ox = int(bx0 - sbx0)
            oy = int(by0 - sby0)

        # the sprite may hang off the edge of the frame: clip it, and the
        # part of it that lands on the frame with it
        cx0 = max(0, ox)
        cy0 = max(0, oy)
        cx1 = min(w, ox + sp_w)
        cy1 = min(h, oy + sp_h)
        if cx1 <= cx0 or cy1 <= cy0:
            continue
        sub = alpha[cy0 - oy:cy1 - oy, cx0 - ox:cx1 - ox]
        rgb = sp_arr[cy0 - oy:cy1 - oy, cx0 - ox:cx1 - ox, :3]
        region = canvas[cy0:cy1, cx0:cx1]
        canvas[cy0:cy1, cx0:cx1] = region * (1 - sub) + rgb * sub

    # 3. the film's grain back over everything, so the mascot sits inside the look
    g = grain_profile(arr, hole)
    if g > 0.4:
        rng = np.random.default_rng(7)
        noise = rng.normal(0, g, size=(h, w, 1)).astype(np.float32)
        canvas = np.clip(canvas + noise, 0, 255)

    out = Image.fromarray(canvas.astype(np.uint8))
    out = out.filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=3))
    dest = out_path or path
    if dest != path:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    out.save(dest, quality=92)
    return '%d Clawd(s), boxes %s' % (len(found), [(x0, y0, x1, y1) for x0, y0, x1, y1 in found])


def main():
    args = sys.argv[1:]
    test = False
    if args and args[0] == '--test':
        test = True
        args = args[1:]
    targets = {t.lstrip('0') or '0' for t in args}
    files = sorted(glob.glob(os.path.join(FRAMES, '*.jpg')))
    if targets:
        files = [f for f in files
                 if os.path.splitext(os.path.basename(f))[0].lstrip('0') in targets]
    sprite = sprite_rgba()
    print('%d frames' % len(files))
    for path in files:
        name = os.path.basename(path)
        out = '/tmp/frames/%s_new.jpg' % os.path.splitext(name)[0] if test else path
        try:
            info = reskin(path, sprite, out)
        except Exception as e:                      # noqa: BLE001
            info = 'ERROR %s' % e
        print('  %s: %s -> %s' % (name, info, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
