import os

from dotenv import load_dotenv
from instabot import Bot

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

bot = Bot()
username = os.environ['IG_USERNAME']
password = os.environ['IG_PASSWORD']
image_path = "1_10_Albert_Einstein_Quote_031.jpg"

bot.login(username=username, password=password)
bot.upload_photo(image_path, caption='')
bot.logout()
