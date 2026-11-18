# -*- coding: utf-8 -*-
"""
Startup animation: shown while the scoreboard boots.

    1. Stadium lights switch on one tower at a time and the field lights up
    2. Title card with the version number
    3. Loading: a mini football field is the progress bar; the ball moves
       downfield as each real loading step finishes
    4. "TOUCHDOWN!" when the ball reaches the end zone

If there's no internet yet (common straight after the Pi boots), it shows
"NO CONNECTION" and retries instead of crashing.

The drawing always happens on the main thread and the loading work runs in a
background thread, so the emulator window stays responsive on Windows.

Preview it with:  python main.py --test startup
"""
import json
import math
import os
import random
import threading
import time
import traceback

from PIL import Image, ImageDraw

from fonts import font_04B_24__8, font_score_large_16, font_score_large_14
from paths import BASE_DIR

W, H = 64, 32
FRAME_SECONDS = 0.08
MIN_LOADING_SECONDS = 2.5        # show the loading field at least this long
RETRY_SECONDS = 10               # wait between retries when there's no connection

YELLOW = (255, 200, 0)
LIGHT = (255, 255, 210)
POLE = (90, 90, 90)
BALL = (150, 75, 20)
LACES = (255, 255, 255)
GRASS = (0, 110, 0)
GRASS_DARK = (0, 25, 0)
LINE = (190, 190, 190)
END_ZONE_LEFT = (0, 40, 120)
END_ZONE_RIGHT = (150, 20, 20)

TOWERS = [6, 22, 42, 58]         # x of each light tower
HORIZON = 17

_rng = random.Random(3)
CROWD = [(x, y, _rng.choice([(120, 30, 30), (30, 30, 120), (90, 90, 90), (130, 110, 30)]))
         for y in range(HORIZON - 4, HORIZON) for x in range(64) if _rng.random() < 0.55]


def version():
    try:
        with open(os.path.join(BASE_DIR, 'version.json')) as f:
            return json.load(f)['version']
    except Exception:
        return ''


def blank():
    return Image.new('RGB', (W, H), 'black')


def show(matrix, img, seconds):
    matrix.SetImage(img, 0, 0)
    time.sleep(seconds)


def dim(color, amount):
    return tuple(round(c * amount) for c in color)


# ---------------------------------------------------------------- 1. lights --

def stadium(lights_on, flicker_tower=None):
    """Night stadium. lights_on = how many towers are lit (0-4)."""
    img = blank()
    d = ImageDraw.Draw(img)
    brightness = 0.15 + 0.85 * lights_on / len(TOWERS)
    # field, with a few yard lines in perspective
    for y in range(HORIZON, H):
        d.line([0, y, W - 1, y], fill=dim(GRASS, brightness * (0.6 + 0.4 * (y - HORIZON) / (H - HORIZON))))
    for y in (19, 22, 27):
        d.line([0, y, W - 1, y], fill=dim(LINE, brightness * 0.8))
    # crowd
    for x, y, c in CROWD:
        d.point((x, y), fill=dim(c, 0.25 + 0.75 * brightness))
    # light towers
    for i, x in enumerate(TOWERS):
        d.line([x, 6, x, HORIZON - 5], fill=POLE)
        on = i < lights_on or i == flicker_tower
        bank = LIGHT if on else (40, 40, 40)
        d.rectangle([x - 2, 3, x + 2, 5], fill=bank)
        if on:   # glow
            for gx, gy in ((x - 3, 4), (x + 3, 4), (x, 2), (x - 2, 2), (x + 2, 2)):
                d.point((gx, gy), fill=(110, 110, 80))
    return img


def lights_frames():
    frames = [(stadium(0), 0.6)]
    for tower in range(len(TOWERS)):
        # a quick flicker before each tower comes on
        frames += [(stadium(tower, flicker_tower=tower), 0.07), (stadium(tower), 0.07),
                   (stadium(tower, flicker_tower=tower), 0.05), (stadium(tower), 0.1),
                   (stadium(tower + 1), 0.35)]
    frames.append((stadium(len(TOWERS)), 0.6))
    return frames


# ----------------------------------------------------------- 2. title card --

