import json
import os
import time
from datetime import datetime

import facebook as fb
from dotenv import load_dotenv

from caption_lib import get_caption_for_image

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

access_token = os.environ['FB_ACCESS_TOKEN']
page_id = os.environ['FB_PAGE_ID']
asafb = fb.GraphAPI(access_token)
meta_user_token = os.environ.get('META_USER_ACCESS_TOKEN', '')
asafb_ig = fb.GraphAPI(meta_user_token) if meta_user_token else None
queue = os.path.join(BASE_DIR, 'list', 'queue.txt')
posted_log = os.path.join(BASE_DIR, 'list', 'posted_log.txt')
def log(message):
    print(f'{datetime.now().isoformat(timespec="seconds")} {message}')


def load_post_caption(filename):
    try:
        caption = get_caption_for_image(filename, BASE_DIR)
        if caption:
            return caption
        log(f'No caption for {filename}, posting image only')
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        log(f'Caption warning for {filename}: {exc}')
    return ''


def ig_enabled():
    return os.environ.get('IG_ENABLED', '0').lower() in ('1', 'true', 'yes')


def get_ig_account_id(graph, page_id):
    ig_id = os.environ.get('IG_BUSINESS_ACCOUNT_ID', '').strip()
    if ig_id:
        return ig_id

    page = graph.get_object(page_id, fields='instagram_business_account')
    ig_account = page.get('instagram_business_account')
    if not ig_account:
        raise ValueError('No Instagram account linked to this Facebook Page')
    return ig_account['id']


def get_photo_url(graph, photo_id):
    photo = graph.get_object(photo_id, fields='images')
    images = photo.get('images', [])
    if not images:
        raise ValueError(f'No public image URL returned for photo {photo_id}')
    return max(images, key=lambda img: img.get('width', 0) * img.get('height', 0))['source']


def wait_for_ig_container(ig_graph, container_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = ig_graph.get_object(container_id, fields='status_code')
        code = status.get('status_code')
        if code == 'FINISHED':
            return
        if code in ('ERROR', 'EXPIRED'):
            raise ValueError(f'Instagram container {code}')
        time.sleep(5)
    raise TimeoutError('Instagram container not ready in time')


def post_to_instagram(ig_graph, fb_graph, ig_account_id, photo_id, caption=''):
    image_url = get_photo_url(fb_graph, photo_id)
    container = ig_graph.put_object(
        ig_account_id,
        'media',
        image_url=image_url,
        caption=caption,
    )
    wait_for_ig_container(ig_graph, container['id'])
    return ig_graph.put_object(
        ig_account_id,
        'media_publish',
        creation_id=container['id'],
    )


with open(queue) as sl:
    lines = sl.readlines()
    lines = [line.rstrip() for line in lines]

posted_image = lines[0]
pI = open(posted_log, 'a')
pI.write(posted_image + '\n')

lines.pop(0)

if os.path.exists(queue):
    os.remove(queue)
else:
    print('File does not exist')

lL = open(queue, "a")

for x in lines:
    lL.write(x + "\n")

print(posted_image)
log(f'Starting post for {posted_image}')
caption = load_post_caption(posted_image)
image_path = os.path.join(BASE_DIR, 'images', posted_image)
with open(image_path, 'rb') as image_file:
    fb_result = asafb.put_photo(image=image_file, message=caption)
log(f'Posted to Facebook: {posted_image}')

if ig_enabled():
    if not asafb_ig:
        log('Instagram post failed: META_USER_ACCESS_TOKEN not set')
    else:
        try:
            ig_account_id = get_ig_account_id(asafb_ig, page_id)
            ig_result = post_to_instagram(asafb_ig, asafb, ig_account_id, fb_result['id'], caption=caption)
            log(f'Posted to Instagram: {ig_result.get("id", ig_result)}')
        except Exception as exc:
            log(f'Instagram post failed: {exc}')
