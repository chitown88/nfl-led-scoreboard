# -*- coding: utf-8 -*-
"""
Project paths, worked out relative to this file so the same code runs
on Windows (emulator) and on the Pi (real matrix).
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
LOGO_DIR = os.path.join(ASSETS_DIR, 'logos')
FONT_DIR = os.path.join(ASSETS_DIR, 'fonts')
