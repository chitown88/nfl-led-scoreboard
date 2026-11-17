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
MIN_UPDATING_SECONDS = 10   # spin at least this long, even if the download is quicker


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
    left, right, bar, base = 46, 60, 17, 28
    draw.line([left, bar, right, bar], fill=POSTS)      # crossbar
    draw.line([left, 0, left, bar], fill=POSTS)         # uprights
    draw.line([right, 0, right, bar], fill=POSTS)
    draw.line([(left + right) // 2, bar, (left + right) // 2, base], fill=POSTS)  # post


# ---------------------------------------------------------------------------
# Field goal, kicker's point of view, then a chase cam behind the ball.
# Simple 3D: x = left/right, y = height, z = distance downfield (all in feet).
# ---------------------------------------------------------------------------
import math
import random

KICK_SPEED = 1.0          # bigger = slower field goal (1.5 = 50% longer)

FOCAL = 80                # perspective strength (pixels)
HORIZON = 15              # screen row of the horizon
POSTS_Z = 120             # distance to the goal posts
UPRIGHT_X = 9.25          # uprights are 18.5 ft apart
CROSSBAR_Y = 10
UPRIGHT_TOP = 40
END_ZONE = (POSTS_Z - 30, POSTS_Z)
FOLLOW = 8                # chase cam distance behind the ball
BOOT = (230, 230, 230)
BOOT_STRIPE = (220, 40, 40)
END_ZONE_COLOR = (0, 40, 110)
GRASS = (0, 70, 0)
LINE = (150, 150, 150)


def ball_height(z):
    """The kick's arc: still climbing gently at the posts (about 18 ft up),
    so it carries on into the distance afterwards."""
    return 0.6 + 0.00121 * z * (240 - z)


def project(x, y, z, cam_y, cam_z):
    dz = z - cam_z
    if dz <= 0.3:
        return None
    return 32 + FOCAL * x / dz, HORIZON - FOCAL * (y - cam_y) / dz, dz


# a fixed, random stadium crowd and lights along the horizon
_rng = random.Random(7)
CROWD = [(x, HORIZON - _rng.randint(1, 3),
          _rng.choice([(60, 20, 20), (20, 20, 60), (50, 50, 50), (70, 60, 20)]))
         for x in range(64) for _ in range(2) if _rng.random() < 0.7]
LIGHTS = [6, 22, 42, 58]


def draw_world(img, cam_y, cam_z):
    d = ImageDraw.Draw(img)
    # stadium
    for x, y, c in CROWD:
        d.point((x, y), fill=c)
    for x in LIGHTS:
        d.point((x, HORIZON - 6), fill=(255, 255, 200))
        d.point((x - 1, HORIZON - 6), fill=(120, 120, 90))
        d.point((x + 1, HORIZON - 6), fill=(120, 120, 90))
    # grass, then the end zone, then yard lines every 5 yards
    d.rectangle([0, HORIZON + 1, 63, 31], fill=GRASS)
    near, far = (project(0, 0, END_ZONE[0], cam_y, cam_z), project(0, 0, END_ZONE[1], cam_y, cam_z))
    if far:
        top = max(HORIZON + 1, round(far[1]))
        bottom = 31 if near is None else min(31, round(near[1]))
        if bottom >= top:
            d.rectangle([0, top, 63, bottom], fill=END_ZONE_COLOR)
    last_row = 99
    for z in range(-30, END_ZONE[0] + 1, 15):       # nearest first
        p = project(0, 0, z, cam_y, cam_z)
        if not p:
            continue
        row = round(p[1])
        # skip lines bunched up near the horizon so it doesn't turn into a grey band
        if HORIZON + 3 <= row < 32 and last_row - row >= 3:
            d.line([0, row, 63, row], fill=LINE)
            last_row = row


def draw_posts(img, cam_y, cam_z):
    d = ImageDraw.Draw(img)
    pts = {name: project(x, y, POSTS_Z, cam_y, cam_z) for name, (x, y) in {
        'base': (0, 0), 'mid': (0, CROSSBAR_Y),
        'lb': (-UPRIGHT_X, CROSSBAR_Y), 'lt': (-UPRIGHT_X, UPRIGHT_TOP),
        'rb': (UPRIGHT_X, CROSSBAR_Y), 'rt': (UPRIGHT_X, UPRIGHT_TOP)}.items()}
    if pts['base'] is None:
        return
    width = max(1, round(FOCAL * 0.5 / pts['base'][2]))
    xy = lambda p: (round(p[0]), round(p[1]))
    d.line([xy(pts['base']), xy(pts['mid'])], fill=POSTS, width=width)
    d.line([xy(pts['lb']), xy(pts['rb'])], fill=POSTS, width=width)
    d.line([xy(pts['lb']), xy(pts['lt'])], fill=POSTS, width=width)
    d.line([xy(pts['rb']), xy(pts['rt'])], fill=POSTS, width=width)


def ball_from_behind(width, spin):
    """The ball seen from behind, tumbling end over end: it stretches from a
    circle (end on) to its full length, with the laces flashing round."""
    s = 4
    w = max(2, width) * s
    h = round(w * (1 + 0.7 * abs(math.sin(spin))))
    img = Image.new('RGBA', (w + 2 * s, h + 2 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([s, s, s + w - 1, s + h - 1], fill=BALL)
    if math.sin(spin) > 0.35 and width >= 4:            # laces facing us
        cx, cy = img.width / 2, img.height / 2
        d.line([cx, cy - h * 0.22, cx, cy + h * 0.22], fill=LACES, width=s)
        for k in (-1, 0, 1):
            y = cy + k * h * 0.11
            d.line([cx - w * 0.15, y, cx + w * 0.15, y], fill=LACES, width=s)
    return img.resize((max(1, img.width // s), max(1, img.height // s)), Image.LANCZOS)


def _tall_ball(w):
    """Upright on the tee, from behind: a tall oval, laces facing away."""
    s = 4
    W, H = max(2, round(w)) * s, round(max(2, round(w)) * 1.7) * s
    img = Image.new('RGBA', (W + 2 * s, H + 2 * s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([s, s, s + W - 1, s + H - 1], fill=BALL)
    return img.resize((img.width // s, img.height // s), Image.LANCZOS)


SOCK = (200, 30, 30)
SHOE = (35, 35, 35)
SHOE_EDGE = (140, 140, 140)
SHOE_STRIPE = (255, 255, 255)
STUDS = (150, 150, 150)


def boot_sprite(length):
    """The kicker's own leg and cleat, seen from above and behind, toe pointing
    up-right at the ball. Drawn big and level, rotated, then shrunk to LED size."""
    s = 4
    u = s * length / 30                    # drawing unit: the sock+boot is 30 units long
    w, h = round(30 * u), round(16 * u)
    shoe = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(shoe)
    # sock coming in from the left, with a white band at the top
    d.rectangle([0, 4 * u, 11 * u, 12 * u], fill=SOCK)
    d.rectangle([8 * u, 4 * u, 10 * u, 12 * u], fill=SHOE_STRIPE)
    # the boot: a chunky rounded shape, toe on the right
    d.rounded_rectangle([9 * u, 2 * u, 29 * u, 14 * u], radius=6 * u, fill=SHOE, outline=SHOE_EDGE, width=round(u))
    d.line([13 * u, 10 * u, 19 * u, 6 * u], fill=SHOE_STRIPE, width=round(1.4 * u))      # short side stripe
    for x in (14, 20, 25):
        d.ellipse([x * u - u, 13.5 * u - u, x * u + u, 13.5 * u + u], fill=STUDS)       # studs peeking out
    shoe = shoe.rotate(35, resample=Image.BICUBIC, expand=True)
    return shoe.resize((max(1, shoe.width // s), max(1, shoe.height // s)), Image.LANCZOS)


BOOT_TARGET = (30, 21)        # bottom of the ball on the tee


def draw_boot(img, progress):
    """Swing the boot in from the bottom left to the ball, shrinking as it goes
    away from you. progress 0 = off screen, 1 = toe at the ball."""
    sprite = boot_sprite(30 - 14 * progress)   # pixels long
    toe_x, toe_y = BOOT_TARGET
    start_x, start_y = -8, 46
    tx = start_x + (toe_x - start_x) * progress
    ty = start_y + (toe_y - start_y) * progress
    # the toe is near the top-right of the rotated sprite
    img.paste(sprite, (round(tx - sprite.width * 0.86), round(ty - sprite.height * 0.2)), sprite)


def draw_impact(img, x, y):
    """A quick white burst where boot meets ball."""
    d = ImageDraw.Draw(img)
    for dx, dy in ((-5, 0), (5, 0), (0, -5), (-4, -4), (4, -4), (-4, 3), (4, 3)):
        d.line([x + dx * 0.5, y + dy * 0.5, x + dx, y + dy], fill='white')


def kick_frames(version):
    frames = []
    t_frame = FRAME_SECONDS * KICK_SPEED
    title = 'NEW VERSION'
    cam_y0, cam_z0 = 1.0, -FOLLOW      # crouched just behind the tee

    def scene(cam_y, cam_z, ball=None, text='', boot=None, impact=None):
        img = blank()
        draw_world(img, cam_y, cam_z)
        ball_dz = None
        if ball:
            bx, by, bz, sprite = ball
            p = project(bx, by, bz, cam_y, cam_z)
            ball_dz = p[2] if p else None
        # draw whichever is further away first
        if ball_dz is not None and ball_dz > POSTS_Z - cam_z:
            paste_centered(img, sprite, p[0], p[1])
            draw_posts(img, cam_y, cam_z)
        else:
            draw_posts(img, cam_y, cam_z)
            if ball_dz is not None:
                paste_centered(img, sprite, p[0], p[1])
        if boot is not None:
            draw_boot(img, boot)
        if impact:
            draw_impact(img, *impact)
        if text:
            ImageDraw.Draw(img).text((W // 2, 1), text, font=font_04B_24__8, fill='white', anchor='mt')
        return img

    tee_ball = (0, 0.9, 0, _tall_ball(FOCAL * 0.56 / FOLLOW))

    # 1. lining up the kick while the title types in
    for i in range(18):
        text = title[:round(len(title) * (i + 1) / 14)]
        frames.append((scene(cam_y0, cam_z0, tee_ball, text), t_frame * 1.3))

    # 2. the boot swings in and strikes the ball
    for i in range(7):
        frames.append((scene(cam_y0, cam_z0, tee_ball, title, boot=(i + 1) / 7), t_frame))
    # contact: the ball squashes and there's a flash
    tee_w = FOCAL * 0.56 / FOLLOW
    squashed = (0, 0.8, 0, _tall_ball(tee_w).resize((round(tee_w * 1.3) + 2, round(tee_w * 1.4)), Image.LANCZOS))
    frames.append((scene(cam_y0, cam_z0, squashed, title, boot=1, impact=BOOT_TARGET), t_frame * 2))

    # 3. chase cam: follow the ball, end over end, through the uprights
    steps, ball_end = 64, POSTS_Z + 60
    cam_stop = POSTS_Z + 4
    for i in range(1, steps + 1):
        t = i / steps
        ball_z = ball_end * t
        cam_z = min(ball_z - FOLLOW, cam_stop)
        if cam_z < cam_stop:
            # ride along at the ball's height, lagging a little so it drifts
            # up the screen while climbing and down while dropping
            cam_y = ball_height(ball_z) - 0.3 - 0.12 * (ball_height(ball_z) - ball_height(max(cam_z, 0)))
        dz = ball_z - cam_z
        sprite = ball_from_behind(round(FOCAL * 0.56 / dz), i * 0.55)
        frames.append((scene(cam_y, cam_z, (0, ball_height(ball_z), ball_z, sprite)), t_frame))

    # 4. a beat watching it go
    frames.append((scene(cam_y, cam_z), t_frame * 6))
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
