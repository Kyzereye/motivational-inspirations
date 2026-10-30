import os
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Merriweather-Regular.ttf')
WIDTH, HEIGHT = 1080, 1080
MARGIN = 100
BACKGROUND_COLOR = (255, 255, 255)  # White
TEXT_COLOR = (0, 0, 0)  # Black
LINE_SPACING = 20
AUTHOR_GAP = 50


def block_size(draw, text, font):
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=LINE_SPACING)
    return right - left, bottom - top


def wrap_to_width(draw, text, font, max_width):
    """Wrap text at the widest character count whose lines still fit in max_width."""
    for chars in range(len(text), 0, -1):
        wrapped = '\n'.join(textwrap.fill(line, width=chars) for line in text.splitlines())
        if block_size(draw, wrapped, font)[0] <= max_width:
            return wrapped
    return text


def create_image(quote, author, out_path):
    image = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    max_width = WIDTH - 2 * MARGIN
    max_height = HEIGHT - 2 * MARGIN
    author_text = f'— {author}' if author else ''

    # Shrink the font until the quote and author fit inside the margins
    for font_size in range(72, 23, -4):
        quote_font = ImageFont.truetype(FONT_PATH, font_size)
        author_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.7))
        quote_text = wrap_to_width(draw, quote, quote_font, max_width)
        quote_w, quote_h = block_size(draw, quote_text, quote_font)
        author_w, author_h = block_size(draw, author_text, author_font) if author_text else (0, 0)
        total_h = quote_h + (AUTHOR_GAP + author_h if author_text else 0)
        if quote_w <= max_width and total_h <= max_height:
            break

    # Center the quote and author together as one block
    y = (HEIGHT - total_h) / 2
    draw.multiline_text((WIDTH / 2, y), quote_text, fill=TEXT_COLOR, font=quote_font,
                        anchor='ma', align='center', spacing=LINE_SPACING)
    if author_text:
        draw.text((WIDTH / 2, y + quote_h + AUTHOR_GAP), author_text, fill=TEXT_COLOR,
                  font=author_font, anchor='ma')

    image.save(out_path)
    image.close()


if __name__ == '__main__':
    if len(sys.argv) == 4:
        create_image(sys.argv[1], sys.argv[2], sys.argv[3])
        print(f'Image created: {sys.argv[3]}')
    else:
        create_image("New day's first sunrise,\nAwakens hope deep inside,\nEmbrace life's surprise.", '', 'output.jpg')
        print('Image created: output.jpg')
