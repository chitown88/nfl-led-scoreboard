# -*- coding: utf-8 -*-
"""
Football-themed animation shown while the Pi updates itself from GitHub.

    1. Field goal: "NEW VERSION" while a kick sails through the uprights
    2. "IT'S GOOD!" with the new version number
    3. Spinning football + "UPDATING..." while git downloads
    4. "TOUCHDOWN!" when done (or "FUMBLE!" if the update failed)

Preview it in the emulator with:  python main.py --test update
"""
import threading
import time

from PIL import Image, ImageDraw

from fonts import font_04B_24__8, font_score_large_16

W, H = 64, 32
BALL = (150, 75, 20)
LACES = (255, 255, 255)
POSTS = (255, 200, 0)
TURF = (0, 90, 0)
YARD_LINE = (220, 220, 220)
FRAME_SECONDS = 0.08
MIN_UPDATING_SECONDS = 3   # spin at least this long, even if the download is quicker


def football(length, angle):
    """A football `length` pixels long, rotated by `angle` degrees.
    Drawn 4x bigger then shrunk, so it stays smooth at LED size."""
    s = 4
    L, T = length * s, int(length * 0.6) * s
    img = Image.new('RGBA', (L + 2 * s, T + 2 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([s, s, s + L - 1, s + T - 1], fill=BALL)
    cx, cy = img.width / 2, img.height / 2
    d.line([cx - L * 0.2, cy, cx + L * 0.2, cy], fill=LACES, width=s)
    for k in (-1, 0, 1):
        x = cx + k * L * 0.12
        d.line([x, cy - T * 0.2, x, cy + T * 0.2], fill=LACES, width=s)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    return img.resize((max(1, img.width // s), max(1, img.height // s)), Image.LANCZOS)


def paste_centered(canvas, sprite, x, y):
    canvas.paste(sprite, (int(round(x - sprite.width / 2)), int(round(y - sprite.height / 2))), sprite)


def blank():
    return Image.new('RGB', (W, H), 'black')


def draw_field(draw):
    draw.rectangle([0, 29, W - 1, H - 1], fill=TURF)
    for x in range(8, W, 12):
        draw.line([x, 29, x, H - 1], fill=YARD_LINE)


def draw_goalposts(draw):
    left, right, bar, base = 46, 60, 15, 28
    draw.line([left, bar, right, bar], fill=POSTS)      # crossbar
    draw.line([left, 0, left, bar], fill=POSTS)         # uprights
    draw.line([right, 0, right, bar], fill=POSTS)
    draw.line([(left + right) // 2, bar, (left + right) // 2, base], fill=POSTS)  # post


def kick_frames(version):
    """The ball is kicked from the left and sails between the uprights."""
    frames = []
    steps = 30
    x0, y0, x_end, y_end, lift = 6, 25, 74, 6, 3   # crosses the uprights at about y=9
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x_end - x0) * t
        y = y0 + (y_end - y0) * t - lift * 4 * t * (1 - t)
        img = blank()
        d = ImageDraw.Draw(img)
        draw_field(d)
        draw_goalposts(d)
        d.text((2, 2), 'NEW VERSION', font=font_04B_24__8, fill='white')
        paste_centered(img, football(9, i * 40), x, y)   # end-over-end spin
        frames.append((img, FRAME_SECONDS))
    return frames


def good_frames(version):
    frames = []
    for i in range(6):
        img = blank()
        d = ImageDraw.Draw(img)
        d.text((W // 2, 4), "IT'S GOOD!", font=font_score_large_16,
               fill=POSTS if i % 2 == 0 else 'white', anchor='mt')
        d.text((W // 2, 22), f'v{version}', font=font_04B_24__8, fill='white', anchor='mt')
        frames.append((img, 0.3))
    return frames


def updating_frame(i, version):
    img = blank()
    d = ImageDraw.Draw(img)
    d.text((W // 2, 1), 'UPDATING' + '.' * (i // 4 % 4), font=font_04B_24__8, fill='white', anchor='mt')
    paste_centered(img, football(20, -i * 15), W / 2, 16)
    d.text((W // 2, 26), f'TO v{version}', font=font_04B_24__8, fill=POSTS, anchor='mt')
    return img


def done_frames(version):
    frames = []
    for i in range(8):
        img = blank()
        d = ImageDraw.Draw(img)
        d.text((W // 2, 1), 'TOUCHDOWN!', font=font_04B_24__8,
               fill=POSTS if i % 2 == 0 else 'white', anchor='mt')
        d.text((W // 2, 9), version, font=font_score_large_16, fill='white', anchor='mt')
        d.text((W // 2, 26), 'RESTARTING', font=font_04B_24__8, fill='white', anchor='mt')
        frames.append((img, 0.3))
    return frames


def failed_frames(current_version):
    frames = []
    for i in range(8):
        img = blank()
        d = ImageDraw.Draw(img)
        d.text((W // 2, 1), 'UPDATE FAILED', font=font_04B_24__8, fill='white', anchor='mt')
        d.text((W // 2, 9), 'FUMBLE!', font=font_score_large_16,
               fill='red' if i % 2 == 0 else 'white', anchor='mt')
        d.text((W // 2, 26), f'KEEPING {current_version}', font=font_04B_24__8, fill='white', anchor='mt')
        frames.append((img, 0.3))
    return frames


def play(matrix, frames):
    for img, seconds in frames:
        matrix.SetImage(img, 0, 0)
        time.sleep(seconds)


def announce(matrix, version):
    play(matrix, kick_frames(version) + good_frames(version))


def done(matrix, version):
    play(matrix, done_frames(version))


def failed(matrix, current_version):
    play(matrix, failed_frames(current_version))


class Updating:
    """Spinning football in the background while git runs:

        with update_animation.Updating(matrix, '01.01.07'):
            ...download...
    """
    def __init__(self, matrix, version, min_seconds=MIN_UPDATING_SECONDS):
        self.matrix, self.version, self.min_seconds = matrix, version, min_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            self.matrix.SetImage(updating_frame(i, self.version), 0, 0)
            i += 1
            time.sleep(0.1)

    def __enter__(self):
        self._started = time.time()
        self._thread.start()
        return self

    def __exit__(self, exc_type, *exc):
        # let the ball spin for the minimum time (not if the download failed)
        if exc_type is None:
            remaining = self.min_seconds - (time.time() - self._started)
            if remaining > 0:
                time.sleep(remaining)
        self._stop.set()
        self._thread.join()
        return False


def preview_frames(old='01.01.06', new='01.01.07', updating_seconds=3):
    """Every frame of a full update, success then failure, for test mode."""
    spin = [(updating_frame(i, new), 0.1) for i in range(int(updating_seconds / 0.1))]
    return kick_frames(new) + good_frames(new) + spin + done_frames(new) + failed_frames(old)
