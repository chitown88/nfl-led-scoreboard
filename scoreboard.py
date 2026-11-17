# -*- coding: utf-8 -*-
"""
Created on Sat Dec 18 09:59:20 2021

@author: Jason
"""

import time

import espn_api

import render

from dateutil import parser
import pytz

import scoreboard_logo_config 
layout_team_pregame = scoreboard_logo_config.layout_team_pregame

test_mode = False
favorites = ['Bears']
team_ids, team_names_to_id = espn_api.get_team_ids()

timeZone = 'US/Central'
timeZone = 'Europe/London'

def run_scoreboard(matrix, display_width, display_height):


    games, current_week, current_season, current_season_type, current_season_year = espn_api.get_scoreboard(favorites)

    try:
        len(games['in'])
        liveGames = True
    except:
        liveGames = False

    if current_season_type == 3 and liveGames == False:
        playoff_week = str(current_week)
        #Render Play off logo for week
        playoff_logo_url_dict = {"1":'https://content.sportslogos.net/logos/7/1008/full/-nfl-playoffs-logo-primary-2016-6864.png',
                                 "2":'https://content.sportslogos.net/logos/7/1008/full/-nfl-playoffs-logo-primary-2016-6864.png',
                                 "3":'https://content.sportslogos.net/logos/7/1008/full/-nfl-playoffs-logo-primary-2016-6864.png',
                                 "4":'https://content.sportslogos.net/logos/7/593/full/-super-bowl-logo-primary-2026-59326552026.png',
                                 "5":'https://content.sportslogos.net/logos/7/593/full/-super-bowl-logo-primary-2026-59326552026.png',
                                 }
        #playoff_logo_url_dict = requests.get('https://raw.githubusercontent.com/chitown88/ScotWinYard/master/test.json').json()
        playoff_url = playoff_logo_url_dict[playoff_week]
        logo = render.playoff_logo(playoff_url, display_width, display_height)
        matrix.SetImage(logo.convert('RGB'), 0,0 )
        time.sleep(4)
    
    if current_season_type == 3 and liveGames == True:   
        display_order = ['in']
    else:
        display_order = ['favorites', 'in', 'post', 'pre', 'other']

    for display_order_idx, each in enumerate(display_order):
        count = 0
        if each not in games.keys():
            print(f'No {each} games.')
            continue
        
        game_carasol_len = len(games[each])
        homeAway = {}
        for game in games[each]:
            count += 1
            
            gameId = game['id']
            if test_mode == False:
                success = False
                while success == False:
                    game, success = espn_api.get_game_summary(gameId)
            
            scoreboard_type = game['status']['type']['state'] # to render correct gamet state (pre, live, post, other)
            competition_data = game['competitions'][0]
            
            for team in competition_data['competitors']:
                homeAway[team['homeAway']] = {}
                homeAway[team['homeAway']]['team'] = team['team']['abbreviation']
                homeAway[team['homeAway']]['score'] = team['score']
                homeAway[team['homeAway']]['logo'] = team['team']['logo']
                
            # test reverse home away
            #homeAway_temp = {}
            #homeAway_temp['home'] = homeAway['away']
            #homeAway_temp['away'] = homeAway['home']
            #homeAway = homeAway_temp
            
                    
                
            d = parser.isoparse(game['date'])
            d = d.astimezone(pytz.timezone(timeZone))
            gameDate = d.strftime('%m.%d')
            gameTime = d.strftime('%I:%M').lstrip("0")
            gameTime = d.strftime('%I:%M %p').lstrip("0")
            
            quarter = game['status']['period']
            time_remaining = game['status']['displayClock']
            
            # test make all games live at half
            #scoreboard_type = 'in'
            #quarter = 2
            #time_remaining = '15:00'
            
            try:
                situation = game['competitions'][0]['situation']
    
                if situation['lastPlay']['type']['text'] == 'End of Half':
                    halftime = True
                    team_possession = ''
                    possessionText = ''
                    teamPossessionHomeAway = ''
                    down = ''
                    yards_to_go = ''
                    shortDownDistanceText = ''
                    yardLine = ''
                    in_redzone = False
                   
                else:
                    halftime = False
                    team_possession = situation['possession']
                    possessionText = situation['possessionText']
                    down = situation['down']
                    yards_to_go = situation['distance']
                    yardLine = situation['yardLine']
                    shortDownDistanceText = situation['shortDownDistanceText']
                    in_redzone = situation['isRedZone']
                    for k,v in homeAway.items():
                        if team_ids[team_possession] == v['team']:
                            teamPossessionHomeAway = k
                            break
            except:
                halftime = False
                team_possession = ''
                possessionText = ''
                teamPossessionHomeAway = ''
                down = ''
                yards_to_go = ''
                shortDownDistanceText = ''
                yardLine = ''
                in_redzone = False
            
               
            
            data = {'homeAway': homeAway,
                    'gameDate':gameDate,
                    'gameTime':gameTime,
                    'scoreboard_type':scoreboard_type,
                    'teamPossession':team_possession,
                    'teamPossessionHomeAway':teamPossessionHomeAway,
                    'possessionText':possessionText,
                    'quarter':quarter,
                    'timeRemaining':time_remaining,
                    'down':down,
                    'yardsToGo':yards_to_go,
                    'yardLine':yardLine,
                    'shortDownDistanceText':shortDownDistanceText,
                    'isRedZone':in_redzone,
                    'isHalftime':halftime}          
            
            
            scoreboard = render.scoreboard(data, display_width, display_height, team_ids)    
            
            scoreboard = render.add_carousel_dots(scoreboard, count, game_carasol_len)

            #TV DELAY
            time.sleep(10)
    
            matrix.SetImage(scoreboard.convert('RGB'), 0,0 )
            
            sleep_delay = 9
            #sleep_delay = 2
            if scoreboard_type in ['pre','post']:
                sleep_delay = 5
                #sleep_delay = 2
            time.sleep(sleep_delay)
            
               
            
    return liveGames            
            

    
    
    
    
    
    
    
    
