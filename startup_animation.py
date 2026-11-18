# -*- coding: utf-8 -*-
"""
Startup animation, shown while the scoreboard boots. Same broadcast style as
the update animation (it shares fx.py and the stadium from update_animation).

    1. COLD OPEN  dark stadium, camera pushing in; the light towers bang on one
                  by one and the field, crowd and camera flashes come up
    2. TITLE      wipe to the title card: "NFL", a gold SCOREBOARD banner, version
    3. LOADING    news banner with the real step, a TV down-and-distance box
                  (1ST & 10 ... 4TH & GOAL) and the ball carried down a mini field
       NO SIGNAL  banner turns red, a penalty flag lands: DELAY OF GAME, retry countdown
    4. TOUCHDOWN  ball crosses the goal line, flash, gold TOUCHDOWN! with confetti,
                  fade into the scoreboard

If there's no internet yet (common straight after the Pi boots), it retries
instead of crashing. Drawing happens on the main thread and the loading work in
a background thread, so the emulator window stays responsive on Windows.

Preview with:  python main.py --test startup
"""
import json
import math
import os
import threading
import time
import traceback

from PIL import Image, ImageDraw

import fx
from fx import W, GOLD, SILVER
from paths import BASE_DIR

FRAME = 0.07
MIN_LOADING_SECONDS = 2.5        # show the loading screen at least this long
RETRY_SECONDS = 10               # wait between retries when there's no connection

NAVY = (0, 30, 80)
YELLOW = (255, 200, 0)
ALERT_RED = (190, 0, 0)

play = fx.play


def version():
    try:
        with open(os.path.join(BASE_DIR, 'version.json')) as f:
            return json.load(f)['version']
    except Exception:
        return ''


# ============================================================ 1. COLD OPEN ===

def _stadium():
    import update_animation as ua      # the same stadium as the field goal
    return ua


def cold_open_frames():
    ua = _stadium()
    towers = ua.LIGHTS
    on_at = [14, 22, 30, 38]            # frame each tower switches on
    steps = 56
    for i in range(steps):
        cam_z = fx.lerp(0, 35, fx.ease_in_out(i / (steps - 1)))       # slow push in
        img = fx.blank()
        ua.draw_world(img, 7, cam_z, i if i > on_at[-1] else 0)
        ua.draw_posts(img, 7, cam_z)
        lit = sum(1 for t in on_at if i >= t)
        img = fx.fade(img, 0.88 * (1 - fx.ease_out(lit / len(towers))))
        d = ImageDraw.Draw(img)
        for k, x in enumerate(towers):
            y = ua.HORIZON - 7
            if i >= on_at[k]:
                age = i - on_at[k]
                flare = max(0.0, 1 - age / 6)             # bright burst as it comes on
                d.line([x - 1, y, x + 1, y], fill=(255, 255, 225))
                for gx, gy in ((x - 2, y), (x + 2, y), (x, y - 1), (x, y + 1)):
                    d.point((gx, gy), fill=fx.lerp_color((70, 70, 50), (255, 255, 220), flare))
                if flare > 0.3:
                    for gx, gy in ((x - 3, y), (x + 3, y), (x, y - 2), (x, y + 2), (x - 2, y - 1), (x + 2, y + 1),
                                   (x - 2, y + 1), (x + 2, y - 1)):
                        d.point((gx, gy), fill=fx.dim((255, 255, 200), flare * 0.7))
            else:
                d.line([x - 1, y, x + 1, y], fill=(45, 45, 45))
        if i in on_at:
            img = fx.flash(img, 0.18)
        yield img, FRAME * 1.15


# =============================================================== 2. TITLE ===

