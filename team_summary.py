# -*- coding: utf-8 -*-
"""
Created on Thu Jan  6 14:50:35 2022

@author: Jason
"""

import time

import requests
import datetime

import espn_api

import re

import render

from dateutil import parser
import pytz

import team_color_config 

favorites = ['Bears']

team_ids, team_names_to_id = espn_api.get_team_ids()

timeZone = 'US/Central'
timeZone = 'Europe/London'

team_colors = team_color_config.team_colors

def find_division_place(node, team_id):
    if 'standings' in node:
        for i, entry in enumerate(node['standings'].get('entries', []), start=1):
            if entry['team']['id'] == str(team_id):
                return i
    for child in node.get('children', []):
        result = find_division_place(child, team_id)
        if result:
            return result
    return None

def run_team_summary(matrix, display_width, display_height):
    url = 'http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/calendar/ondays'
    jsonData = requests.get(url).json()
    
    currentSeason = re.search(r'\d{4}', jsonData['season']['$ref']).group()
    today = datetime.datetime.now(pytz.timezone(timeZone))

    for each in jsonData['sections']:
        startDate = each['startDate']
        endDate = each['endDate']
        
        if today >= parser.parse(startDate) and today <= parser.parse(endDate):
            currentSeasonType = int(each['value'])
            
    for each in favorites:
        teamId = team_names_to_id[each]
        
        url = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{teamId}/schedule'
        events = []
        for seasonType in ['1','2','3']:
            payload = {'seasontype':seasonType}
            jsonData = requests.get(url, params=payload).json()
            events += jsonData['events']
        
        url ='https://site.api.espn.com/apis/v2/sports/football/nfl/standings'
        standings = requests.get(url).json()
    
        teamData = jsonData['team']    
    
        teamAbbr = teamData['abbreviation']
        logo = teamData['logo']
    
        teamColorDark = team_colors[teamAbbr]['dark']
        teamColorLite = team_colors[teamAbbr]['lite']
    
        try:
            standingSummary = teamData['standingSummary']   
            if teamData['seasonSummary'] != currentSeason:
                raise ValueError("{teamData['seasonSummary']} not current {currentSeason} season")
        except:
            standingSummary = '99'
        #place = int(re.findall(r'\d+', standingSummary)[0])
        
        divStandings = requests.get('https://site.api.espn.com/apis/v2/sports/football/nfl/standings',
                                        params={'level': '3'}).json()
        place = find_division_place(divStandings, teamId)
        if place is None:
            place = int(re.findall(r'\d+', standingSummary)[0])
        
        placeOutputText = {1:'1st PLACE', 2:'2nd PLACE', 3:'3rd PLACE', 4:'4th PLACE', 5:'5th PLACE', 99:'PRESEASON'}
        place = placeOutputText[place]



    
        
        try:
            record = teamData['recordSummary']
            if teamData['seasonSummary'] != currentSeason:
                raise ValueError("{teamData['seasonSummary']} not current {currentSeason} season")
        except:
            url = f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{currentSeason}/types/{currentSeasonType}/teams/{teamId}/record'
            jsonData = requests.get(url).json()
            record = jsonData['items'][0]['summary']
        
        # Get Current season_type and week:
        url = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events'
        jsonData = requests.get(url).json()['$meta']['parameters']
        seasonType = jsonData['seasontypes'][0]
    
    
        for idx, game in enumerate(events):
            if game['competitions'][0]['status']['type']['state'] == 'pre':
                lastGameIdx = idx - 1
                nextGameIdx = idx
                live = False
                break
            
            else:
                lastGameIdx = idx
                nextGameIdx = None
                live = False
            
        for each in events[lastGameIdx]['competitions'][0]['competitors']:
            if events[lastGameIdx]['competitions'][0]['status']['type']['state'] == 'in':
                live = True
            if each['id'] == teamId:
                favoriteTeamScore = each['score']['displayValue']
                favoriteTeamHomeAway = each['homeAway']
                if favoriteTeamHomeAway == 'away':
                    lastHomeAway = '@'
                else:
                    lastHomeAway = 'VS'
            else:
                lastGameOpp = each['team']['abbreviation']
                oppTeamScore = each['score']['displayValue']
                
        if int(favoriteTeamScore) > int(oppTeamScore):
            winLoss = 'W' 
        elif int(favoriteTeamScore) < int(oppTeamScore):
            winLoss = 'L' 
        elif int(favoriteTeamScore) == int(oppTeamScore):
            winLoss = 'T' 
            
        if live == True:
            winLoss = '^'
    
        postSeason = True
        if nextGameIdx != None:
            endSeason = False
            for each in events[nextGameIdx]['competitions'][0]['competitors']:
                if each['id'] == teamId:
                    favoriteTeamHomeAway = each['homeAway']
                    if favoriteTeamHomeAway == 'away':
                        nextHomeAway = '@'
                    else:
                        nextHomeAway = 'VS'
                else:
                    nextGameOpp = each['team']['abbreviation']
                    if events[nextGameIdx]['seasonType']['type'] == 3:
                        nextGameText = events[nextGameIdx]['week']['text'].upper()
                        postSeason = True
                    else:
                        nextGameText = ''
                        postSeason = False
                        
                    
                    
        else:
            # Check if team eliminated
            for conf in standings['children']:
                for team in conf['standings']['entries']:
                    if team['team']['id'] == teamId:
                        for each in team['stats']:
                            if each['name'] == 'clincher':
                                nextGameText = each['description']
                                if each['displayValue'] == 'e':
                                    endSeason = True
                                else:
                                    endSeason = False
                                break





                    

        if nextGameText == '' and postSeason == False:
            d = parser.isoparse(events[nextGameIdx]['date'])  
            d = d.astimezone(pytz.timezone(timeZone))
            nextGameDate = d.strftime('%b %d')
            nextGameTime = d.strftime('%I:%M').lstrip("0")
            nextGameTime = d.strftime('%I:%M %p').lstrip("0")
            
        elif postSeason == True and endSeason == False:
            try:
                d = parser.isoparse(events[nextGameIdx]['date'])  
                d = d.astimezone(pytz.timezone(timeZone))
                nextGameDate = d.strftime('%b %d')
                nextGameTime = d.strftime('%I:%M').lstrip("0")
                nextGameTime = d.strftime('%I:%M %p').lstrip("0")
            except:
                nextGameDate = ''
                nextGameTime = ''
                nextGameOpp = ''
                nextHomeAway = ''
  
        elif endSeason == True:
            nextGameDate = ''
            nextGameTime = ''
            nextGameOpp = ''
            nextHomeAway = ''
                

            
        
        team_summary_data = {
            'logo':logo,
            'team': teamAbbr,
            'teamColorDark': '#'+teamColorDark,
            'teamColorLite': '#'+teamColorLite,
            'place':place,
            'record':record,
            'lastGameOpp': f'{lastHomeAway} {lastGameOpp}',
            'lastGameOutcome':f'{winLoss}',
            'lastGameScore': f'{favoriteTeamScore}-{oppTeamScore}',
            'nextGameDate': f'{nextGameDate}',
            'nextGameTime': f'{nextGameTime}',
            'nextGameOpp': f'{nextHomeAway} {nextGameOpp}',
            'nextGameText': nextGameText,
            'postSeason':postSeason,
            'endSeason':endSeason}
            
     
        x, y = (0,0) 
        while True:
            team_summary = render.team_summary(team_summary_data, display_width, display_height, x, y)  
            matrix.SetImage(team_summary.convert('RGB'), 0,0 ) 
            #print(y)
            if y in [0, -21, -43]:
                time.sleep(6)
            time.sleep(0)
            y-=1
            if y == (-43):
                break
    
        #print('done')    
        time.sleep(6)    
    

    
    
        
    








