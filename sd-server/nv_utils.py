"""
NailVision shared utilities
---------------------------
Used by both Colab notebooks (generation + LoRA training) so that the
dataset preparation and the generation pipeline apply the SAME nail
detection, crop, and colour logic.

Sections
  1. Colour utilities   (parse, name, dominant colours, ΔE2000 adherence, random palettes)
  2. Mask utilities     (clean-up, connected components, boxes, dilation)
  3. Crop / paste       (square crop around the nail -> 512x512 -> paste back)
  4. Palette seed       (paints the chosen colours into the nail before diffusion)
  5. Prompts            (style vocabulary + prompt builder)
  6. NailDetector       (YOLO-seg model trained in Part A) + drawing helper
"""
import colorsys
import random
import re

import cv2
import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, lab2rgb, rgb2lab
from sklearn.cluster import KMeans

# ============================================================
# 1. COLOUR UTILITIES
# ============================================================

# Colour vocabulary used in prompts and captions. Names are ones that
# appear in real nail-polish descriptions so the text encoder knows them.
NAMED_COLORS = {
    "white": "#F5F5F2", "off-white": "#EDE6DA", "black": "#141414",
    "gray": "#8A8A8A", "silver": "#C0C0C8", "gold": "#D4AF37",
    "rose gold": "#B76E79", "nude": "#E3BC9A", "beige": "#D9C3A5",
    "taupe": "#8B7D6B", "brown": "#6B4226", "chocolate": "#3E2418",
    "red": "#C8102E", "cherry red": "#9E1B32", "burgundy": "#6D071A",
    "wine": "#5A1E2B", "coral": "#FF7F61", "peach": "#FFC3A0",
    "orange": "#F27329", "yellow": "#F6D02F", "mustard": "#D1A220",
    "lime green": "#9ACD32", "olive green": "#6B7A3A", "sage green": "#9CAF88",
    "mint green": "#A8E6CF", "emerald green": "#0B7A55", "dark green": "#1F4D2B",
    "teal": "#1C8C8C", "turquoise": "#40C9C6", "baby blue": "#A7C7E7",
    "sky blue": "#6CB4EE", "royal blue": "#2850B4", "navy blue": "#1B2A4A",
    "lavender": "#C7B3E5", "lilac": "#B48FC9", "purple": "#6A3D9A",
    "plum": "#5E2750", "magenta": "#C2187A", "hot pink": "#FF4FA0",
    "pink": "#F4A6C1", "baby pink": "#F8C8DC", "dusty rose": "#C98B93",
    "mauve": "#A57C8E",
}

_NAMED_KEYS = list(NAMED_COLORS)
_NAMED_LAB = None


def parse_color(c):
    """Accepts '#RGB', '#RRGGBB', 'rgb(r,g,b)', 'rgba(r,g,b,a)' or an (r,g,b) tuple.
    Gradio's ColorPicker returns different formats across versions, so be lenient."""
    if isinstance(c, (tuple, list, np.ndarray)):
        return tuple(int(round(float(v))) for v in c[:3])
    s = str(c).strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        h = h[:6]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    nums = re.findall(r"[\d.]+", s)
    if len(nums) >= 3:
        return tuple(int(round(float(v))) for v in nums[:3])
    if s.lower() in NAMED_COLORS:
        return parse_color(NAMED_COLORS[s.lower()])
    raise ValueError(f"Cannot parse colour: {c!r}")


def rgb_to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[int(np.clip(v, 0, 255)) for v in rgb])


