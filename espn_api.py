# -*- coding: utf-8 -*-
"""
Created on Wed Dec 22 09:06:07 2021

@author: Jason
"""

import requests

def get_scoreboard(favorites):
    #with open('D:/test/espn_api_samples/week_18_early_live_1.json') as f:
    #    jsonData = json.load(f)

    url = 'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
    payload = {#'week':'18',
               'region': 'us'}
    jsonData = requests.get(url, params=payload).json()
    
    current_week = jsonData['week']['number']
    current_season = jsonData['season']
    current_season_type = current_season['type']
    current_season_year = current_season['year']
    
    events = jsonData['events']

    # If playoffs, remove favorites    
    if current_season_type == 3:
        favorites = []

    games = {'favorites':[]}
    
    for event in events:
        if any(x.lower() in event['name'].lower() for x in favorites):
            games['favorites'].append(event)
        else:
            game_status = event['status']['type']['state']
            if game_status not in games.keys():
                games[game_status] = []
            games[game_status].append(event)
            
        #Sort Favorites to be in order of list
        sorted_favorites = []
        for x in favorites:
            for each in games['favorites']:
                if x.lower() in each['name'].lower():
                    sorted_favorites.append(each)
                    
        games['favorites'] = sorted_favorites

    return games, current_week, current_season, current_season_type, current_season_year

def get_game_summary(gameId):
    #url = 'http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary'
    #payload = {'event':gameId}
    #jsonData = requests.get(url, params=payload).json()
    try:
        url = f'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard/{gameId}'
        jsonData = requests.get(url).json()
        success = True
    except:
        jsonData = None
        success = False
    return jsonData, success

def get_team_ids():
    url = 'http://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'
    payload = {'limit':'99'}
    jsonData = requests.get(url, params=payload).json()
    
    teams = jsonData['sports'][0]['leagues'][0]['teams']
    teams_id_dict = {}
    team_names_to_id = {}
    for each in teams:
        teams_id_dict[each['team']['id']] = each['team']['abbreviation']
        if 'name' not in each['team'].keys() and each['team']['abbreviation'] == 'WSH':
            each['team']['name'] = 'Commanders'
            
        team_names_to_id.update({each['team']['name']:each['team']['id']})
        
    return teams_id_dict, team_names_to_id

def get_standings(preferences):
    standingsLevel = {
        'nfl':'1',
        'conf':'2',
        'div':'3'}

    preference_standings_key = {
        'nfl':['NFL'],
        'conf':['AFC','NFC'],
        'div':['AFC EAST', 'AFC SOUTH', 'AFC NORTH', 'AFC WEST',
               'NFC EAST', 'NFC SOUTH', 'NFC NORTH', 'NFC WEST']
        }
    
    
    preference_payload_list = []
    for k, v in preference_standings_key.items():
        if any( item in preferences for item in v ):
            preference_payload_list.append(k)
            
    url ='https://site.api.espn.com/apis/v2/sports/football/nfl/standings'
    
    standings_data = {}
    for pref in preference_payload_list:
        payload = {'level':standingsLevel[pref],
                   'sort': 'winpercent:desc,playoffseed:asc'}
        standings = requests.get(url, params=payload).json()
        if pref == 'nfl':
            subList = [standings]
        elif pref == 'conf':
            subList = standings['children']
        elif pref == 'div':
            subList = []
            for each in standings['children']:
                subList += each['children']
            
        for each in subList:
            if pref == 'div':
                name = 'name'
            else:
                name = 'abbreviation'
                
            if each[name].upper() not in preferences:
                continue
                
            if each[name].upper() not in standings_data.keys():
                standings_data[each[name].upper()] = []
            for standing in each['standings']['entries']:
                team = standing['team']['abbreviation']
                team_data = {'team':team}
                for stat in standing['stats']:
                    team_data.update({stat['name']:stat['displayValue']})
                    
                standings_data[each[name].upper()].append(team_data)
                
    return standings_data


