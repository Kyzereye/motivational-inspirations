import hashlib
import json
import os
import re
from collections import OrderedDict

BRAND_TAGS = [
    '#InspirationalMotivation',
    '#KeepMovingForward',
    '#PositivelyMovingForward',
]

BRAND_PAIRS = [(0, 1), (1, 2), (0, 2), (2, 0), (1, 0), (2, 1)]

DISCOVERY_POOLS = {
    'love': ['#motivation', '#mindfulness', '#positivity', '#dailyinspiration'],
    'discipline': ['#discipline', '#motivation', '#selfgrowth', '#mindset'],
    'ownership': ['#leadership', '#mindset', '#selfgrowth', '#motivation'],
    'mindset': ['#mindset', '#motivation', '#selfgrowth', '#dailyinspiration'],
    'courage': ['#motivation', '#mindset', '#selfgrowth', '#dailyinspiration'],
    'growth': ['#selfgrowth', '#motivation', '#mindset', '#dailyinspiration'],
    'success': ['#motivation', '#motivationalquotes', '#mindset', '#selfgrowth'],
    'peace': ['#mindfulness', '#positivity', '#dailyinspiration', '#motivation'],
    'default': ['#motivation', '#dailyinspiration', '#motivationalquotes', '#quotes'],
}

THEME_KEYWORDS = {
    'love': (
        'love', 'kind', 'heart', 'compassion', 'god', 'spirit', 'forgive',
        'grace', 'care', 'generous',
    ),
    'discipline': (
        'grind', 'discipline', 'work', 'effort', 'commit', 'morning', 'habit',
        'consistent', 'practice', 'show up', 'dedicated', 'excuse', 'weakness',
    ),
    'ownership': (
        'stand behind', 'responsible', 'accountab', 'integrity',
        'reputation', 'word', 'promise', 'your name', 'name on it',
    ),
    'mindset': (
        'mind', 'think', 'belief', 'attitude', 'thought', 'perspective',
        'story', 'focus', 'doubt', 'priority', 'priorities', 'target',
        'clarity', 'choose', 'input',
    ),
    'courage': (
        'fear', 'brave', 'risk', 'courage', 'bold', 'leap', 'try', 'attempt',
    ),
    'growth': (
        'grow', 'learn', 'improve', 'better', 'change', 'progress', 'develop',
        'stretch', 'discomfort',
    ),
    'success': (
        'success', 'goal', 'win', 'achieve', 'excel', 'great', 'master',
        'excel', 'results',
    ),
    'peace': (
        'peace', 'calm', 'present', 'mindful', 'still', 'quiet', 'breathe',
        'patience', 'slow',
    ),
}

S1_BY_THEME = {
    'love': (
        'Love shows up in how you treat people when it costs you something.',
        'Kindness is a daily practice, not a mood you wait to feel.',
        'The standard is simple: lead with care before ego.',
    ),
    'discipline': (
        'Discipline is what keeps you moving when motivation fades.',
        'Structure on ordinary days builds a self you can trust.',
        'Follow-through matters more than how inspired you felt at the start.',
    ),
    'ownership': (
        'Reputation is built when you fix what breaks, not when everything looks fine.',
        'Your name means most when something goes wrong and you still show up.',
        'Integrity is measured in corrections made, not promises made.',
    ),
    'mindset': (
        'Your thoughts set the ceiling on what you will attempt today.',
        'A useful mindset turns pressure into a next step, not an excuse.',
        'What you repeat to yourself becomes the story you live out.',
    ),
    'courage': (
        'Courage is action taken while doubt is still in the room.',
        'Most progress starts before you feel ready to begin.',
        'Bold moves are often small moves taken without guarantee.',
    ),
    'growth': (
        'Growth is rarely comfortable while it is happening.',
        'One honest upgrade at a time beats waiting for a perfect restart.',
        'Progress belongs to people who keep going after the first setback.',
    ),
    'success': (
        'Results follow the standards you keep when no one is watching.',
        'Success here is alignment between what you say and what you repeat.',
        'Big outcomes are usually small choices stacked over time.',
    ),
    'peace': (
        'Peace is steadiness under pressure, not escape from responsibility.',
        'A quieter mind makes better decisions and softer reactions.',
        'Calm is a skill you practice, not a mood you stumble into.',
    ),
    'default': (
        'Small actions repeated honestly beat big intentions left undone.',
        'Inspiration only matters when it changes one choice you would skip.',
        'Progress starts when you stop waiting for the perfect moment.',
    ),
}

