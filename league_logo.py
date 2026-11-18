# -*- coding: utf-8 -*-
"""
The league logo for the startup animation, cached in assets/logos/NFL.png.

It's downloaded in the background the first time it's needed, so the very
first boot shows the title without it and every boot after that has it.

If the image has a solid background instead of a transparent one, the
background is removed automatically: it's flood-filled in from the corners, so
only the area around the logo goes and anything white inside it stays.
"""
import os
import threading
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw

from paths import LOGO_DIR

# ESPN's league logo (transparent PNG, same server as the team logos).
LOGO_URL = 'https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png'
# Or the sportslogos version:
# LOGO_URL = 'https://content.sportslogos.net/logos/7/1007/full/dwuw5lojnwsj12vfe0hfa6z47.gif'

LOGO_FILE = os.path.join(LOGO_DIR, 'NFL.png')


def remove_background(img, tolerance=40):
    """Make a solid background transparent (only if there isn't transparency already)."""
    img = img.convert('RGBA')
    if img.getextrema()[3][0] < 250:          # already has transparent pixels
        return img
    w, h = img.size
    marker = (255, 0, 255, 0)
    work = img.copy()
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if work.getpixel(corner) != marker:
            ImageDraw.floodfill(work, corner, marker, thresh=tolerance)
    # wherever the fill reached becomes transparent
    filled = ImageChops.difference(work.convert('RGB'), Image.new('RGB', (w, h), marker[:3])).convert('L')
    alpha = filled.point(lambda v: 255 if v > 8 else 0)
    img.putalpha(ImageChops.multiply(img.getchannel('A'), alpha))
    return img


def trim(img):
    """Crop to the visible part of the logo."""
    box = img.getchannel('A').getbbox()
    return img.crop(box) if box else img


def download(url=LOGO_URL):
    import requests
    response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    img.seek(0)                                # first frame, if it's an animated GIF
    img = trim(remove_background(img))
    img.thumbnail((256, 256))
    os.makedirs(LOGO_DIR, exist_ok=True)
    img.save(LOGO_FILE)
    print(f'League logo saved: {LOGO_FILE}')
    return img


def get():
    """The cached logo (RGBA), or None if it isn't downloaded yet."""
    try:
        return Image.open(LOGO_FILE).convert('RGBA')
    except Exception:
        return None


def ensure_in_background():
    """If there's no cached logo, fetch one in the background for next time."""
    if os.path.isfile(LOGO_FILE):
        return

    def fetch():
        try:
            download()
        except Exception as e:
            print(f'League logo download failed (title will show text): {e}')
    threading.Thread(target=fetch, daemon=True).start()