def title_scene(i, ver):
    img = fx.background(stripes=i * 0.5)
    d = ImageDraw.Draw(img)
    pop = fx.ease_back(i / 7)
    shine = (i - 16) / 12 if i >= 16 else None
    fx.draw_text(img, 'NFL', W / 2, 8, 'score_large.otf', 16, colors=SILVER,
                 scale=fx.lerp(0.5, 1.0, pop), shine=shine)
    # gold banner slides in under it
    bar = fx.ease_out((i - 5) / 8) if i >= 5 else 0
    if bar > 0:
        left = W - 68 * bar
        d.polygon([(left + 4, 17), (W, 17), (W, 24), (left, 24)], fill=YELLOW)
        d.rectangle([W - 2, 17, W - 1, 24], fill=(255, 255, 255))
        if i >= 9:
            fx.draw_text(img, 'SCOREBOARD', fx.lerp(W + 30, W / 2, fx.ease_out((i - 9) / 7)), 20.5,
                         colors=((20, 20, 20), (20, 20, 20)), outline=None, shadow=False)
    if i >= 14:
        fx.draw_text(img, f'v{ver}', W / 2, 28.5, colors=(YELLOW, (200, 140, 0)), outline=None,
                     alpha=fx.clamp((i - 14) / 5))
    return img


def title_frames(ver, start_from=None):
    first = title_scene(0, ver)
    if start_from is not None:
        for k in range(8):
            yield fx.wipe(start_from, first, k / 7), FRAME
    for i in range(36):
        yield title_scene(i, ver), FRAME


# ============================================================= 3. LOADING ===

FIELD_LEFT, FIELD_RIGHT, FIELD_TOP, FIELD_BOTTOM = 1, 62, 22, 30
END_ZONE = 6
PLAY_LEFT, PLAY_RIGHT = FIELD_LEFT + END_ZONE, FIELD_RIGHT - END_ZONE


def _field():
    img = Image.new('RGB', (FIELD_RIGHT - FIELD_LEFT + 1, FIELD_BOTTOM - FIELD_TOP + 1))
    d = ImageDraw.Draw(img)
    h = img.height
    # grass with alternating 10-yard stripes
    for k in range(10):
        x0 = round(END_ZONE + (PLAY_RIGHT - PLAY_LEFT) * k / 10)
        x1 = round(END_ZONE + (PLAY_RIGHT - PLAY_LEFT) * (k + 1) / 10)
        img.paste(fx.vgradient(x1 - x0 + 1, h, (0, 120, 0) if k % 2 else (0, 105, 0), (0, 70, 0)), (x0, 0))
    # end zones with a diagonal hatch
    for x0, top, bottom in ((0, (0, 55, 150), (0, 25, 80)), (img.width - END_ZONE, (175, 25, 25), (95, 10, 10))):
        img.paste(fx.vgradient(END_ZONE, h, top, bottom), (x0, 0))
        hatch = Image.new('RGB', (END_ZONE, h), fx.lerp_color(top, (255, 255, 255), 0.18))
        img.paste(hatch, (x0, 0), _hatch_mask(h))
    # goal lines and yard lines
    for k in range(11):
        x = round(END_ZONE + (PLAY_RIGHT - PLAY_LEFT) * k / 10)
        d.line([x, 0, x, h - 1], fill=(235, 235, 235) if k in (0, 10) else (120, 140, 120))
    return img


def _hatch_mask(h):
    m = Image.new('L', (END_ZONE, h), 0)
    d = ImageDraw.Draw(m)
    for k in range(-h, END_ZONE + h, 3):
        d.line([k, h, k + h, 0], fill=255)
    return m


FIELD = None


def down_and_distance(progress):
    if progress < 0.15:
        return '1ST & 10'
    if progress < 0.45:
        return '2ND & 7'
    if progress < 0.75:
        return '3RD & 3'
    return '4TH & GOAL'


