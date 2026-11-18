# -*- coding: utf-8 -*-
"""
Small graphics toolkit for the 64x32 animations: broadcast-style text
(outline, drop shadow, gradient fill, shine sweep, pop-in zoom), angled wipes,
fades, confetti and fireworks. Everything is cheap enough for a Pi Zero.
"""
import math
import os
import random
import time
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from paths import FONT_DIR

W, H = 64, 32


# ------------------------------------------------------------------ basics --

def blank(color=(0, 0, 0)):
    return Image.new('RGB', (W, H), color)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(a, b, t):
    return tuple(round(lerp(x, y, t)) for x, y in zip(a, b))


def dim(color, amount):
    return tuple(round(c * amount) for c in color)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_back(t, overshoot=1.7):
    """Ease out with a little overshoot: things 'pop' into place."""
    t = clamp(t) - 1
    return 1 + t * t * ((overshoot + 1) * t + overshoot)


@lru_cache(maxsize=None)
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def small_font():
    return font('04B_24__.TTF', 8)


def big_font(size=16):
    return font('score_large.otf', size)


@lru_cache(maxsize=64)
def vgradient(w, h, top, bottom):
    img = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([0, y, w - 1, y], fill=lerp_color(top, bottom, y / max(1, h - 1)))
    return img


def background(top=(0, 12, 40), bottom=(0, 0, 0), stripes=None):
    """Dark broadcast backdrop: vertical gradient, optional moving diagonal stripes."""
    img = vgradient(W, H, top, bottom).copy()
    if stripes is not None:
        d = ImageDraw.Draw(img)
        shift = int(stripes) % 8
        for x in range(-H, W + 8, 8):
            d.line([x + shift, H, x + shift + H, 0], fill=lerp_color(top, (255, 255, 255), 0.06))
    return img


# -------------------------------------------------------------------- text --

@lru_cache(maxsize=256)
def text_mask(text, font_name, size, scale=1.0):
    """Crisp (non-smoothed) 1-bit text as an 'L' mask with 2 px padding."""
    f = font(font_name, size)
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=f)
    mask = Image.new('L', (r - l + 4, b - t + 4), 0)
    d = ImageDraw.Draw(mask)
    d.fontmode = '1'
    d.text((2 - l, 2 - t), text, font=f, fill=255)
    if scale != 1.0:
        mask = mask.resize((max(1, round(mask.width * scale)), max(1, round(mask.height * scale))), Image.NEAREST)
    return mask


def text_width(text, font_name='04B_24__.TTF', size=8):
    return text_mask(text, font_name, size).width - 4


def draw_text(img, text, cx, cy, font_name='04B_24__.TTF', size=8,
              colors=((255, 255, 255), (255, 255, 255)), outline=(0, 0, 0),
              shadow=True, shine=None, scale=1.0, alpha=1.0):
    """Text centred on (cx, cy) with outline, drop shadow and a vertical gradient.

    shine: 0..1 moves a diagonal highlight across the text (None = no shine).
    scale: zoom (used for pop-ins). alpha: 0..1 fade.
    """
    mask = text_mask(text, font_name, size, round(scale, 2))
    if alpha < 1:
        mask = mask.point(lambda v: round(v * clamp(alpha)))
    x, y = round(cx - mask.width / 2), round(cy - mask.height / 2)
    if outline is not None or shadow:
        ring = mask.filter(ImageFilter.MaxFilter(3))
        if shadow:
            img.paste((0, 0, 0), (x + 1, y + 1), ring)
        if outline is not None:
            img.paste(outline, (x, y), ring)
    img.paste(vgradient(mask.width, mask.height, colors[0], colors[1]), (x, y), mask)
    if shine is not None and 0 <= shine <= 1:
        band = Image.new('L', mask.size, 0)
        d = ImageDraw.Draw(band)
        c = -mask.height + shine * (mask.width + 2 * mask.height)
        d.polygon([(c, 0), (c + 4, 0), (c + 4 - mask.height * 0.7, mask.height), (c - mask.height * 0.7, mask.height)],
                  fill=255)
        img.paste((255, 255, 255), (x, y), ImageChops.multiply(band, mask))
    return img


def shine_image(sprite, t, width=4):
    """A diagonal highlight sweeping across an RGBA sprite (t runs 0..1)."""
    if t is None or not 0 <= t <= 1:
        return sprite
    w, h = sprite.size
    band = Image.new('L', (w, h), 0)
    c = -h + t * (w + 2 * h)
    ImageDraw.Draw(band).polygon([(c, 0), (c + width, 0), (c + width - h * 0.7, h), (c - h * 0.7, h)], fill=170)
    band = ImageChops.multiply(band, sprite.getchannel('A'))
    out = sprite.copy()
    out.paste((255, 255, 255, 255), (0, 0), band)
    return out