def to_lab(rgb_list):
    arr = np.asarray(rgb_list, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return rgb2lab(arr).reshape(-1, 3)


def color_name(rgb):
    """Nearest named colour by CIEDE2000 distance."""
    global _NAMED_LAB
    if _NAMED_LAB is None:
        _NAMED_LAB = to_lab([parse_color(NAMED_COLORS[k]) for k in _NAMED_KEYS])
    lab = to_lab([parse_color(rgb)])
    d = deltaE_ciede2000(np.repeat(lab, len(_NAMED_LAB), 0), _NAMED_LAB)
    return _NAMED_KEYS[int(np.argmin(d))]


def dominant_colors(img, mask, k=3, max_pixels=20000, seed=0):
    """K-means (in CIELAB) over the nail pixels only.
    Returns [(rgb_tuple, fraction), ...] sorted by fraction, largest first."""
    px = np.asarray(img.convert("RGB"))[np.asarray(mask, bool)]
    if len(px) == 0:
        return []
    if len(px) > max_pixels:
        idx = np.random.default_rng(seed).choice(len(px), max_pixels, replace=False)
        px = px[idx]
    lab = to_lab(px)
    k = max(1, min(k, len(np.unique(px, axis=0))))
    km = KMeans(n_clusters=k, n_init=4, random_state=seed).fit(lab)
    counts = np.bincount(km.labels_, minlength=k) / len(lab)
    centers_rgb = (lab2rgb(km.cluster_centers_.reshape(-1, 1, 3)).reshape(-1, 3) * 255).round()
    out = [(tuple(int(v) for v in centers_rgb[i]), float(counts[i])) for i in range(k)]
    return sorted(out, key=lambda t: -t[1])


def palette_from_nail(img, mask, k=4, merge_delta_e=15.0, min_fraction=0.08, max_colors=3, seed=0):
    """Readable 1-3 colour palette of a real nail (used for training captions).
    Merges near-identical shades (shading / highlights) and drops tiny clusters."""
    dom = dominant_colors(img, mask, k=k, seed=seed)
    kept = []                                   # [(rgb, fraction)]
    for rgb, frac in dom:
        lab = to_lab([rgb])
        for i, (krgb, kfrac) in enumerate(kept):
            if deltaE_ciede2000(lab, to_lab([krgb]))[0] < merge_delta_e:
                kept[i] = (krgb, kfrac + frac)
                break
        else:
            kept.append((rgb, frac))
    kept = sorted([c for c in kept if c[1] >= min_fraction], key=lambda t: -t[1])[:max_colors]
    return [c for c, _ in kept] or [dom[0][0]]


def color_adherence(img, mask, targets, k=5, coverage_threshold=20.0, max_pixels=20000, seed=0):
    """How faithfully a generated nail uses the target colours.

    mean_delta_e : for each target colour, the CIEDE2000 distance to the closest of the
                   k dominant nail colours, averaged over targets. LOWER is better.
                   (~<10 close match, 10-20 noticeable but same family, >25 different colour)
    per_color    : that distance for each target separately.
    coverage     : fraction of nail pixels within `coverage_threshold` ΔE of ANY target.
                   HIGHER is better (how much of the nail is "on-palette").
    """
    targets = [parse_color(t) for t in targets]
    dom = dominant_colors(img, mask, k=k, max_pixels=max_pixels, seed=seed)
    if not dom:
        return {"mean_delta_e": float("nan"), "per_color": [], "coverage": 0.0, "dominant": []}
    dom_lab = to_lab([c for c, _ in dom])
    tgt_lab = to_lab(targets)
    per = []
    for t in tgt_lab:
        d = deltaE_ciede2000(np.repeat(t[None], len(dom_lab), 0), dom_lab)
        per.append(float(d.min()))
    px = np.asarray(img.convert("RGB"))[np.asarray(mask, bool)]
    if len(px) > max_pixels:
        px = px[np.random.default_rng(seed).choice(len(px), max_pixels, replace=False)]
    px_lab = to_lab(px)
    dmin = np.full(len(px_lab), np.inf)
    for t in tgt_lab:
        dmin = np.minimum(dmin, deltaE_ciede2000(np.repeat(t[None], len(px_lab), 0), px_lab))
    return {
        "mean_delta_e": float(np.mean(per)),
        "per_color": [round(v, 2) for v in per],
        "coverage": float((dmin <= coverage_threshold).mean()),
        "dominant": [(rgb_to_hex(c), round(f, 3)) for c, f in dom],
    }


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, float(np.clip(s, 0, 1)), float(np.clip(v, 0, 1)))
    return (int(r * 255), int(g * 255), int(b * 255))


