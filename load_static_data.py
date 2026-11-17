# -*- coding: utf-8 -*-
"""
Created on Fri Jan  7 15:22:08 2022

@author: Jason
"""

import os
import time
import requests
from PIL import Image
from io import BytesIO

import espn_api

from paths import LOGO_DIR

MAX_AGE_DAYS = 30   # re-download a logo once it's older than this

# Teams whose default logo doesn't show well on the matrix
LOGO_OVERRIDES = {
    'NYG': ('full', 'dark'),
    'NYJ': ('full', 'secondary_logo_on_black_color'),
    'LAR': ('full', 'secondary_logo_on_black_color'),
}



def logo_needs_update(logo_path, force=False):
    if force or not os.path.isfile(logo_path):
        return True
    age_days = (time.time() - os.path.getmtime(logo_path)) / 86400
    return age_days > MAX_AGE_DAYS


def get_json(url, attempts=3):
    for attempt in range(1, attempts + 1):
        try:
            return requests.get(url, timeout=5).json()
        except Exception as e:
            print(f'Attempt {attempt} failed for {url}: {e}')
    return None

def get_logo_url(logos, rel=('full', 'default')):
    """Return the href of the logo whose rel list matches `rel` exactly."""
    wanted = set(rel)
    for logo in logos:
        if set(logo.get('rel', [])) == wanted:
            return logo['href']
    return logos[0]['href'] if logos else None


def load(force=False):
    os.makedirs(LOGO_DIR, exist_ok=True)

    team_ids, _ = espn_api.get_team_ids()

    for team_id, abbreviation in team_ids.items():
        logo_path = os.path.join(LOGO_DIR, f'{abbreviation}.png')

        if not logo_needs_update(logo_path, force):
            continue

        data = get_json(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}')
        if data is None:
            print(f'Skipping {abbreviation}: could not reach ESPN')
            continue

        logos = data.get('team', {}).get('logos', [])
        if not logos:
            print(f'No logo found: {abbreviation}')
            continue

        try:
            rel = LOGO_OVERRIDES.get(abbreviation, ('full', 'default'))
            response = requests.get(get_logo_url(logos, rel), timeout=10)
            Image.open(BytesIO(response.content)).save(logo_path)
            print(f'Saved: {abbreviation}')
        except Exception as e:
            print(f'Failed to save {abbreviation}: {e}')