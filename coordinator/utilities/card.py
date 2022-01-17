import random

from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

class Card:

    FONTS = [
        font_manager.findfont(font_manager.FontProperties(family = 'sans-serif', style = 'normal', weight = 'normal')),
        font_manager.findfont(font_manager.FontProperties(family = 'sans-serif', style = 'italic', weight = 'normal')),
        font_manager.findfont(font_manager.FontProperties(family = 'sans-serif', style = 'normal', weight = 'medium')),
        font_manager.findfont(font_manager.FontProperties(family = 'serif', style = 'normal', weight = 'normal')),
        font_manager.findfont(font_manager.FontProperties(family = 'serif', style = 'italic', weight = 'normal')),
        font_manager.findfont(font_manager.FontProperties(family = 'serif', style = 'normal', weight = 'medium')),
    ]
    IMG_SIZE = settings.CARD_GENERATED_IMAGE_SIZE
    NOISE_LEVEL = settings.CARD_GENERATED_IMAGE_NOISE_LEVEL
    ROTATE_MAX_ANGLE = settings.CARD_GENERATED_IMAGE_ROTATE_MAX_ANGLE

    def __init__(self, rank):
        self.rank = rank

    def get_image(self, noise_level = None):
        if noise_level is None:
            noise_level = Card.NOISE_LEVEL
        if not 0 <= noise_level <= 1:
            raise ValueError(f"Invalid noise level: {noise_level}, value must be between zero and one")

        # Create rank image from text
        text = self.rank[0]  # Extract letter to write
        font = ImageFont.truetype(random.choice(self.FONTS), size = Card.IMG_SIZE - 6)  # Pick a random font
        img = Image.new('L', (Card.IMG_SIZE, Card.IMG_SIZE), color = 255)
        draw = ImageDraw.Draw(img)
        (text_width, text_height) = draw.textsize(text, font = font)  # Extract text size
        draw.text(((Card.IMG_SIZE - text_width) / 2, (Card.IMG_SIZE - text_height) / 2 - 4), text, fill = 0, font = font)

        # Random rotate transformation
        img = img.rotate(random.uniform(-Card.ROTATE_MAX_ANGLE, Card.ROTATE_MAX_ANGLE), expand = False, fillcolor = '#FFFFFF')
        pixels = list(img.getdata())  # Extract image pixels

        # Introduce random noise
        for (i, _) in enumerate(pixels):
            if random.random() <= noise_level:
                pixels[i] = random.randint(0, 255)  # Replace a chosen pixel with a random intensity

        # Save noisy image
        noisy_img = Image.new('L', img.size)
        noisy_img.putdata(pixels)

        return noisy_img