def random_palette(rng=None):
    """Random but harmonious 3-colour palette for the 2 'random' designs."""
    rng = rng or random.Random()
    scheme = rng.choice(["analogous", "complementary", "triadic", "monochrome", "neutral_accent"])
    h = rng.random()
    s = rng.uniform(0.35, 0.85)
    v = rng.uniform(0.55, 0.95)
    if scheme == "analogous":
        pal = [_hsv(h, s, v), _hsv(h + 0.08, s * 0.8, v), _hsv(h - 0.08, s, v * 0.85)]
    elif scheme == "complementary":
        pal = [_hsv(h, s, v), _hsv(h + 0.5, s, v * 0.9), _hsv(h, s * 0.3, 0.97)]
    elif scheme == "triadic":
        pal = [_hsv(h, s, v), _hsv(h + 1 / 3, s * 0.9, v), _hsv(h + 2 / 3, s * 0.8, v)]
    elif scheme == "monochrome":
        pal = [_hsv(h, s, v), _hsv(h, s * 0.45, min(1, v + 0.15)), _hsv(h, s, v * 0.55)]
    else:  # one colour + neutrals that are very common in salons
        neutral = rng.choice(["white", "black", "gold", "silver", "nude"])
        pal = [_hsv(h, s, v), parse_color(NAMED_COLORS[neutral]), _hsv(h, s * 0.4, 0.95)]
    rng.shuffle(pal)
    return pal, scheme


# ============================================================
# 2. MASK UTILITIES
# ============================================================

def mask_components(mask, min_area_frac=0.001, max_components=10):
    """Morphological clean-up, then split into connected components (largest first)."""
    m = np.asarray(mask, bool).astype(np.uint8)
    if m.sum() == 0:
        return []
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    min_area = min_area_frac * m.size
    comps = [(stats[i, cv2.CC_STAT_AREA], i) for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    comps.sort(reverse=True)
    return [(labels == i) for _, i in comps[:max_components]]


def fill_holes(mask):
    m = np.asarray(mask, bool).astype(np.uint8)
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(m)
    cv2.drawContours(out, contours, -1, 1, thickness=-1)
    return out.astype(bool)


def mask_to_box(mask):
    ys, xs = np.where(np.asarray(mask, bool))
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def dilate(mask, px):
    if px <= 0:
        return np.asarray(mask, bool)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(np.asarray(mask, bool).astype(np.uint8), k).astype(bool)


def iou(a, b):
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


# ============================================================
# 3. CROP / PASTE  (pixel specification)
#   original photo (any size)
#   -> square box around the nail, side = max(nail w, h) * (1 + 2*pad)
#   -> resized to 512 x 512 for the diffusion model
#   -> 512 x 512 result resized back to the box and pasted ONLY inside the nail mask
# ============================================================

def square_crop_box(mask, image_size, pad=0.6, min_side=96):
    W, H = image_size
    x0, y0, x1, y1 = mask_to_box(mask)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0) * (1 + 2 * pad)
    side = int(round(min(max(side, min_side), W, H)))
    bx0 = int(round(np.clip(cx - side / 2, 0, W - side)))
    by0 = int(round(np.clip(cy - side / 2, 0, H - side)))
    return (bx0, by0, bx0 + side, by0 + side)


def crop_to(img, mask, box, size=512):
    crop = img.convert("RGB").crop(box).resize((size, size), Image.LANCZOS)
    m = Image.fromarray(np.asarray(mask, bool).astype(np.uint8) * 255).crop(box)
    m = np.asarray(m.resize((size, size), Image.NEAREST)) > 127
    return crop, m


def paste_back(original, generated_crop, box, mask_full, feather=3):
    """Paste the generated crop into the original photo, only inside the (feathered) nail mask."""
    orig = original.convert("RGB")
    bw, bh = box[2] - box[0], box[3] - box[1]
    gen = generated_crop.convert("RGB").resize((bw, bh), Image.LANCZOS)
    canvas = orig.copy()
    canvas.paste(gen, box[:2])
    alpha = np.asarray(mask_full, bool).astype(np.float32)
    if feather > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=feather)
    alpha = alpha[..., None]
    out = np.asarray(canvas, np.float32) * alpha + np.asarray(orig, np.float32) * (1 - alpha)
    return Image.fromarray(out.round().clip(0, 255).astype(np.uint8))


# ============================================================
# 4. PALETTE SEED
#   Text alone ("red and gold") is a weak colour constraint. We therefore paint the
#   chosen colours into the nail region and start diffusion from that image with
#   strength < 1.0, so the colour layout survives into the final design
#   ("palette-seeded inpainting").
# ============================================================

