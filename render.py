# -*- coding: utf-8 -*-
"""
Created on Wed Dec 22 14:55:06 2021

@author: Jason
"""
from PIL import Image
from PIL import ImageDraw, ImageFilter

from io import BytesIO
import requests

import datetime
import math

import scoreboard_logo_config
import team_summary_logo_config
import team_color_config 
from fonts import font_04B_24__8, font_04B_24__24, font_score_large_16
import os
from paths import LOGO_DIR
import load_static_data

def text_size(draw, text, font=None):
    """Width and height of text, like the old draw.textsize() (removed in Pillow 10).

    Newer Pillow: measured with textbbox. Older Pillow (like the Pi's) can't use
    textbbox with the built-in default font, so fall back to font.getsize() there.
    """
    font = font or draw.getfont()
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right, bottom
    except ValueError:
        return font.getsize(text)


def load_logo(abbreviation):
    """Load a team logo from assets/logos.

    If the file is missing, run load_static_data.load() (which downloads any
    missing logos, using LOGO_OVERRIDES) and try again. If it still can't be
    loaded, return an empty image so the screen still draws without the logo.
    """
    path = os.path.join(LOGO_DIR, f'{abbreviation}.png')
    if not os.path.isfile(path):
        print(f'Logo missing for {abbreviation}, downloading')
        try:
            load_static_data.load()
        except Exception as e:
            print(f'Logo download failed: {e}')
    try:
        return Image.open(path)
    except Exception as e:
        print(f'Could not load logo for {abbreviation}: {e}')
        return Image.new('RGBA', (1, 1), (0, 0, 0, 0))

def add_carousel_dots(image, position, total):
    """Row of dots along the bottom showing which game of `total` is on screen
    (position is 1-based, current game in red). Nothing is drawn for a single game."""
    if total <= 1:
        return image
    width, height = image.size
    draw = ImageDraw.Draw(image)
    draw.rectangle([math.floor(width/2 - total), height - 4,
                    math.ceil(width/2 + total), height - 2], fill='black')
    count_dot = 0
    for i, x in enumerate(range(math.floor(width/2 - total), math.ceil(width/2 + total))):
        if (i % 2) == 1:
            draw.point((x, height - 3), fill='white')
            count_dot += 1
            if count_dot == position:
                draw.point((x, height - 3), fill='red')
    return image


