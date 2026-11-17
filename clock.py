# -*- coding: utf-8 -*-
"""
Created on Sat Jan  8 09:53:36 2022

@author: Jason
"""

import time

import datetime

import espn_api

import render

from dateutil import parser
import pytz

import team_color_config

import scoreboard_logo_config 
layout_team_pregame = scoreboard_logo_config.layout_team_pregame

favorites = ['Bears']
team_ids, team_names_to_id = espn_api.get_team_ids()

teamColor = team_color_config.team_colors[team_ids[team_names_to_id[favorites[0]]]]['clock']

timeZone = 'US/Central'
timeZone = 'Europe/London'

def run_clock(matrix, display_width, display_height):

    count = 0
    while True:
        second = count % 2
    
        # Get Date and Time
        now = datetime.datetime.now()
        d = parser.isoparse(str(now))
        d = d.astimezone(pytz.timezone(timeZone))
        
        dateStr = d.strftime('%b %d %Y')
        hrStr = d.strftime('%I')
        minStr = d.strftime('%M')
        am_pm = d.strftime('%p')
        
        #hrStr = '07'
        #minStr = '07'
        
        if second == 0:
            timeStr = hrStr + ':' + minStr
        else:
            timeStr = hrStr + ' ' + minStr
        
        data = {
                'dateStr':dateStr,
                'hrStr':hrStr,
                'minStr':minStr,
                'timeStr':timeStr,
                'am_pm':am_pm,
                'teamColor':'#' + teamColor}
        
        clock = render.clock(data, display_width, display_height)  
        matrix.SetImage(clock.convert('RGB'), 0,0 ) 
        
        count += 1
        time.sleep(1)
        
        if count == 21:  # change to 21
            break


















