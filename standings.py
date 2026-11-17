# -*- coding: utf-8 -*-
"""
Created on Thu Jan  6 20:14:10 2022

@author: Jason
"""

import time

import espn_api

import render

import team_color_config 

team_ids, team_names_to_id = espn_api.get_team_ids()
team_colors = team_color_config.team_colors

preferences = ['NFL', 'AFC', 'NFC', 
               'NFC NORTH', 'NFC SOUTH', 'NFC EAST', 'NFC WEST',
               'AFC NORTH', 'AFC SOUTH', 'AFC EAST', 'AFC WEST']
preferences = ['NFC', 'AFC', 'NFC NORTH']


def run_standings(matrix, display_width, display_height):

    standings_data = espn_api.get_standings(preferences)
            
      
    for standings_title in preferences:
        data = standings_data[standings_title]
        data_length = abs((((len(data)+1) * 7) - display_height))
        x, y = (0,0) 
        while True:
            standings, placement = render.standings(standings_title, data, display_width, display_height, x, y)  
            matrix.SetImage(standings.convert('RGB'), 0,0 ) 
            
            if y in [0, -7, -35, -63, -91, -119, -147, -175,  ]:
                time.sleep(6)
            time.sleep(0)
                   
            if abs(y) == data_length + 4:
                break
            y-=1
            
        time.sleep(5)