STYLE_LAYOUT = {   # which colour layout to seed for each style (others: random)
    "french tip": "tip", "ombre": "gradient", "aura": "gradient", "chrome": "gradient",
    "cat eye": "gradient", "solid gloss": "solid", "minimalist": "solid",
    "checkered": "stripes", "geometric": "diagonal", "polka dots": "blobs", "floral": "blobs",
}


def make_palette_seed(crop, nail_mask, palette, rng=None, noise=8, layout=None):
    """Paint the palette into the nail region of `crop` (outside the mask is untouched).
    palette[0] = base colour (largest area), palette[1], palette[2] = accents."""
    rng = rng or random.Random()
    pal = [parse_color(c) for c in palette]
    arr = np.asarray(crop.convert("RGB")).copy()
    seed = np.zeros_like(arr)
    seed[:] = pal[0]                                        # base colour
    ys, xs = np.where(nail_mask)
    if len(xs):
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        layout = layout or rng.choice(["tip", "diagonal", "blobs", "stripes"])
        if layout == "gradient":                             # base -> accent1 -> accent2 along the nail
            t = np.clip((np.arange(seed.shape[0]) - y0) / h, 0, 1)[:, None, None]
            a, b, c = (np.array(p, np.float32) for p in pal)
            col = np.where(t < .5, a * (1 - 2 * t) + b * (2 * t), b * (2 - 2 * t) + c * (2 * t - 1))
            col = np.where(t < .35, a, col)                  # keep the base dominant
            seed = np.broadcast_to(col, seed.shape).astype(np.uint8).copy()
        elif layout == "solid":                              # mostly base, one small accent
            cv2.circle(seed, (int(x0 + w * rng.uniform(.35, .65)), int(y0 + h * rng.uniform(.55, .75))),
                       int(max(2, min(w, h) * .12)), pal[1], -1)
            cv2.circle(seed, (int(x0 + w * rng.uniform(.35, .65)), int(y0 + h * rng.uniform(.3, .45))),
                       int(max(2, min(w, h) * .06)), pal[2], -1)
        elif layout == "tip":                                # accent at the free edge
            cut = int(y0 + h * rng.uniform(0.18, 0.32))
            seed[:cut] = pal[1]
            cv2.ellipse(seed, (int(x0 + w * rng.uniform(.3, .7)), int(y0 + h * .65)),
                        (max(2, w // 7), max(2, h // 9)), 0, 0, 360, pal[2], -1)
        elif layout == "diagonal":
            pts = np.array([[x0, y0 + h * .55], [x1, y0 + h * .2], [x1, y0 + h * .45], [x0, y0 + h * .8]], np.int32)
            cv2.fillPoly(seed, [pts], pal[1])
            cv2.line(seed, (int(x0), int(y0 + h * .85)), (int(x1), int(y0 + h * .5)), pal[2], max(2, w // 12))
        elif layout == "blobs":
            for i in range(rng.randint(3, 6)):
                c = pal[1] if i % 2 == 0 else pal[2]
                cv2.circle(seed, (int(x0 + w * rng.random()), int(y0 + h * rng.random())),
                           int(max(2, min(w, h) * rng.uniform(.08, .2))), c, -1)
        else:
            n = rng.randint(2, 4)
            for i in range(n):
                y = int(y0 + h * (i + 1) / (n + 1))
                cv2.line(seed, (int(x0), y), (int(x1), y), pal[1 + i % 2], max(2, h // 14))
    seed = cv2.GaussianBlur(seed, (0, 0), 2.0)
    if noise:
        seed = np.clip(seed.astype(np.int16) + np.random.default_rng(rng.randint(0, 2**31)).integers(
            -noise, noise + 1, seed.shape), 0, 255).astype(np.uint8)
    m = np.asarray(nail_mask, bool)[..., None]
    out = np.where(m, seed, arr)
    return Image.fromarray(out.astype(np.uint8))


# ============================================================
# 5. PROMPTS
# ============================================================

STYLES = {
    "french tip": "french tip manicure, crisp smile line at the free edge",
    "ombre": "ombre gradient nail, smooth colour fade",
    "marble": "marble nail art, soft swirling veins",
    "floral": "floral nail art, small hand-painted flowers",
    "glitter": "glitter gel polish, fine sparkle",
    "geometric": "geometric nail art, clean lines and blocks",
    "polka dots": "polka dot nail art, neat dots",
    "chrome": "chrome powder nail, metallic mirror sheen",
    "abstract": "abstract nail art, organic brush strokes",
    "minimalist": "minimalist nail art, negative space, one simple accent",
    "checkered": "checkered pattern nail art",
    "aura": "aura nail, soft airbrushed glow in the centre",
    "cat eye": "cat eye magnetic gel polish, shimmering light band",
    "solid gloss": "solid colour glossy gel polish with a small accent detail",
}

NEGATIVE_PROMPT = (
    "deformed finger, extra fingers, skin texture on nail, blurry, low quality, jpeg artifacts, "
    "text, watermark, logo, cartoon, illustration, painting outside the nail, messy cuticles, chipped polish"
)

TRIGGER = "nvnail"   # token the LoRA is trained with


def build_prompt(style, palette, use_trigger=False):
    names = [color_name(parse_color(c)) for c in palette]
    # de-duplicate while keeping order (two picks can map to the same name)
    seen, uniq = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    if len(uniq) == 1:
        colour_txt = f"{uniq[0]} colour"
    elif len(uniq) == 2:
        colour_txt = f"{uniq[0]} base colour with {uniq[1]} accents"
    else:
        colour_txt = f"{uniq[0]} base colour with {uniq[1]} and {uniq[2]} accents"
    head = f"{TRIGGER} nail art" if use_trigger else "nail art"
    return (f"{head}, {STYLES.get(style, style)}, {colour_txt}, glossy gel polish, "
            "close-up photo of a single fingernail, professional salon manicure, realistic, sharp detail")


# ============================================================
# 6. NAIL DETECTOR  (YOLO segmentation model trained in Part A)
# ============================================================

class NailDetector:
    """Wraps the trained YOLO-seg model. Finds every nail in a hand photo and returns one
    full-resolution boolean mask per nail, numbered left -> right."""

    def __init__(self, weights, device=None, conf=0.35, imgsz=640):   # device None = GPU if available
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.device, self.conf, self.imgsz = device, conf, imgsz

    def detect(self, img, conf=None, min_area_frac=0.0003):
        img = img.convert("RGB")
        W, H = img.size
        r = self.model.predict(img, conf=conf or self.conf, imgsz=self.imgsz, device=self.device,
                               retina_masks=True, verbose=False)[0]
        if r.masks is None or len(r.masks) == 0:
            return []
        masks = r.masks.data.cpu().numpy() > 0.5
        confs = r.boxes.conf.cpu().numpy()
        out = []
        for m, c in zip(masks, confs):
            if m.shape != (H, W):
                m = cv2.resize(m.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)
            m = fill_holes(m)
            if m.sum() < min_area_frac * m.size:
                continue
            out.append(dict(mask=m, box=mask_to_box(m), conf=float(c)))
        out.sort(key=lambda d: (d["box"][0] + d["box"][2]) / 2)          # left -> right
        for i, d in enumerate(out):
            d["number"] = i + 1
        return out

    def segment(self, img, max_nails=1, **kw):
        """Largest nails first (used when no specific nail is chosen)."""
        dets = sorted(self.detect(img, **kw), key=lambda d: -d["mask"].sum())
        return [d["mask"] for d in dets[:max_nails]]


def draw_detections(img, dets, color=(255, 0, 180)):
    """Hand photo with each nail outlined and numbered."""
    arr = np.asarray(img.convert("RGB")).copy()
    over = arr.copy()
    th = max(2, int(round(min(arr.shape[:2]) / 300)))
    for d in dets:
        over[d["mask"]] = color
    arr = cv2.addWeighted(over, 0.35, arr, 0.65, 0)
    for d in dets:
        cnts, _ = cv2.findContours(d["mask"].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(arr, cnts, -1, color, th)
        x0, y0, x1, y1 = d["box"]
        cx, cy = int((x0 + x1) / 2), max(0, int(y0) - 6 * th)
        fs = 0.5 * th
        cv2.putText(arr, str(d["number"]), (cx - 6 * th, cy), cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 0, 0), th * 3)
        cv2.putText(arr, str(d["number"]), (cx - 6 * th, cy), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), th)
    return Image.fromarray(arr)
