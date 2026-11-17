import os
from PIL import ImageFont
from paths import FONT_DIR

font_04B_24__8 = ImageFont.truetype(os.path.join(FONT_DIR, '04B_24__.TTF'), 8)
font_04B_24__24 = ImageFont.truetype(os.path.join(FONT_DIR, '04B_24__.TTF'), 24)
font_score_large_16 = ImageFont.truetype(os.path.join(FONT_DIR, 'score_large.otf'), 16)
