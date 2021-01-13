import random
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont


class Card:
    RANKS = ['J', 'Q', 'K']
    FONTS = font_manager.findSystemFonts(fontpaths = None, fontext = 'ttf')

    def __init__(self, rank):
        # Sanity check
        if rank not in self.RANKS:
            raise ValueError(f"Invalid rank: {rank}")

        self.rank = rank

    def get_image(self, noise_level):
        if not 0 <= noise_level <= 1:
            raise ValueError(f"Invalid noise level: {noise_level}, value must be between zero and one")

        # Create rank image from text
        text = self.rank[0]  # Extract letter to write
        font = ImageFont.truetype(random.choice(self.FONTS), size = 28)  # Pick a random font
        img = Image.new('L', (28, 28), color = 255)
        draw = ImageDraw.Draw(img)
        (text_width, text_height) = draw.textsize(text, font = font)  # Extract text size
        draw.text(((28 - text_width) / 2, (28 - text_height) / 2 - 3), text, fill = 0, font = font)  # Center and draw text
        pixels = list(img.getdata())  # Extract image pixels

        # Introduce random noise
        for (i, _) in enumerate(pixels):
            if random.random() <= noise_level:
                pixels[i] = random.randint(0, 255)  # Replace a chosen pixel with a random intensity

        # Save noisy image
        noisy_img = Image.new('L', img.size)
        noisy_img.putdata(pixels)

        return noisy_img