def flag_sprite(t):
    """A yellow penalty flag, flapping a little."""
    img = Image.new('RGBA', (7, 7), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wave = 1 if math.sin(t * 2) > 0 else 0
    d.polygon([(1, 1), (6, 1 + wave), (6, 4 + wave), (1, 4)], fill=YELLOW)
    d.line([1, 1, 1, 6], fill=(90, 90, 90))
    return img


def loading_frame(step, progress, tick, retry_seconds=None):
    """step = text for the current step, progress = 0..1 (ball position).
    retry_seconds = countdown to show while waiting for a connection."""
    global FIELD
    if FIELD is None:
        FIELD = _field()
    ua = _stadium()
    alert = retry_seconds is not None
    img = fx.background(top=(30, 0, 0) if alert else (0, 12, 40), stripes=tick * 0.4)
    d = ImageDraw.Draw(img)

    # news banner with the step
    banner = ALERT_RED if alert else NAVY
    d.rectangle([0, 0, 63, 8], fill=banner)
    d.line([0, 9, 63, 9], fill=fx.dim(YELLOW, 0.6) if not alert else (255, 90, 90))
    if fx.text_width(step) <= 54:          # edge markers, when there's room
        d.rectangle([0, 0, 1, 8], fill=YELLOW)
        d.rectangle([62, 0, 63, 8], fill=YELLOW)
    dots = '' if alert else '.' * (tick // 5 % 4)
    label = step if fx.text_width(step + '...') > 58 else step + dots
    fx.draw_text(img, label, W / 2 + (0 if label == step else (fx.text_width(step + '...') - fx.text_width(label)) / 2),
                 4.5, outline=None, shadow=False,
                 alpha=1 if not alert else (1 if tick % 8 < 6 else 0.4))

    # TV down-and-distance box
    text = (f'RETRY IN {retry_seconds}' if tick % 24 >= 12 else 'DELAY OF GAME') if alert else down_and_distance(progress)
    tw = fx.text_width(text)
    box_l, box_r = round(W / 2 - tw / 2 - 4), round(W / 2 + tw / 2 + 3)
    d.rectangle([box_l, 12, box_r, 19], fill=(10, 10, 10))
    d.rectangle([box_l, 12, box_r, 19], outline=YELLOW if not alert else (255, 90, 90))
    fx.draw_text(img, text, W / 2, 16, colors=((255, 255, 255), (200, 200, 200)) if not alert else (YELLOW, YELLOW),
                 outline=None, shadow=False)

    # the field, the ball and its shadow
    img.paste(FIELD, (FIELD_LEFT, FIELD_TOP))
    x = PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT + END_ZONE // 2) * fx.clamp(progress)
    y = (FIELD_TOP + FIELD_BOTTOM) / 2
    d.ellipse([x - 3, FIELD_BOTTOM - 3, x + 3, FIELD_BOTTOM - 1], fill=(0, 45, 0))
    bob = 0 if alert else (1 if tick % 6 < 3 else 0)
    ball = ua.spiral_ball(9, 0 if alert else tick * 0.8, tilt=-8)
    img.paste(ball, (round(x - ball.width / 2), round(y - 1 - bob - ball.height / 2)), ball)
    if alert:   # flag thrown onto the field ahead of the ball
        flag = flag_sprite(tick / 3)
        img.paste(flag, (round(min(x + 8, PLAY_RIGHT - 7)), FIELD_TOP + 1), flag)
    return img


# =========================================================== 4. TOUCHDOWN ===

def touchdown_frames(start_from=None):
    confetti = fx.Confetti(seed=5)
    if start_from is not None:
        for k in range(3):
            yield fx.flash(start_from, 0.7 - 0.2 * k), FRAME
    last = None
    for i in range(30):
        img = fx.background(top=(30, 20, 0), bottom=(0, 0, 0))
        confetti.step_and_draw(img, i)
        shine = (i - 10) / 12 if i >= 10 else None
        fx.draw_text(img, 'TOUCHDOWN!', W / 2, 13, 'score_large.otf', 14, colors=GOLD,
                     scale=fx.lerp(0.5, 1.0, fx.ease_out(i / 5)), shine=shine)
        if i >= 8:
            fx.draw_text(img, "LET'S PLAY", W / 2, 26, colors=SILVER, outline=None,
                         alpha=fx.clamp((i - 8) / 5))
        last = img
        yield img, FRAME
    for k in range(8):
        yield fx.fade(last, k / 7), FRAME


# =============================================================== runner ===

_last = {}      # last frame shown per matrix, so the next scene can wipe/flash from it
_loading_shown = set()


class Loader:
    """Runs the loading work in a background thread and animates on the main
    thread until it's done.

        def work(step):
            step('LOADING TEAMS', 0.3)
            ...
        Loader(matrix).run(work)
    """
    def __init__(self, matrix, retry_on=(), first_step=('STARTING UP', 0.0)):
        self.matrix = matrix
        self.retry_on = retry_on
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

    def _show(self, img, seconds):
        _last[id(self.matrix)] = img
        self.matrix.SetImage(img, 0, 0)
        time.sleep(seconds)

    def run(self, work):
        tick, shown = 0, 0.0
        previous = _last.get(id(self.matrix))
        if previous is not None and id(self.matrix) not in _loading_shown:   # wipe in from the title card
            first = loading_frame(self.step_text, 0.0, 0)
            play(self.matrix, ((fx.wipe(previous, first, k / 7), FRAME) for k in range(8)))
        _loading_shown.add(id(self.matrix))
        while True:
            self.done, self.error = False, None
            started = time.time()
            threading.Thread(target=self._worker, args=(work,), daemon=True).start()

            while not self.done or time.time() - started < MIN_LOADING_SECONDS or shown < self.target - 0.01:
                if self.done and self.error is None:
                    self.target = 1.0
                if self.done and self.error is not None:
                    break
                shown += (self.target - shown) * 0.15
                self._show(loading_frame(self.step_text, shown, tick), FRAME)
                tick += 1

            if self.error is None:
                return
            if not isinstance(self.error, self.retry_on):
                raise self.error
            print(f'Startup: no connection ({self.error}), retrying in {RETRY_SECONDS}s')
            traceback.print_exception(type(self.error), self.error, self.error.__traceback__, limit=1)
            end = time.time() + RETRY_SECONDS
            while time.time() < end:
                left = max(1, math.ceil(end - time.time()))
                self._show(loading_frame('NO CONNECTION', shown, tick, retry_seconds=left), FRAME)
                tick += 1
            self.step_text = 'STARTING UP'


def intro(matrix, ver=None):
    """Cold open and title card."""
    ver = ver or version()
    def frames():
        last = None
        for img, seconds in cold_open_frames():
            last = img
            yield img, seconds
        yield from title_frames(ver, start_from=last)
    play(matrix, frames())
    _last[id(matrix)] = title_scene(35, ver)


def checking_updates(matrix):
    """A still loading frame while the update check talks to GitHub."""
    img = loading_frame('CHECKING UPDATES', 0.0, 0)
    first = _last.get(id(matrix))
    if first is not None:
        play(matrix, ((fx.wipe(first, img, k / 7), FRAME) for k in range(8)))
    _last[id(matrix)] = img
    _loading_shown.add(id(matrix))
    matrix.SetImage(img, 0, 0)


def kickoff(matrix):
    play(matrix, touchdown_frames(start_from=_last.get(id(matrix))))


def preview_frames(ver='01.01.11'):
    """Every frame of a startup, including a no-connection retry, for test mode."""
    frames, last = [], None
    for img, s in cold_open_frames():
        frames.append((img, s)); last = img
    frames += list(title_frames(ver, start_from=last))
    title_last = frames[-1][0]
    first_loading = loading_frame('CHECKING UPDATES', 0.0, 0)
    frames += [(fx.wipe(title_last, first_loading, k / 7), FRAME) for k in range(8)]
    steps = [('CHECKING UPDATES', 0.0), ('LOADING TEAMS', 0.3), ('LOADING LOGOS', 0.6), ('GETTING SCORES', 0.85)]
    shown, tick = 0.0, 0
    for text, target in steps:
        for _ in range(16):
            shown += (target - shown) * 0.15
            frames.append((loading_frame(text, shown, tick), FRAME))
            tick += 1
    for k in range(int(4 / FRAME)):
        frames.append((loading_frame('NO CONNECTION', shown, tick, retry_seconds=4 - int(k * FRAME)), FRAME))
        tick += 1
    for _ in range(28):
        shown += (1.0 - shown) * 0.15
        frames.append((loading_frame('GETTING SCORES', shown, tick), FRAME))
        tick += 1
    return frames + list(touchdown_frames(start_from=frames[-1][0]))