def scoreboard(data, display_width, display_height, team_ids):
    
    # Load logo layout based on if it's a pre/post game display or live in progress game
    if data['scoreboard_type'] in ['pre', 'post']:
        config = scoreboard_logo_config.layout_team_pregame
    elif data['scoreboard_type'] in ['in']:
        config = scoreboard_logo_config.layout_team_live
        
    
    #Create blank canvas to construct scoreboard image/view
    canvas = Image.new('RGB', (display_width, display_height), "black")

    # Load each team logo, process, and position onto scoreboard from config
    # based on game status type (pre, live, post, other)
    for team in data['homeAway'].items():
        zoom = config[team[1]['team']]['zoom'] # adjusts logo display size
        position = config[team[1]['team']]['position'][team[0]] # adjusts log x,y position based on if away/home   
        
        logo_image = load_logo(team[1]['team'])
        logo_image.thumbnail((display_width*zoom, display_height*zoom))
        
        canvas.paste(logo_image, position)
        
    mask = Image.new("RGBA", canvas.size, 0)
    bg = Image.new('RGBA', (display_width, display_height), "black")
    draw = ImageDraw.Draw(bg)
    draw.rectangle([0, 0 , canvas.width, canvas.height], fill='black')
    
    # Scoreboard - center align gradient to left and right
    draw = ImageDraw.Draw(mask)
    if data['scoreboard_type'] in ['pre', 'post']:
        left_edge = .25
        right_edge = .72
    else:
        left_edge = .5
        right_edge = .5
        
    draw.rectangle([0, 0 , math.ceil(canvas.width * left_edge), canvas.height], fill='white')
    draw.rectangle([math.floor(canvas.width* right_edge), 0 , canvas.width, canvas.height], fill='white')
    mask_blur = mask.filter(ImageFilter.GaussianBlur(2))
    
    scoreboard = Image.composite(canvas, bg, mask_blur)
    
    draw = ImageDraw.Draw(scoreboard)
    
    if data['scoreboard_type'] == 'pre':
        if datetime.datetime.now().strftime('%m.%d') == data['gameDate']:
            gameDate_text = 'TODAY'
        else:
            gameDate_text = data['gameDate']
        w, h = text_size(draw, gameDate_text)
        draw.text((((display_width)/2 ), 4), gameDate_text, font = font_04B_24__8, anchor="mm") 
        draw = ImageDraw.Draw(scoreboard)
        gameTime_text = data['gameTime']
        w, h = text_size(draw, gameTime_text)
        draw.text((((display_width)/2 ), 10), gameTime_text, font = font_04B_24__8, anchor="mm") 
        
        draw = ImageDraw.Draw(scoreboard)
        text = 'VS'
        w, h = text_size(draw, text)
        draw.text((((display_width)/2 ), scoreboard_logo_config.final_score_position), text, font = font_score_large_16, anchor="mm") 
    elif data['scoreboard_type'] == 'post':
        text = 'FINAL'
        w, h = text_size(draw, text)
        draw.text((((display_width)/2 ), 4), text, font = font_04B_24__8, anchor="mm")         
        
        awayScore = data['homeAway']['away']['score']
        homeScore = data['homeAway']['home']['score']
        
        draw = ImageDraw.Draw(scoreboard)
        score_text = '{0}-{1}'.format(awayScore, homeScore)
        w, h = text_size(draw, score_text)
        if w > 0:
            # blur around 
            canvas = Image.new('RGB', (display_width, display_height), "black")
            mask = Image.new("L", scoreboard.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([math.floor(display_width/2 - w/2) - 6, 
                            math.floor(scoreboard_logo_config.final_score_position - h/2) -4 , 
                            math.ceil(display_width/2 + w/2 + 4), 
                            math.ceil(scoreboard_logo_config.final_score_position + h/2) + 4], 
                           fill=255, radius=7)
            mask_blur = mask.filter(ImageFilter.GaussianBlur(2))
            scoreboard = Image.composite(canvas, scoreboard, mask_blur)

        draw = ImageDraw.Draw(scoreboard)
        draw.text((((display_width)/2 ), scoreboard_logo_config.final_score_position), score_text, font = font_score_large_16, anchor="mm") 

        
    elif data['scoreboard_type'] == 'in':
        if data['isHalftime'] == True:
            quarter = 'HALF'
            draw.text((((display_width)/2 ), 4), quarter, font = font_04B_24__8, anchor="mm") 
            team_possession_home_away = ''
            
        else:
            quarter = data['quarter']
            outputText = {1:'1st', 2:'2nd', 3:'3rd', 4:'4th'}
            try:
                quarter = outputText[quarter]
            except:
                quarter = 'OT'
            w, h = text_size(draw, quarter)
            draw.text((((display_width)/2 ), 4), quarter, font = font_04B_24__8, anchor="mm")            
            
            #If not halftime
            time_remaining = data['timeRemaining']
            w, h = text_size(draw, time_remaining)
            draw.text((((display_width)/2 ), 10), time_remaining, font = font_04B_24__8, anchor="mm") 
            
            try:
                team_possession = team_ids[data['teamPossession']]
                team_possession_home_away = data['teamPossessionHomeAway']
            except:
                team_possession = ''
                team_possession_home_away = ''
            w, h = text_size(draw, team_possession)
            
            down = data['down']
            yards_to_go = data['yardsToGo']
            if down == 4:
                textColor = 'yellow'
            else:
                textColor = 'white'
            
            shortDownDistanceText = data['shortDownDistanceText']
            if 'goal' in shortDownDistanceText.lower():
                yards_to_go = 'G'
            downDistance = f'{down}&{yards_to_go}'
            if downDistance == '&':
                downDistance = ''
            draw.text((((display_width)/2 ), 17), downDistance, font = font_04B_24__8, anchor="mm", fill=textColor) 
            
            possessionText = data['possessionText']
            if data['isRedZone'] == True:
                textColor = 'red'
            else:
                textColor = 'white'
            draw.text((((display_width)/2 ), 23), possessionText, font = font_04B_24__8, anchor="mm", fill=textColor) 
            
            
        awayScore = data['homeAway']['away']['score']
        homeScore = data['homeAway']['home']['score']
        
        text = awayScore
        if team_possession_home_away == 'away':
            w, h = text_size(draw, text)
            pos_loc = (math.floor((display_width)* .20 ) - (w/2)) - 3
            draw.ellipse((pos_loc-2, 25-1, pos_loc+2, 25+1), fill='#5a2c00') 
        draw.text((math.ceil((display_width)* .20 ), 25), text, font = font_score_large_16, anchor="mm", fill='white') 

        text = homeScore
        if team_possession_home_away == 'home':
            w, h = text_size(draw, text)
            pos_loc = (math.floor((display_width)* .80 ) + (w/2)) + 3
            draw.ellipse((pos_loc-2, 25-1, pos_loc+2, 25+1), fill='#5a2c00') 
        draw.text((((display_width)* .80 ), 25), text, font = font_score_large_16, anchor="mm", fill='white') 
        
    return scoreboard
    

    
def team_summary(data, display_width, display_height, x, y):
    
    canvas = Image.new('RGB', (display_width, display_height), "black")
    
    # Load specific team logo, process, and position onto scoreboard from config
    config = team_summary_logo_config.layout_team_summary
    zoom = config[data['team']]['zoom'] # adjusts logo display size
    position = config[data['team']]['position']
    
    logo_image = load_logo(data['team'])
    logo_image.thumbnail((display_width*zoom, display_height*zoom))
    
    canvas.paste(logo_image, position)
    
    mask = Image.new("RGBA", canvas.size, 0)
    bg = Image.new('RGBA', (display_width, display_height), "black")
    draw = ImageDraw.Draw(bg)
    draw.rectangle([0, 0 , canvas.width, canvas.height], fill='black')
    
    # Scoreboard - center align gradient to left and right
    draw = ImageDraw.Draw(mask)

    right_edge = .60

        

    draw.rectangle([math.floor(canvas.width* right_edge), 0 , canvas.width, canvas.height], fill='white')
    mask_blur = mask.filter(ImageFilter.GaussianBlur(2))
    
    team_summary = Image.composite(canvas, bg, mask_blur)
    
    
    
    # Render Text Data:
    draw = ImageDraw.Draw(team_summary)
    
    ### RECORD ###
    record_header = 'RECORD:'
    w, h = text_size(draw, record_header, font = font_04B_24__8)
    
    draw.rectangle([x, y , w+x, h+y], fill=data['teamColorLite'])
    draw.text((x+1, y+1), record_header, font = font_04B_24__8, fill=data['teamColorDark'] , anchor="lt") 
    
    ## {place}      2
    ## {record}     9-3
    draw.text((x, h+y+2), data['place'], font = font_04B_24__8, fill='white' , anchor="lt") 
    draw.text((x, h+y+8), data['record'], font = font_04B_24__8, fill='white' , anchor="lt") 
    
    ### LAST GAME ###
    last_game_header = 'LAST GAME:'
    w, h = text_size(draw, last_game_header, font = font_04B_24__8)
    
    draw.rectangle([x, h+y+15 , w+x, h+y+15+h], fill=data['teamColorLite'])
    draw.text((x+1, h+y+16), last_game_header, font = font_04B_24__8, fill=data['teamColorDark'] , anchor="lt")  
    
    
    # @/VS Opp
    draw.text((x, h+y+23), data['lastGameOpp'], font = font_04B_24__8, fill='white' , anchor="lt") 
    w, h = text_size(draw, data['lastGameOpp'], font = font_04B_24__8)
    additionaTextPos = x+w+1
    
    if data['lastGameOutcome'] == 'W':
        color = 'green'
        additionalText = ''
    elif data['lastGameOutcome'] == 'L':
        color = 'red'
        additionalText = ''
    elif data['lastGameOutcome'] == 'T':
        color = 'yellow'
        additionalText = ''
    elif data['lastGameOutcome'] == '^':
        color = 'green'
        additionalText = 'LIVE'
        
    w, h = text_size(draw, data['lastGameOutcome'], font = font_04B_24__8)
    draw.text((x, h+y+29), data['lastGameOutcome'], font = font_04B_24__8, fill=color , anchor="lt") 
    draw.text((x+w+1, h+y+29), data['lastGameScore'], font = font_04B_24__8, fill='white' , anchor="lt") 
    

    if additionalText == 'LIVE':
        draw.text((additionaTextPos, h+y+23), additionalText, font = font_04B_24__8, fill=color , anchor="lt") 
        
    
    ### NEXT GAME ###
    next_game_header = 'NEXT GAME:'
    w, h = text_size(draw, next_game_header, font = font_04B_24__8)
    
    draw.rectangle([x, h+y+36 , w+x, h+y+36+h], fill=data['teamColorLite'])
    draw.text((x+1, h+y+37), next_game_header, font = font_04B_24__8, fill=data['teamColorDark'] , anchor="lt")   

    if data['postSeason'] == False:
        #draw.text((x, h+y+44), data['nextGameText'], font = font_04B_24__8, fill='green' , anchor="lt") 
        draw.text((x, h+y+44), data['nextGameDate'], font = font_04B_24__8, fill='white' , anchor="lt") 
        draw.text((x, h+y+50), data['nextGameTime'], font = font_04B_24__8, fill='white' , anchor="lt") 
        draw.text((x, h+y+56), data['nextGameOpp'], font = font_04B_24__8, fill='white' , anchor="lt") 

    elif data['postSeason'] == True and data['endSeason'] == True:
        textSplit = data['nextGameText'].split()
        textSplit = [x.upper() for x in textSplit]
        initialY = 44
        for eachText in textSplit:
            draw.text((x, h+y+initialY), eachText, font = font_04B_24__8, fill='white' , anchor="lt") 
            initialY += 6

    elif data['postSeason'] == True and data['endSeason'] == False and data['nextGameDate'] == '':
        textSplit = data['nextGameText'].split()
        textSplit = [x.upper() for x in textSplit]
        initialY = 44
        for eachText in textSplit:
            draw.text((x, h+y+initialY), eachText, font = font_04B_24__8, fill='white' , anchor="lt") 
            initialY += 6

    elif data['postSeason'] == True and data['endSeason'] == False and data['nextGameDate'] != '':
        draw.text((x, h+y+44), data['nextGameText'], font = font_04B_24__8, fill='green' , anchor="lt") 
        draw.text((x, h+y+50), data['nextGameDate'], font = font_04B_24__8, fill='white' , anchor="lt") 
        draw.text((x, h+y+56), data['nextGameTime'], font = font_04B_24__8, fill='white' , anchor="lt") 
        draw.text((x, h+y+62), data['nextGameOpp'], font = font_04B_24__8, fill='white' , anchor="lt") 
    

    
    return team_summary


def standings(standings_title, data, display_width, display_height, x, y):
    standings = Image.new('RGB', (display_width, display_height), "black")
    draw = ImageDraw.Draw(standings)

    if standings_title in ['NFL', 'AFC', 'NFC']:
        add_on_text = ' STANDINGS'
    else:
        add_on_text = ''
    header = standings_title + add_on_text
    w, h = text_size(draw, '---', font = font_04B_24__8)
    
    draw.text((x+1, y+1), header, font = font_04B_24__8, fill='white' , anchor="lt") 
    
    team_color = team_color_config.team_colors
    
    y1 = 7
    y2 = 13
    for row, team in enumerate(data, start=1):
        bg_color = '#' + team_color[team['team']]['lite']
        text_color = '#' + team_color[team['team']]['dark']
        teamName = team['team']
        teamRecord = team['overall']
        streak = team['streak']
        try:
            clincher = team['clincher']
            if clincher == 'e':
                color = 'red'
            else:
                color = 'green'
        except:
            clincher = ''
            color = 'white'
        draw.rectangle([x, y+(y1*row) , w+x, y+(y2*row)], fill=bg_color)
        draw.text((x+1, y+(y1*row+1)), teamName, font = font_04B_24__8, fill=text_color , anchor="lt")  
        draw.text((x+15, y+(y1*row+1)), clincher, font = font_04B_24__8, fill=color , anchor="lt")  
        
        draw.text((x+20, y+(y1*row+1)), teamRecord, font = font_04B_24__8, fill='white' , anchor="lt")  
        draw.text((64, y+(y1*row+1)), streak, font = font_04B_24__8, fill='white' , anchor="rt")  
        
    draw.rectangle([x, y+(y1*(row+1)) , w+x, y+(y2*(row+1))], fill='black')
        
    return standings, y+(y1*row)


def clock(data, display_width, display_height):
    
    clock = Image.new('RGB', (display_width, display_height), "black")
    
    draw = ImageDraw.Draw(clock)
    
    draw.text((8, 6), data['dateStr'], font = font_04B_24__8, fill='white' , anchor="lt") 
    #draw.text((8, 12), data['hrStr'], font = font_04B_24__24, fill='white' , anchor="lt") 
    
    w, h = text_size(draw, data['timeStr'], font = font_04B_24__24)
    draw.text((8, 12), data['timeStr'], font = font_04B_24__24, fill=data['teamColor'] , anchor="lt") 
    
    am_pm_pos = 8/2 + w + 2
    draw.text((am_pm_pos, 12), data['am_pm'][0], font = font_04B_24__8, fill='white' , anchor="lt") 
    draw.text((am_pm_pos, 18), data['am_pm'][1], font = font_04B_24__8, fill='white' , anchor="lt") 
    
    
    return clock
    
def playoff_logo(playoff_url, display_width, display_height):
    #Create blank canvas to construct scoreboard image/view
    canvas = Image.new('RGB', (display_width, display_height), "black")        
    
    response = requests.get(playoff_url)
    image_bytes = BytesIO(response.content)
    logo_image = Image.open(image_bytes)
    logo_image.thumbnail((display_width, display_height))
    
    w, h = logo_image.size
    
    center_w = int((display_width - w)/2)
    center_h = int((display_height - h)/2)
        
    canvas.paste(logo_image, (center_w, center_h)) 
    
    return canvas