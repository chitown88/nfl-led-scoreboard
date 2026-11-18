# -*- coding: utf-8 -*-
"""
Update animation, shown while the Pi updates itself from GitHub.
Styled like a TV broadcast graphics package.

    1. ALERT     "SOFTWARE UPDATE" banner sweeps in, the new version pops up and shines
    2. KICK      kicker's-eye view: boot strikes the ball (camera shake), then a
                 chase cam rides behind it, end over end, through the uprights
    3. IT'S GOOD white flash, gold "IT'S GOOD!" pops in over fireworks
    4. INSTALL   lower-third banner, a spiralling football, gold progress bar
                 (runs for as long as the download takes)
    5. DONE      "TOUCHDOWN!" with confetti, then the version card, fade out
       FAILED    red alert, the ball fumbles across the screen, "KEEPING vX"

Every scene is a generator of (image, seconds), drawn as it plays, so nothing
has to be rendered up front on the Pi.

Preview with:  python main.py --test update
"""
import math
import random
import threading
import time

from PIL import Image, ImageDraw

import fx
from fx import W, H, GOLD, SILVER, RED

FRAME = 0.07                  # seconds per frame for most scenes
KICK_SPEED = 1.0              # bigger = slower field goal (1.3 = 30% longer)
MIN_UPDATING_SECONDS = 3      # the install screen shows at least this long

NAVY = (0, 30, 80)
YELLOW = (255, 200, 0)
BALL = (150, 75, 20)
BALL_LIGHT = (205, 120, 55)
BALL_DARK = (95, 45, 12)
LACES = (255, 255, 255)
POSTS = (255, 200, 0)
POSTS_SHADE = (190, 130, 0)


# =============================================================== 1. ALERT ====

def alert_frames(version):
    """'SOFTWARE UPDATE' banner sweeps in; the version rises up and shines."""
    label = 'SOFTWARE UPDATE'
    steps = 46
    for i in range(steps):
        img = fx.background(stripes=i * 0.5)
        d = ImageDraw.Draw(img)
        # banner slides in from the left with an angled end
        bar = fx.ease_out(i / 9)
        right = -4 + 72 * bar
        d.polygon([(0, 2), (right + 4, 2), (right, 11), (0, 11)], fill=YELLOW)
        d.polygon([(0, 2), (3, 2), (3, 11), (0, 11)], fill=(255, 255, 255))
        # label slides in behind the banner
        if i >= 5:
            tx = fx.lerp(-30, W / 2 + 1, fx.ease_out((i - 5) / 8))
            fx.draw_text(img, label, tx, 6.5, colors=((20, 20, 20), (20, 20, 20)), outline=None, shadow=False)
        # version rises with a little overshoot, then a shine sweeps across
        if i >= 10:
            rise = fx.ease_back((i - 10) / 10)
            y = fx.lerp(44, 21, rise)
            shine = (i - 24) / 14 if i >= 24 else None
            fx.draw_text(img, version, W / 2, y, 'score_large.otf', 16, colors=SILVER, shine=shine)
        # underline grows from the centre
        if i >= 16:
            half = 24 * fx.ease_out((i - 16) / 8)
            d.line([W / 2 - half, 30, W / 2 + half, 30], fill=YELLOW)
        yield img, FRAME


# ================================================================ 2. KICK ====
# Simple 3D: x = left/right, y = height, z = distance downfield (feet).

FOCAL = 80
HORIZON = 15
POSTS_Z = 120
UPRIGHT_X = 9.25
CROSSBAR_Y = 10
UPRIGHT_TOP = 40
END_ZONE = (POSTS_Z - 30, POSTS_Z)
FOLLOW = 8
END_ZONE_COLOR = (0, 40, 110)
GRASS_NEAR = (0, 95, 0)
GRASS_FAR = (0, 45, 0)
STRIPE = (0, 80, 0)
LINE = (160, 160, 160)


def ball_height(z):
    """Still climbing gently at the posts (about 18 ft up), so it carries on afterwards."""
    return 0.6 + 0.00121 * z * (240 - z)


def project(x, y, z, cam_y, cam_z):
    dz = z - cam_z
    if dz <= 0.3:
        return None
    return 32 + FOCAL * x / dz, HORIZON - FOCAL * (y - cam_y) / dz, dz