GOLD = ((255, 240, 140), (225, 140, 0))
SILVER = ((215, 222, 235), (105, 115, 135))
RED = ((255, 120, 110), (190, 0, 0))


# ------------------------------------------------------------- transitions --

ACCENT = (255, 200, 0)


def wipe(frm, to, t, accent=ACCENT):
    """Broadcast wipe: an angled edge with a coloured bar sweeps left to right."""
    t = ease_in_out(t)
    edge = -14 + (W + 28) * t
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    slant = 10
    d.polygon([(0, 0), (edge + slant, 0), (edge - slant, H), (0, H)], fill=255)
    out = Image.composite(to, frm, mask)
    d = ImageDraw.Draw(out)
    d.polygon([(edge + slant, 0), (edge + slant + 3, 0), (edge - slant + 3, H), (edge - slant, H)], fill=accent)
    d.line([(edge + slant + 4, 0), (edge - slant + 4, H)], fill=(255, 255, 255))
    return out


def fade(img, t, to=(0, 0, 0)):
    return Image.blend(img, blank(to), clamp(t))


def flash(img, amount):
    return Image.blend(img, blank((255, 255, 255)), clamp(amount))


def shake(img, i, strength=1):
    """Camera shake: shift the picture by a pixel or so."""
    dx = ((i * 7) % 3 - 1) * strength
    dy = ((i * 5) % 3 - 1) * strength
    out = blank()
    out.paste(img, (dx, dy))
    return out


# --------------------------------------------------------------- particles --

CONFETTI_COLORS = [(255, 200, 0), (255, 255, 255), (220, 30, 30), (30, 90, 230), (0, 180, 70)]


class Confetti:
    def __init__(self, count=55, seed=11):
        rng = random.Random(seed)
        self.bits = [[rng.uniform(0, W), rng.uniform(-40, -2), rng.uniform(-0.4, 0.4), rng.uniform(0.3, 0.9),
                      rng.choice(CONFETTI_COLORS), rng.uniform(0, 6.3)] for _ in range(count)]

    def step_and_draw(self, img, tick):
        d = ImageDraw.Draw(img)
        for b in self.bits:
            b[0] += b[2] + 0.35 * math.sin(tick / 3 + b[5])
            b[1] += b[3]
            if b[1] > H + 2:            # recycle at the top
                b[1] = -2
            flip = math.sin(tick / 2 + b[5])     # paper tumbling: shade changes
            color = b[4] if flip > 0 else dim(b[4], 0.55)
            x, y = round(b[0]) % W, round(b[1])
            d.point((x, y), fill=color)
            if abs(flip) > 0.6:
                d.point((x + 1, y), fill=color)


def firework(img, x, y, color, t, sparks=14, radius=11, seed=0):
    """A burst at (x, y); t runs 0..1 over its life."""
    if not 0 <= t <= 1:
        return
    d = ImageDraw.Draw(img)
    rng = random.Random(seed)
    r = radius * ease_out(t)
    fadeout = (1 - t) ** 1.3
    for k in range(sparks):
        a = 2 * math.pi * k / sparks + rng.uniform(-0.15, 0.15)
        rr = r * rng.uniform(0.8, 1.05)
        sx = x + math.cos(a) * rr
        sy = y + math.sin(a) * rr + 3 * t * t        # droops as it fades
        d.point((round(sx), round(sy)), fill=dim(color, fadeout))
        tx = x + math.cos(a) * rr * 0.75
        ty = y + math.sin(a) * rr * 0.75 + 2 * t * t
        d.point((round(tx), round(ty)), fill=dim(color, fadeout * 0.45))
    if t < 0.15:
        d.point((x, y), fill=(255, 255, 255))


# ---------------------------------------------------------------- playback --

def play(matrix, frames):
    """Show (image, seconds) frames. Works with lists or generators; the time
    spent drawing each frame is taken off its wait, so pacing stays right even
    on a slow Pi."""
    deadline = time.time()
    for img, seconds in frames:
        matrix.SetImage(img.convert('RGB'), 0, 0)
        deadline += seconds
        wait = deadline - time.time()
        if wait > 0:
            time.sleep(wait)
        elif wait < -0.5:          # far behind (very slow device): don't try to catch up
            deadline = time.time()
