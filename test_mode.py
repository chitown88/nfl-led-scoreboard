# -*- coding: utf-8 -*-
"""
Test mode: cycle every screen layout with dummy data, no ESPN calls.

    python main.py --test                      all screens, all teams
    python main.py --test pre live             only these screens
    python main.py --test --teams NYG LAR      only these teams
    python main.py --test --images             also save contact sheets to test_output/
    python main.py --test --images --no-display   only save the images
    (or use RUN_TEST_MODE / TEST_SHOW_DISPLAY / TEST_SAVE_IMAGES in main.py with F5 in Spyder)

Each team plays itself, so a single screen shows its logo in both the away
and home spots. Dummy scores/situations come from test_data.json.

The logo layout files (scoreboard_logo_config.py, team_summary_logo_config.py)
are re-read before every screen, so you can tweak a position, save, and see
the change next time that team comes round, without restarting.
"""
import datetime
import importlib
import json
import os
import time

from PIL import Image, ImageDraw

import render
import update_animation
import scoreboard_logo_config
import team_summary_logo_config
import team_color_config
from paths import BASE_DIR

TEST_DATA_FILE = os.path.join(BASE_DIR, 'test_data.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'test_output')
ALL_SCREENS = ['pre', 'post', 'live', 'summary', 'update']
WIDTH, HEIGHT = 64, 32
SUMMARY_SCROLL = [('top', 0), ('middle', -21), ('bottom', -42)]   # where team_summary.py pauses


def load_test_data():
    with open(TEST_DATA_FILE) as f:
        return json.load(f)


def reload_layouts():
    """Pick up any edits to the logo layout files since the last screen."""
    for module in (scoreboard_logo_config, team_summary_logo_config):
        try:
            importlib.reload(module)
        except Exception as e:
            print(f'  ! {module.__name__} has an error, using the previous layout: {e}')


def blank_game(team, kind):
    """Scoreboard data in the same shape scoreboard.py builds from ESPN."""
    return {
        'homeAway': {'away': {'team': team, 'score': '', 'logo': ''},
                     'home': {'team': team, 'score': '', 'logo': ''}},
        'scoreboard_type': kind,
        'gameDate': '', 'gameTime': '',
        'teamPossession': '', 'teamPossessionHomeAway': '', 'possessionText': '',
        'quarter': 0, 'timeRemaining': '',
        'down': '', 'yardsToGo': '', 'yardLine': '', 'shortDownDistanceText': '',
        'isRedZone': False, 'isHalftime': False,
    }


def pre_game(team, s):
    data = blank_game(team, 'pre')
    # render.scoreboard() shows TODAY when the date matches today's
    data['gameDate'] = datetime.datetime.now().strftime('%m.%d') if s['gameDate'] == 'TODAY' else s['gameDate']
    data['gameTime'] = s['gameTime']
    return data


def post_game(team, s):
    data = blank_game(team, 'post')
    data['homeAway']['away']['score'] = s['away']
    data['homeAway']['home']['score'] = s['home']
    return data


def live_game(team, s):
    data = blank_game(team, 'in')
    data['homeAway']['away']['score'] = s['away']
    data['homeAway']['home']['score'] = s['home']
    data['quarter'] = s['quarter']
    data['timeRemaining'] = s['timeRemaining']
    if s.get('halftime'):
        data['isHalftime'] = True
    else:
        data['teamPossession'] = team   # test mode maps team -> team, see team_ids below
        data['teamPossessionHomeAway'] = s['possession']
        data['down'] = s['down']
        data['yardsToGo'] = s['yardsToGo']
        data['shortDownDistanceText'] = s['shortDownDistanceText']
        data['possessionText'] = s['possessionText'].replace('{team}', team)
        data['isRedZone'] = s['isRedZone']
    return data


def summary_data(team, s):
    """Team summary data in the same shape team_summary.py builds from ESPN."""
    colors = team_color_config.team_colors[team]
    return {
        'logo': '',
        'team': team,
        'teamColorDark': '#' + colors['dark'],
        'teamColorLite': '#' + colors['lite'],
        'place': s['place'],
        'record': s['record'],
        'lastGameOpp': f"{s['lastGameHomeAway']} {s['lastGameOpp']}",
        'lastGameOutcome': s['lastGameOutcome'],
        'lastGameScore': s['lastGameScore'],
        'nextGameDate': s['nextGameDate'],
        'nextGameTime': s['nextGameTime'],
        'nextGameOpp': f"{s['nextGameHomeAway']} {s['nextGameOpp']}",
        'nextGameText': s['nextGameText'],
        'postSeason': s['postSeason'],
        'endSeason': s['endSeason'],
    }


def pick_teams(teams):
    """All 32 teams, or just the ones asked for (ignoring unknown abbreviations)."""
    all_teams = sorted(team_summary_logo_config.layout_team_summary)
    if not teams:
        return all_teams
    unknown = [t for t in teams if t not in all_teams]
    if unknown:
        print(f'Unknown team(s) ignored: {", ".join(unknown)}. Valid: {" ".join(all_teams)}')
    return [t for t in all_teams if t in teams] or all_teams


def scoreboard_frame(screen, team, s, team_ids, position, total):
    build = {'pre': pre_game, 'post': post_game, 'live': live_game}[screen]
    image = render.scoreboard(build(team, s), WIDTH, HEIGHT, team_ids)
    return render.add_carousel_dots(image, position, total).convert('RGB')


def show_scoreboard(matrix, screen, team, s, team_ids, position, total, seconds):
    matrix.SetImage(scoreboard_frame(screen, team, s, team_ids, position, total), 0, 0)
    time.sleep(seconds)


def show_team_summary(matrix, data, pause):
    """Same scroll as team_summary.py: pause at the top, middle and bottom."""
    width, height = matrix.width, matrix.height
    x, y = 0, 0
    while True:
        image = render.team_summary(data, width, height, x, y)
        matrix.SetImage(image.convert('RGB'), 0, 0)
        if y in [0, -21]:
            time.sleep(pause)
        y -= 1
        if y == -43:
            break
    time.sleep(pause)


def contact_sheet(tiles, title, scale, columns):
    """Grid of (label, 64x32 image) tiles, scaled up with hard pixel edges."""
    gap, label_h, title_h = 6, 14, 30
    tile_w, tile_h = WIDTH * scale, HEIGHT * scale
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * (tile_w + gap) + gap, title_h + rows * (tile_h + label_h + gap)), (45, 45, 45))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 9), title, fill='white')
    max_chars = tile_w // 6
    for k, (label, image) in enumerate(tiles):
        x = gap + (k % columns) * (tile_w + gap)
        y = title_h + (k // columns) * (tile_h + label_h + gap)
        draw.text((x, y), label[:max_chars], fill='white')
        sheet.paste(image.resize((tile_w, tile_h), Image.NEAREST), (x, y + label_h))
    return sheet


def save_images(screens=None, teams=None):
    """Save one contact sheet per screen to test_output/.

    All teams: one tile per team, scenarios rotated across teams (like the display).
    Picked teams (--teams): every scenario for each of those teams.
    """
    screens = screens or ALL_SCREENS
    filtered = bool(teams)
    teams = pick_teams(teams)
    team_ids = {t: t for t in teams}
    test_data = load_test_data()
    scale = test_data.get('image_scale', 3)
    carousel = test_data['carousel_games']
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    reload_layouts()

    for screen in screens:
        if screen == 'update':
            frames = update_animation.preview_frames()
            tiles = [(f'frame {k + 1}', image) for k, (image, _) in enumerate(frames) if k % 2 == 0]
            sheet = contact_sheet(tiles, 'UPDATE ANIMATION - every other frame, success then failure', scale, 8)
            path = os.path.join(OUTPUT_DIR, 'test_update.png')
            sheet.save(path)
            print(f'Saved {path}')
            continue

        scenarios = test_data['team_summary' if screen == 'summary' else screen]
        tiles = []
        for n, team in enumerate(teams):
            picks = scenarios if filtered else [scenarios[n % len(scenarios)]]
            for s in picks:
                note = s.get('_note', '')
                if screen == 'summary':
                    data = summary_data(team, s)
                    for where, y in SUMMARY_SCROLL:
                        image = render.team_summary(data, WIDTH, HEIGHT, 0, y).convert('RGB')
                        tiles.append((f'{team} {where}' + (f' - {note}' if where == 'top' else ''), image))
                else:
                    image = scoreboard_frame(screen, team, s, team_ids, n % carousel + 1, carousel)
                    tiles.append((f'{team} - {note}' if note else team, image))

        columns = 6 if screen == 'summary' else 8
        title = {'pre': 'PRE-GAME', 'post': 'FINAL', 'live': 'LIVE', 'summary': 'TEAM SUMMARY'}[screen]
        sheet = contact_sheet(tiles, f'{title} - each team vs itself' if screen != 'summary' else title, scale, columns)
        path = os.path.join(OUTPUT_DIR, f'test_{screen}.png')
        sheet.save(path)
        print(f'Saved {path}')


def run(matrix, screens=None, teams=None):
    screens = screens or ALL_SCREENS
    teams = pick_teams(teams)

    # render.scoreboard() looks up the team with the ball via team_ids[id];
    # in test mode the "id" is just the abbreviation
    team_ids = {t: t for t in teams}

    print(f'TEST MODE - screens: {" ".join(screens)} | teams: {len(teams)} | Ctrl+C to stop')
    loop = 0
    try:
        while True:
            test_data = load_test_data()   # re-read each loop, so edits to the JSON show up too
            seconds = test_data['seconds_per_screen']
            carousel = test_data['carousel_games']

            for screen in screens:
                print(f'\n=== {screen.upper()} ===')
                if screen == 'update':
                    print('  update animation (success, then failure)')
                    update_animation.play(matrix, update_animation.preview_frames())
                    continue
                scenarios = test_data['team_summary' if screen == 'summary' else screen]

                for n, team in enumerate(teams):
                    # rotate each pass, so a team gets a different scenario every time round
                    s = scenarios[(n + loop) % len(scenarios)]
                    note = s.get('_note', '')
                    print(f'  {screen:<7} {team:<4} ({n + 1}/{len(teams)})  {note}')
                    reload_layouts()

                    if screen == 'summary':
                        show_team_summary(matrix, summary_data(team, s), test_data['team_summary_pause'])
                    else:
                        show_scoreboard(matrix, screen, team, s, team_ids,
                                        position=n % carousel + 1, total=carousel, seconds=seconds)
            loop += 1
    except KeyboardInterrupt:
        print('\nExiting test mode')
        matrix.Clear()