_rng = random.Random(7)
CROWD = [(x, HORIZON - _rng.randint(1, 3),
          _rng.choice([(70, 22, 22), (22, 22, 70), (55, 55, 55), (80, 68, 22)]))
         for x in range(64) for _ in range(2) if _rng.random() < 0.7]
LIGHTS = [6, 22, 42, 58]
SKY = fx.vgradient(W, HORIZON, (0, 6, 22), (0, 18, 45))


def draw_world(img, cam_y, cam_z, tick):
    img.paste(SKY, (0, 0))
    d = ImageDraw.Draw(img)
    # stadium: crowd with camera flashes, light towers with a soft halo
    for x, y, c in CROWD:
        d.point((x, y), fill=c)
    rng = random.Random(tick)
    for _ in range(3):
        d.point((rng.randrange(64), HORIZON - rng.randint(1, 3)), fill=(255, 255, 255))
    for x in LIGHTS:
        y = HORIZON - 7
        for gx, gy in ((x - 2, y), (x + 2, y), (x, y - 1), (x, y + 1)):
            d.point((gx, gy), fill=(70, 70, 50))
        d.line([x - 1, y, x + 1, y], fill=(255, 255, 215))
    # grass: darker towards the horizon, with mowing stripes every 5 yards
    for row in range(HORIZON + 1, H):
        d.line([0, row, 63, row], fill=fx.lerp_color(GRASS_FAR, GRASS_NEAR, (row - HORIZON) / (H - HORIZON)))
    for z in range(-30, END_ZONE[0], 30):
        a, b = project(0, 0, z, cam_y, cam_z), project(0, 0, z + 15, cam_y, cam_z)
        if a and b:
            top, bottom = max(HORIZON + 1, round(b[1])), min(31, round(a[1]))
            if bottom > top:
                d.rectangle([0, top, 63, bottom], fill=fx.lerp_color(STRIPE, GRASS_NEAR, 0.35))
    near, far = project(0, 0, END_ZONE[0], cam_y, cam_z), project(0, 0, END_ZONE[1], cam_y, cam_z)
    if far:
        top = max(HORIZON + 1, round(far[1]))
        bottom = 31 if near is None else min(31, round(near[1]))
        if bottom >= top:
            d.rectangle([0, top, 63, bottom], fill=END_ZONE_COLOR)
    last_row = 99
    for z in range(-30, END_ZONE[0] + 1, 15):
        p = project(0, 0, z, cam_y, cam_z)
        if p:
            row = round(p[1])
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
    xy = lambda p, dx=0: (round(p[0]) + dx, round(p[1]))
    for a, b in (('base', 'mid'), ('lb', 'rb'), ('lb', 'lt'), ('rb', 'rt')):
        if width >= 3:   # close up: give the posts a shaded edge
            d.line([xy(pts[a], 1), xy(pts[b], 1)], fill=POSTS_SHADE, width=width)
        d.line([xy(pts[a]), xy(pts[b])], fill=POSTS, width=max(1, width - (1 if width >= 3 else 0)))


