# -*- coding: utf-8 -*-
"""
Created on Fri Jan  7 19:24:59 2022

@author: Jason
"""

import sys
import os

# RGBMatrixEmulator reads emulator_config.json from the working directory,
# so run from the project folder whatever folder the script was launched from
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import argparse

# Emulator by default (Spyder, F5/debug). On the Pi: sudo python3 main.py --production
arg_parser = argparse.ArgumentParser(description='NFL LED Scoreboard')
arg_parser.add_argument('--production', '-production', action='store_true',
                        help='drive the physical LED matrix instead of the emulator')
arg_parser.add_argument('--test', nargs='*', choices=['pre', 'post', 'live', 'summary'], metavar='SCREEN',
                        help='show dummy data from test_data.json instead of ESPN. '
                             'Optionally pick screens: pre post live summary (default: all)')
arg_parser.add_argument('--teams', nargs='+', type=str.upper, metavar='TEAM',
                        help='with --test, only show these teams, e.g. --teams NYG LAR')
arg_parser.add_argument('--images', action='store_true',
                        help='with --test, save contact-sheet images of every screen to test_output/')
arg_parser.add_argument('--no-display', action='store_true',
                        help="with --test, don't cycle the screens on the emulator/LEDs")
args, _ = arg_parser.parse_known_args()   # ignore any extra args Spyder passes

# Spyder shortcut: set to True to run test mode with F5, same as --test
RUN_TEST_MODE = False
# Test mode options (only used when test mode is on):
TEST_SHOW_DISPLAY = True    # cycle the screens on the emulator (or LEDs with --production)
TEST_SAVE_IMAGES = False    # save contact-sheet images of every screen to test_output/

if RUN_TEST_MODE and args.test is None:
    args.test = []
test_show_display = TEST_SHOW_DISPLAY and not args.no_display
test_save_images = TEST_SAVE_IMAGES or args.images

# Test mode images: no display needed, so done before the matrix starts
if args.test is not None:
    if not (test_show_display or test_save_images):
        sys.exit('Test mode has nothing to do: TEST_SHOW_DISPLAY and TEST_SAVE_IMAGES are both off')
    if test_save_images:
        import test_mode
        test_mode.save_images(screens=args.test, teams=args.teams)
    if not test_show_display:
        sys.exit(0)

if args.production:
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions
    except ImportError:
        sys.exit('--production needs the rgbmatrix library - is this running on the Pi?')
    print('Running on the LED matrix')

    # Pi only: update from GitHub first if version.json there is newer
    import updater
    updater.check_for_update(force=True)
else:
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
    print('Running in the emulator')

os.umask(0)

# Configuration for the matrix
options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat-pwm'  # If you have an Adafruit HAT: 'adafruit-hat'
options.gpio_slowdown = 2
# Keep running as root after the matrix starts. By default the LED library
# switches to the 'daemon' user, which can't read or write the project folder.
options.drop_privileges = False

matrix = RGBMatrix(options = options)

display_width = matrix.width
display_height = matrix.height

# Test mode: dummy data only, no ESPN calls, so it stops here
if args.test is not None:
    import test_mode
    test_mode.run(matrix, screens=args.test, teams=args.teams)
    sys.exit(0)

import espn_api

import scoreboard_logo_config
layout_team_pregame = scoreboard_logo_config.layout_team_pregame

import scoreboard
import team_summary
import standings
import clock

import load_static_data

try:
    load_static_data.load()
except Exception as e:
    print(f'Logo update failed, using cached logos: {e}')


favorites = ['Bears','Bengals']
team_ids, team_names_to_id = espn_api.get_team_ids()

timeZone = 'US/Central'
timezone = 'Europe/London'

main_order = ['clock', 'scoreboard', 'team_summary', 'standings']


def run(liveGames):
    if liveGames == False:
        clock.run_clock(matrix, display_width, display_height)
    liveGames = scoreboard.run_scoreboard(matrix, display_width, display_height)
    if liveGames == False:
        team_summary.run_team_summary(matrix, display_width, display_height)
        standings.run_standings(matrix, display_width, display_height)
    return liveGames



if __name__ == "__main__":
    liveGames = False
    while True:
        try:
            if args.production:
                updater.check_for_update()   # only really checks every few hours
            liveGames = run(liveGames)
    
        except KeyboardInterrupt:
            print("Exiting NFL-LED-SCOREBOARD\n")
            sys.exit(0)
        