S2_BY_THEME = {
    'love': (
        'People feel it in patience, respect, and attention on hard days.',
        'That standard matters most when you are tired or feel wronged.',
        'Your daily choices widen or narrow the love you actually give.',
    ),
    'discipline': (
        'That is how momentum builds on days that feel uninspired.',
        'The win is trusting yourself when feelings would talk you out of it.',
        'Fewer excuses and more reps change what you believe you can do.',
    ),
    'ownership': (
        'People remember who made it right without waiting to be chased.',
        'Trust grows when you absorb the cost and tell the truth quickly.',
        'A strong name is an asset built one repair at a time.',
    ),
    'mindset': (
        'A small shift in framing can change what you attempt today.',
        'Useful thinking is a choice, not a personality trait.',
        'The story you accept today becomes the limit you respect tomorrow.',
    ),
    'courage': (
        'Waiting to feel ready is how important work gets delayed.',
        'The first step matters more than the perfect plan.',
        'Fear loses power when you move before it gives you permission.',
    ),
    'growth': (
        'You do not need a reinvention — just one real upgrade at a time.',
        'Discomfort often signals the edge where improvement begins.',
        'Keep going once; that is where most people stop.',
    ),
    'success': (
        'Let this filter where your time and energy go today.',
        'Alignment beats intensity when the work is long.',
        'What you repeat daily becomes the result you eventually get.',
    ),
    'peace': (
        'Respond instead of react when the pressure rises.',
        'Clearer decisions come when the noise in your head drops.',
        'Steadiness under load is a form of strength people notice.',
    ),
    'default': (
        'The benefit is what you do differently because you saw this today.',
        'Make the idea practical or it stays decoration in your feed.',
        'One better choice today is enough to move the needle.',
    ),
}

S3_BY_THEME = {
    'love': (
        'Today, give one person your full attention without correcting them.',
        'Today, answer irritation with respect before you defend yourself.',
        'Today, do one kindness you would normally skip when busy.',
    ),
    'discipline': (
        'Today, finish the first ten minutes of one task you have avoided.',
        'Today, protect twenty-five focused minutes for what matters most.',
        'Today, complete one non-negotiable action before distractions win.',
    ),
    'ownership': (
        'Today, fix one thing that has your name on it without delay.',
        'Today, close one loop you have been leaving open for someone else.',
        'Today, send the correction or message you have been putting off.',
    ),
    'mindset': (
        'Today, rewrite one negative story into a useful next step.',
        'Today, replace one complaint with the question: what is next?',
        'Today, take the smallest step your doubt keeps talking you out of.',
    ),
    'courage': (
        'Today, take the first step on one thing you have postponed.',
        'Today, do the feared task for five minutes and let momentum decide.',
        'Today, choose progress over comfort in one decision you control.',
    ),
    'growth': (
        'Today, practice one skill or habit for fifteen focused minutes.',
        'Today, ask for feedback and listen without defending yourself.',
        'Today, change one small routine that keeps you stuck.',
    ),
    'success': (
        'Today, protect ninety minutes for your single most important priority.',
        'Today, remove one distraction that steals your best energy.',
        'Today, finish one meaningful task before starting something new.',
    ),
    'peace': (
        'Today, take five quiet minutes with no phone before you decide.',
        'Today, count to three before you speak or send the sharp reply.',
        'Today, drop one commitment that drains more than it helps.',
    ),
    'default': (
        'Today, take one action that matches this idea, not just your mood.',
        'Today, write the next step and do it before you talk yourself out.',
        'Today, make one improvement your future self will notice.',
    ),
}

AUTHOR_RE = re.compile(r'^\d+_\d+_(.+?)_Quote_\d+\.(jpg|jpeg|png)$', re.IGNORECASE)
FOOTER_RE = re.compile(
    r'inspirational motivation|motivational inspiration|ownership|keep moving forward',
    re.IGNORECASE,
)


def seed_index(key, modulo):
    digest = hashlib.md5(key.encode('utf-8')).hexdigest()
    return int(digest, 16) % modulo


def parse_author_from_filename(filename):
    match = AUTHOR_RE.match(filename)
    if not match:
        return None
    return match.group(1).replace('_', ' ').strip()


def slug_to_title(filename):
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r'^[Nn]?\d+-', '', stem)
    stem = stem.replace('-', ' ').replace('_', ' ')
    return stem.strip().title()


def quote_body_for_theme(quote):
    quote = (quote or '').strip()
    if '\n' in quote:
        return quote.split('\n', 1)[1].strip()
    for separator in ('. ', ' — ', ' - '):
        if separator in quote:
            return quote.split(separator, 1)[1].strip()
    return quote


def detect_theme(text):
    lowered = (text or '').lower()
    best_theme = 'default'
    best_score = 0
    for theme, keywords in THEME_KEYWORDS.items():
        score = sum(1 for word in keywords if word in lowered)
        if score > best_score:
            best_score = score
            best_theme = theme
    return best_theme