def shaded_ball(w, h):
    """An oval football with light from the top left."""
    s = 4
    img = Image.new('RGBA', (w * s + 2 * s, h * s + 2 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([s, s, s + w * s - 1, s + h * s - 1], fill=BALL_DARK)
    d.ellipse([s, s, s + w * s * 0.92, s + h * s * 0.9], fill=BALL)
    d.ellipse([s + w * s * 0.2, s + h * s * 0.14, s + w * s * 0.55, s + h * s * 0.42], fill=BALL_LIGHT)
    return img, s


def ball_from_behind(width, spin):
    """From behind, tumbling end over end: it stretches from round to full length."""
    w = max(2, width)
    h = max(2, round(w * (1 + 0.7 * abs(math.sin(spin)))))
    img, s = shaded_ball(w, h)
    if math.sin(spin) > 0.35 and width >= 4:      # laces come round
        d = ImageDraw.Draw(img)
        cx, cy = img.width / 2, img.height / 2
        d.line([cx, cy - h * s * 0.22, cx, cy + h * s * 0.22], fill=LACES, width=s)
        for k in (-1, 0, 1):
            y = cy + k * h * s * 0.11
            d.line([cx - w * s * 0.15, y, cx + w * s * 0.15, y], fill=LACES, width=s)
    return img.resize((max(1, img.width // s), max(1, img.height // s)), Image.LANCZOS)


def tee_ball(w, squash=1.0):
    width = max(2, round(w * (1.25 if squash < 1 else 1)))
    img, s = shaded_ball(width, max(2, round(w * 1.7 * squash)))
    return img.resize((img.width // s, img.height // s), Image.LANCZOS)


SOCK = (200, 30, 30)
SHOE = (35, 35, 35)
SHOE_EDGE = (140, 140, 140)
SHOE_STRIPE = (255, 255, 255)
STUDS = (150, 150, 150)
BOOT_TARGET = (30, 21)


def boot_sprite(length):
    s = 4
    u = s * length / 30
    shoe = Image.new('RGBA', (round(30 * u), round(16 * u)), (0, 0, 0, 0))
    d = ImageDraw.Draw(shoe)
    d.rectangle([0, 4 * u, 11 * u, 12 * u], fill=SOCK)
    d.rectangle([8 * u, 4 * u, 10 * u, 12 * u], fill=SHOE_STRIPE)
    d.rounded_rectangle([9 * u, 2 * u, 29 * u, 14 * u], radius=6 * u, fill=SHOE, outline=SHOE_EDGE, width=round(u))
    d.line([13 * u, 10 * u, 19 * u, 6 * u], fill=SHOE_STRIPE, width=round(1.4 * u))
    for x in (14, 20, 25):
        d.ellipse([x * u - u, 13.5 * u - u, x * u + u, 13.5 * u + u], fill=STUDS)
    shoe = shoe.rotate(35, resample=Image.BICUBIC, expand=True)
    return shoe.resize((max(1, shoe.width // s), max(1, shoe.height // s)), Image.LANCZOS)


def draw_boot(img, progress):
    sprite = boot_sprite(30 - 14 * progress)
    tx = fx.lerp(-8, BOOT_TARGET[0], progress)
    ty = fx.lerp(46, BOOT_TARGET[1], progress)
    img.paste(sprite, (round(tx - sprite.width * 0.86), round(ty - sprite.height * 0.2)), sprite)


def draw_impact(img, x, y, t):
    """Burst lines where boot meets ball, growing outwards."""
    d = ImageDraw.Draw(img)
    for dx, dy in ((-5, 0), (5, 0), (0, -5), (-4, -4), (4, -4), (-4, 3), (4, 3)):
        a, b = 0.4 + 0.5 * t, 0.9 + 0.5 * t
        d.line([x + dx * a, y + dy * a, x + dx * b, y + dy * b], fill=fx.dim((255, 255, 255), 1 - 0.5 * t))


def paste_centered(canvas, sprite, x, y):
    canvas.paste(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)), sprite)


def kick_frames():
    t_frame = FRAME * KICK_SPEED
    cam_y0 = 1.0

    def scene(cam_y, cam_z, tick, ball=None, boot=None):
        img = fx.blank()
        draw_world(img, cam_y, cam_z, tick)
        p = None
        if ball:
            bx, by, bz, sprite = ball
            p = project(bx, by, bz, cam_y, cam_z)
        if p and p[2] > POSTS_Z - cam_z:          # ball beyond the posts: draw it first
            paste_centered(img, sprite, p[0], p[1])
            draw_posts(img, cam_y, cam_z)
        else:
            draw_posts(img, cam_y, cam_z)
            if p:
                paste_centered(img, sprite, p[0], p[1])
        if boot is not None:
            draw_boot(img, boot)
        return img

    w_tee = FOCAL * 0.56 / FOLLOW
    on_tee = (0, 0.9, 0, tee_ball(w_tee))
    tick = 0

    # lining up: a slow push in towards the ball
    for i in range(16):
        cam_z = fx.lerp(-FOLLOW - 3, -FOLLOW, fx.ease_out(i / 15))
        yield scene(cam_y0, cam_z, tick, on_tee), t_frame * 1.2
        tick += 1

    # the boot swings in
    for i in range(7):
        yield scene(cam_y0, -FOLLOW, tick, on_tee, boot=fx.ease_in_out((i + 1) / 7) ** 1.3), t_frame
        tick += 1

    # contact: squash, flash, shake
    squashed = (0, 0.8, 0, tee_ball(w_tee, squash=0.8))
    for k in range(3):
        img = scene(cam_y0, -FOLLOW, tick, squashed, boot=1)
        draw_impact(img, *BOOT_TARGET, k / 2)
        img = fx.shake(fx.flash(img, 0.35 - 0.12 * k), k, 1)
        yield img, t_frame * 1.3
        tick += 1

    # chase cam through the uprights
    steps, ball_end, cam_stop = 64, POSTS_Z + 60, POSTS_Z + 4
    cam_y, cam_z = cam_y0, -FOLLOW
    for i in range(1, steps + 1):
        ball_z = ball_end * i / steps
        cam_z = min(ball_z - FOLLOW, cam_stop)
        if cam_z < cam_stop:
            cam_y = ball_height(ball_z) - 0.3 - 0.12 * (ball_height(ball_z) - ball_height(max(cam_z, 0)))
        dz = ball_z - cam_z
        sprite = ball_from_behind(round(FOCAL * 0.56 / dz), i * 0.55)
        img = scene(cam_y, cam_z, tick, (0, ball_height(ball_z), ball_z, sprite))
        if i <= 3:
            img = fx.shake(img, i + 3, 1)
        yield img, t_frame
        tick += 1

    # watch it sail away
    for _ in range(5):
        yield scene(cam_y, cam_z, tick), t_frame
        tick += 1


# ============================================================ 3. IT'S GOOD ====

def good_frames(backdrop, version):
    """White flash, then a gold 'IT'S GOOD!' pops in over fireworks."""
    dark = fx.fade(backdrop, 0.6)
    bursts = [(12, 8, (255, 70, 60), 2), (52, 7, (90, 150, 255), 6), (32, 5, (255, 220, 120), 10),
              (20, 6, (120, 255, 140), 15), (45, 9, (255, 255, 255), 19)]
    steps = 34
    for i in range(steps):
        img = dark.copy()
        for k, (x, y, c, start) in enumerate(bursts):
            fx.firework(img, x, y, c, (i - start) / 14, seed=k)
        pop = fx.ease_back(i / 6)
        shine = (i - 14) / 12 if i >= 14 else None
        fx.draw_text(img, "IT'S GOOD!", W / 2, 13, 'score_large.otf', 14, colors=fx.GOLD,
                     scale=fx.lerp(0.5, 1.0, pop), shine=shine)
        if i >= 8:
            fx.draw_text(img, f'v{version}', W / 2, 26, colors=SILVER, alpha=fx.clamp((i - 8) / 5))
        if i < 3:
            img = fx.flash(img, 0.8 - 0.3 * i)
        yield img, FRAME


# ============================================================= 4. INSTALL ====

def spiral_ball(length, phase, tilt=-12):
    """Side-on football spinning in a tight spiral: the laces roll round it."""
    s = 4
    L, T = length * s, round(length * 0.58) * s
    img = Image.new('RGBA', (L + 2 * s, T + 2 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([s, s, s + L - 1, s + T - 1], fill=BALL_DARK)
    d.ellipse([s, s, s + L - 1, s + T * 0.88], fill=BALL)
    d.ellipse([s + L * 0.2, s + T * 0.12, s + L * 0.75, s + T * 0.4], fill=BALL_LIGHT)
    # stripes near each end
    for ex in (0.17, 0.83):
        d.line([s + L * ex, s + T * 0.15, s + L * ex, s + T * 0.85], fill=(235, 235, 235), width=s)
    # laces travel round the ball as it spins
    lace_y = s + T / 2 - math.sin(phase) * T * 0.32
    if math.cos(phase) > -0.2:
        cx = s + L / 2
        d.line([cx - L * 0.17, lace_y, cx + L * 0.17, lace_y], fill=LACES, width=s)
        for k in (-2, -1, 0, 1, 2):
            x = cx + k * L * 0.07
            d.line([x, lace_y - T * 0.07, x, lace_y + T * 0.07], fill=LACES, width=s)
    img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return img.resize((img.width // s, img.height // s), Image.LANCZOS)


def install_frame(tick, version, progress):
    img = fx.background(stripes=tick * 0.4)
    d = ImageDraw.Draw(img)
    # lower-third style banner
    d.rectangle([0, 1, 63, 8], fill=NAVY)
    d.rectangle([0, 1, 2, 8], fill=YELLOW)
    d.line([0, 9, 63, 9], fill=fx.dim(YELLOW, 0.6))
    fx.draw_text(img, 'INSTALLING' + '.' * (tick // 5 % 4), 6 + fx.text_width('INSTALLING...') / 2, 5,
                 outline=None, shadow=False)
    # the ball in flight, with speed streaks behind it
    for k, y in enumerate((14, 17, 20)):
        x = 4 + (tick * 3 + k * 7) % 14
        d.line([x, y, x + 5 + k, y], fill=(90, 90, 90))
    paste_centered(img, spiral_ball(20, tick * 0.7), 36, 17)
    # gold progress bar with a moving glint
    left, right, top, bottom = 4, 59, 26, 29
    d.rectangle([left - 1, top - 1, right + 1, bottom + 1], fill=(30, 30, 30))
    fill_to = left + (right - left) * fx.clamp(progress)
    if fill_to > left:
        img.paste(fx.vgradient(round(fill_to - left) + 1, bottom - top + 1, GOLD[0], GOLD[1]), (left, top))
        glint = left + (tick * 2) % max(1, round(fill_to - left) + 1)
        d.line([glint, top, glint, bottom], fill=(255, 255, 230))
    for k in range(1, 10):
        x = round(left + (right - left) * k / 10)
        d.point((x, bottom), fill=(0, 0, 0))
    return img


class Updating:
    """Install screen in the background while git runs:

        with update_animation.Updating(matrix, '01.01.11'):
            ...download...

    The bar creeps towards 90% while waiting, then fills when the download is done.
    """
    def __init__(self, matrix, version, min_seconds=MIN_UPDATING_SECONDS):
        self.matrix, self.version, self.min_seconds = matrix, version, min_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.tick, self.progress = 0, 0.0
        self.last = None

    def _run(self):
        while not self._stop.is_set():
            elapsed = time.time() - self._started
            self.progress = 0.9 * (1 - math.exp(-elapsed / 2.5))
            self.last = install_frame(self.tick, self.version, self.progress)
            self.matrix.SetImage(self.last, 0, 0)
            self.tick += 1
            time.sleep(FRAME)

    def __enter__(self):
        self._started = time.time()
        self._thread.start()
        return self

    def __exit__(self, exc_type, *exc):
        if exc_type is None:
            remaining = self.min_seconds - (time.time() - self._started)
            if remaining > 0:
                time.sleep(remaining)
        self._stop.set()
        self._thread.join()
        if exc_type is None:           # fill the bar to 100%
            start = self.progress
            for k in range(1, 7):
                self.last = install_frame(self.tick, self.version, fx.lerp(start, 1.0, fx.ease_out(k / 6)))
                self.matrix.SetImage(self.last, 0, 0)
                self.tick += 1
                time.sleep(FRAME)
        if self.last is not None:
            _last_install[id(self.matrix)] = self.last
        return False


# ================================================================ 5. DONE ====

def touchdown_scene(confetti, tick, i):
    img = fx.background(top=(30, 20, 0), bottom=(0, 0, 0))
    confetti.step_and_draw(img, tick)
    shine = (i - 10) / 12 if i >= 10 else None
    # TOUCHDOWN! nearly fills the width, so it grows in without overshooting
    fx.draw_text(img, 'TOUCHDOWN!', W / 2, 13, 'score_large.otf', 14, colors=fx.GOLD,
                 scale=fx.lerp(0.5, 1.0, fx.ease_out(i / 5)), shine=shine)
    return img


def version_card(confetti, tick, i, version):
    img = fx.background()
    confetti.step_and_draw(img, tick)
    fx.draw_text(img, 'UPDATED TO', W / 2, 4, colors=((200, 200, 200), (150, 150, 150)), outline=None)
    shine = (i - 4) / 12 if i >= 4 else None
    fx.draw_text(img, version, W / 2, 16, 'score_large.otf', 16, colors=SILVER, shine=shine)
    fx.draw_text(img, 'RESTARTING' + '.' * (i // 4 % 4), W / 2, 28, colors=(YELLOW, YELLOW), outline=None)
    return img


def done_frames(version, start_from=None):
    confetti = fx.Confetti()
    tick = 0
    first = touchdown_scene(confetti, tick, 0)
    if start_from is not None:
        for k in range(8):
            yield fx.wipe(start_from, first, k / 7), FRAME
    for i in range(30):
        last = touchdown_scene(confetti, tick, i)
        yield last, FRAME
        tick += 1
    card = version_card(confetti, tick, 0, version)
    for k in range(8):
        yield fx.wipe(last, card, k / 7), FRAME
    for i in range(26):
        last = version_card(confetti, tick, i, version)
        yield last, FRAME
        tick += 1
    for k in range(8):
        yield fx.fade(last, k / 7), FRAME


# ============================================================== FAILED ====

def failed_frames(current_version, start_from=None):
    """Red alert, then the ball fumbles across the screen."""
    def scene(i):
        pulse = 0.5 + 0.5 * math.sin(i / 3)
        img = fx.background(top=fx.lerp_color((40, 0, 0), (70, 0, 0), pulse), bottom=(0, 0, 0))
        d = ImageDraw.Draw(img)
        bar = fx.ease_out(i / 8)
        d.rectangle([0, 1, round(63 * bar), 8], fill=(200, 0, 0))
        if i >= 4:
            fx.draw_text(img, 'UPDATE FAILED', W / 2, 5, outline=None, shadow=False,
                         alpha=fx.clamp((i - 4) / 4))
        # loose ball bouncing along the bottom
        t = i / 18                     # gone before the KEEPING line appears
        if t <= 1:
            x = fx.lerp(-6, 70, t)
            bounce = abs(math.sin(t * math.pi * 3)) * 7 * (1 - t * 0.5)
            paste_centered(img, spiral_ball(9, 0, tilt=-i * 35), x, 28 - bounce)
        jitter = (1 if i % 2 else -1) if 6 <= i < 14 else 0
        fx.draw_text(img, 'FUMBLE!', W / 2 + jitter, 15, 'score_large.otf', 14, colors=RED,
                     scale=fx.lerp(0.5, 1.0, fx.ease_back((i - 4) / 6)) if i >= 4 else 0.5,
                     alpha=1 if i >= 4 else 0)
        if i >= 18:
            fx.draw_text(img, f'KEEPING v{current_version}', W / 2, 26, outline=None,
                         alpha=fx.clamp((i - 18) / 5))
        return img

    first = scene(0)
    if start_from is not None:
        for k in range(6):
            yield fx.wipe(start_from, first, k / 5, accent=(220, 0, 0)), FRAME
    last = first
    for i in range(46):
        last = scene(i)
        yield last, FRAME
    for k in range(8):
        yield fx.fade(last, k / 7), FRAME


# ============================================================== running ====

play = fx.play


def announce_frames(version):
    last = None
    for img, seconds in alert_frames(version):
        last = img
        yield img, seconds
    kick = kick_frames()
    first_kick, sec = next(kick)
    for k in range(8):
        yield fx.wipe(last, first_kick, k / 7), FRAME
    yield first_kick, sec
    for img, seconds in kick:
        last = img
        yield img, seconds
    yield from good_frames(last, version)


def announce(matrix, version):
    """Alert, field goal and IT'S GOOD, before the download starts."""
    play(matrix, announce_frames(version))


_last_install = {}    # last install frame per matrix, so DONE/FAILED can wipe from it


def done(matrix, version):
    play(matrix, done_frames(version, start_from=_last_install.get(id(matrix))))


def failed(matrix, current_version):
    play(matrix, failed_frames(current_version, start_from=_last_install.get(id(matrix))))


def preview_frames(old='01.01.10', new='01.01.11', updating_seconds=3):
    """Every frame of a full update, success then failure, for test mode."""
    frames = list(announce_frames(new))
    install = []
    steps = int(updating_seconds / FRAME)
    for k in range(steps):
        progress = 0.9 * (1 - math.exp(-k * FRAME / 2.5))
        install.append((install_frame(k, new, progress), FRAME))
    for k in range(1, 7):
        install.append((install_frame(steps + k, new, fx.lerp(progress, 1, fx.ease_out(k / 6))), FRAME))
    last_install = install[-1][0]
    return (frames + install + list(done_frames(new, start_from=last_install))
            + install[:20] + list(failed_frames(old, start_from=install[19][0])))
