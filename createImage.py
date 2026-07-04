from PIL import Image, ImageDraw, ImageFont

# Create a white image
width, height = 1080, 1080
background_color = (255, 255, 255)
image = Image.new('RGB', (width, height), background_color)

# Create a drawing context
draw = ImageDraw.Draw(image)

# Specify the font and text to write
font_size = 100
font = ImageFont.truetype('angelina.TTF', font_size)  # You may need to specify a different font file path
text = '''        New day's first sunrise,
        Awakens hope deep inside,
        Embrace life's surprise.'''

# Calculate text size and position
text_width, text_height = draw.textsize(text, font)
x = (width - text_width) / 2
y = (height - text_height) / 2

# Text color
text_color = (0, 0, 0)  # Black

# Write the text on the image
draw.text((-70, 300), text, fill=text_color, font=font)

# Save the image as a JPEG
image.save('output.jpg')

# Close the image
image.close()

print("Image created and text added.")