def shorten_quote(quote, limit=110):
    quote = ' '.join((quote or '').split())
    if len(quote) <= limit:
        return quote
    return quote[: limit - 3].rstrip() + '...'


def pick_hashtags(filename, theme):
    seed = seed_index(filename, 1000)
    pair = BRAND_PAIRS[seed % len(BRAND_PAIRS)]
    brand = [BRAND_TAGS[pair[0]], BRAND_TAGS[pair[1]]]

    pool = DISCOVERY_POOLS.get(theme, DISCOVERY_POOLS['default'])
    first = pool[seed % len(pool)]
    second = pool[(seed // len(pool) + 1) % len(pool)]
    if second == first:
        second = pool[(seed // len(pool) + 2) % len(pool)]
    return brand + [first, second]


def build_caption(quote, filename, author=None):
    theme_source = quote_body_for_theme(quote)
    if not theme_source and author:
        theme_source = quote or ''
    theme = detect_theme(theme_source)
    seed = seed_index(filename, 1000)

    s1_options = S1_BY_THEME[theme]
    s2_options = S2_BY_THEME[theme]
    s3_options = S3_BY_THEME[theme]
    sentence1 = s1_options[seed % len(s1_options)]
    sentence2 = s2_options[(seed // 3) % len(s2_options)]
    sentence3 = s3_options[(seed // 7) % len(s3_options)]

    hashtags = pick_hashtags(filename, theme)
    body = f'{sentence1} {sentence2} {sentence3}'
    return f'{body}\n\n{" ".join(hashtags)}'


BANNED_CAPTION_PHRASE = 'The image states the idea'

CAPTION_THEME_MARKERS = {
    'ownership': (
        'Reputation is built when you fix what breaks',
        'Your name means most when something goes wrong',
        'Integrity is measured in corrections made',
        'A strong name is an asset',
    ),
    'peace': (
        'Peace is steadiness under pressure',
        'A quieter mind makes better decisions',
        'Calm is a skill you practice',
    ),
    'discipline': (
        'Discipline is what keeps you moving',
        'Structure on ordinary days builds',
        'Follow-through matters more than how inspired',
    ),
    'mindset': (
        'Your thoughts set the ceiling',
        'A useful mindset turns pressure',
        'What you repeat to yourself becomes',
    ),
    'courage': (
        'Courage is action taken while doubt',
        'Most progress starts before you feel ready',
        'Bold moves are often small moves',
    ),
    'growth': (
        'Growth is rarely comfortable',
        'One honest upgrade at a time',
        'Progress belongs to people who keep going',
    ),
    'success': (
        'Results follow the standards you keep',
        'Success here is alignment between',
        'Big outcomes are usually small choices',
    ),
    'love': (
        'Love shows up in how you treat people',
        'Kindness is a daily practice',
        'The standard is simple: lead with care',
    ),
    'default': (
        'Small actions repeated honestly',
        'Inspiration only matters when it changes',
        'Progress starts when you stop waiting',
        'Make the idea practical or it stays decoration',
        'The benefit is what you do differently',
        'One better choice today is enough',
    ),
}


def caption_theme(caption):
    for theme, markers in CAPTION_THEME_MARKERS.items():
        if any(marker in caption for marker in markers):
            return theme
    return None


def should_regenerate_caption(quote, caption):
    caption = (caption or '').strip()
    if not caption:
        return True
    if BANNED_CAPTION_PHRASE in caption:
        return True

    body = quote_body_for_theme(quote)
    quote_theme = detect_theme(body)
    cap_theme = caption_theme(caption)
    if cap_theme and cap_theme != quote_theme:
        return True
    if cap_theme == 'default' and quote_theme != 'default':
        return True
    return False


def captions_path(base_dir=None):
    base = base_dir or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'list', 'captions.json')


def load_captions(base_dir=None):
    path = captions_path(base_dir)
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def order_captions(data, base_dir=None):
    base = base_dir or os.path.dirname(os.path.abspath(__file__))
    backup_path = os.path.join(base, 'list', 'queue_backup.txt')
    order = []
    if os.path.exists(backup_path):
        with open(backup_path, encoding='utf-8') as handle:
            order = [line.strip() for line in handle if line.strip()]

    ordered = OrderedDict()
    for filename in order:
        if filename in data:
            ordered[filename] = data[filename]
    for filename, entry in data.items():
        if filename not in ordered:
            ordered[filename] = entry
    return ordered


def save_captions(data, base_dir=None):
    path = captions_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ordered = order_captions(data, base_dir)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def get_caption_for_image(filename, base_dir=None):
    try:
        data = load_captions(base_dir)
        entry = data.get(filename, {})
        if isinstance(entry, dict):
            return (entry.get('caption') or '').strip()
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return ''
