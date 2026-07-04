import os

import facebook as fb
from dotenv import load_dotenv

# from autoPostIG import post_on_ig

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

access_token = os.environ['FB_ACCESS_TOKEN']
page_id = os.environ['FB_PAGE_ID']
asafb = fb.GraphAPI(access_token)
queue = os.path.join(os.path.dirname(__file__), 'list', 'queue.txt')
posted_log = os.path.join(os.path.dirname(__file__), 'list', 'posted_log.txt')

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
image_path = os.path.join(os.path.dirname(__file__), 'images', posted_image)
asafb.put_photo(image=open(image_path, "rb"), message="")
# post_on_ig(image_path)