def title_frames(ver):
    frames = []
    for i in range(14):
        img = stadium(len(TOWERS))
        # darken the stadium behind the text
        img = Image.blend(img, blank(), 0.75)
        d = ImageDraw.Draw(img)
        d.text((W // 2, 2), 'NFL', font=6, fill='white', anchor='mt')
        d.text((W // 2, 16), 'SCOREBOARD', font=font_04B_24__8, fill='white', anchor='mt')
        if i >= 4:
            d.text((W // 2, 24), f'v{ver}', font=font_04B_24__8, fill=YELLOW, anchor='mt')
        frames.append((img, 0.12))
    return frames


# --------------------------------------------------------------- 3. loading --

def football(length, angle):
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


FIELD_LEFT, FIELD_RIGHT, FIELD_TOP, FIELD_BOTTOM = 1, 62, 20, 30
END_ZONE_WIDTH = 6


def loading_frame(step, progress, tick, message_color='white'):
    """step = text for the current step, progress = 0..1 (ball position)."""
    img = blank()
    d = ImageDraw.Draw(img)
    d.text((W // 2, 1), step, font=font_04B_24__8, fill=message_color, anchor='mt')
    d.text((W // 2, 9), '.' * (tick // 4 % 4), font=font_04B_24__8, fill='white', anchor='mt')
    # the field
    d.rectangle([FIELD_LEFT, FIELD_TOP, FIELD_RIGHT, FIELD_BOTTOM], fill=GRASS)
    d.rectangle([FIELD_LEFT, FIELD_TOP, FIELD_LEFT + END_ZONE_WIDTH - 1, FIELD_BOTTOM], fill=END_ZONE_LEFT)
    d.rectangle([FIELD_RIGHT - END_ZONE_WIDTH + 1, FIELD_TOP, FIELD_RIGHT, FIELD_BOTTOM], fill=END_ZONE_RIGHT)
    play_left, play_right = FIELD_LEFT + END_ZONE_WIDTH, FIELD_RIGHT - END_ZONE_WIDTH
    for k in range(11):   # every 10 yards
        x = round(play_left + (play_right - play_left) * k / 10)
        d.line([x, FIELD_TOP, x, FIELD_BOTTOM], fill=LINE if k in (0, 10) else dim(LINE, 0.6))
    # the ball, carried downfield, with a little bob
    x = play_left + (play_right - play_left + END_ZONE_WIDTH // 2) * progress
    y = (FIELD_TOP + FIELD_BOTTOM) / 2 - (1 if tick % 6 < 3 else 0)
    sprite = football(9, 10 * math.sin(tick / 3))
    img.paste(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)), sprite)
    return img


# --------------------------------------------------------------- 4. kickoff --

def kickoff_frames():
    frames = []
    for i in range(8):
        img = loading_frame('', 1.0, 0)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, FIELD_TOP - 2], fill='black')
        d.text((W // 2, 3), 'TOUCHDOWN!', font=font_score_large_14,
               fill=YELLOW if i % 2 == 0 else 'white', anchor='mt')
        frames.append((img, 0.18))
    return frames


# ------------------------------------------------------------------ runner --

class Loader:
    """Runs the loading work in a background thread and animates the field
    on the main thread until it's done.

        def work(step):
            step('LOADING TEAMS', 0.3)
            ...
        Loader(matrix).run(work)
    """
    def __init__(self, matrix, retry_on=(), first_step=('STARTING UP', 0.0)):
        self.matrix = matrix
        self.retry_on = retry_on            # exception types that mean "try again"
        self.step_text, self.target = first_step
        self.error = None
        self.done = False

    def step(self, text, progress):
        print(f'Startup: {text.lower()}')
        self.step_text, self.target = text, progress

    def _worker(self, work):
        try:
            work(self.step)
        except BaseException as e:
            self.error = e
        finally:
            self.done = True

    def run(self, work):
        tick, shown = 0, 0.0
        while True:
            self.done, self.error = False, None
            started = time.time()
            threading.Thread(target=self._worker, args=(work,), daemon=True).start()

            while not self.done or time.time() - started < MIN_LOADING_SECONDS or shown < self.target - 0.01:
                if self.done and self.error is None:
                    self.target = 1.0
                if self.done and self.error is not None:
                    break
                shown += (self.target - shown) * 0.15           # ease the ball towards its target
                show(self.matrix, loading_frame(self.step_text, shown, tick), FRAME_SECONDS)
                tick += 1

            if self.error is None:
                return
            if not isinstance(self.error, self.retry_on):
                raise self.error
            # no connection yet: say so, wait, then try again from the start
            print(f'Startup: no connection ({self.error}), retrying in {RETRY_SECONDS}s')
            traceback.print_exception(type(self.error), self.error, self.error.__traceback__, limit=1)
            for i in range(int(RETRY_SECONDS / 0.25)):
                text = 'NO CONNECTION' if (i // 4) % 2 == 0 else 'RETRYING'
                show(self.matrix, loading_frame(text, shown, tick, message_color=(255, 80, 80)), 0.25)
                tick += 3
            self.step_text = 'STARTING UP'


def intro(matrix, ver=None):
    """Stadium lights and title card."""
    ver = ver or version()
    for img, seconds in lights_frames() + title_frames(ver):
        show(matrix, img, seconds)


def kickoff(matrix):
    for img, seconds in kickoff_frames():
        show(matrix, img, seconds)


def checking_updates(matrix):
    """A still loading frame while the update check talks to GitHub."""
    matrix.SetImage(loading_frame('CHECKING UPDATES', 0.0, 0), 0, 0)


def preview_frames(ver='01.01.10'):
    """Every frame of a startup, including a no-connection retry, for test mode."""
    frames = lights_frames() + title_frames(ver)
    steps = [('CHECKING UPDATES', 0.0), ('LOADING TEAMS', 0.3), ('LOADING LOGOS', 0.6), ('GETTING SCORES', 0.85)]
    shown, tick = 0.0, 0
    for text, target in steps:
        for _ in range(14):
            shown += (target - shown) * 0.15
            frames.append((loading_frame(text, shown, tick), FRAME_SECONDS))
            tick += 1
    for i in range(16):
        text = 'NO CONNECTION' if (i // 4) % 2 == 0 else 'RETRYING'
        frames.append((loading_frame(text, shown, tick, message_color=(255, 80, 80)), 0.25))
        tick += 3
    for _ in range(25):
        shown += (1.0 - shown) * 0.15
        frames.append((loading_frame('GETTING SCORES', shown, tick), FRAME_SECONDS))
        tick += 1
    return frames + kickoff_frames()
