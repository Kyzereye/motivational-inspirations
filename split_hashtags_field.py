#!/usr/bin/env python3
"""One-off migration: split list/captions.json's combined `caption` string
(body + blank line + hashtag line) into separate `caption` (body only) and
`hashtags` (list) fields. Pure structural split — does not recompute tags,
since resync_hashtags.py already brought them up to date with the current
DISCOVERY_POOLS this session.

Handles the common case (clean blank-line separator) and a fallback for
captions where hashtags were glued directly onto the body with no separator
(found 3 such cases this session, one with a stray trailing backtick).
"""
import re

from caption_lib import load_captions, save_captions

BASE_DIR = '.'

TRAILING_HASHTAGS_RE = re.compile(r'((?:#\w+[\s`]*)+)$')


def split_caption(caption):
    """Returns (body, hashtags_list)."""
    parts = caption.split('\n\n')
    if len(parts) >= 2:
        last = parts[-1].strip()
        tokens = last.split()
        if tokens and all(t.startswith('#') for t in tokens):
            body = '\n\n'.join(parts[:-1])
            return body, tokens

    match = TRAILING_HASHTAGS_RE.search(caption)
    if match:
        hashtags = re.findall(r'#\w+', match.group(1))
        if hashtags:
            body = caption[:match.start()].rstrip()
            return body, hashtags

    return caption, []


def main():
    captions = load_captions(BASE_DIR)

    migrated, already_done, no_hashtags_found = [], [], []
    for filename, entry in captions.items():
        if 'hashtags' in entry:
            already_done.append(filename)
            continue
        caption = (entry.get('caption') or '').strip()
        if not caption:
            entry['hashtags'] = []
            continue

        body, hashtags = split_caption(caption)
        entry['caption'] = body
        entry['hashtags'] = hashtags
        if hashtags:
            migrated.append(filename)
        else:
            no_hashtags_found.append(filename)

    save_captions(captions, BASE_DIR)

    print(f'Migrated: {len(migrated)}')
    print(f'Already had hashtags field (skipped): {len(already_done)}')
    if no_hashtags_found:
        print(f'No hashtags found at all (left caption as full text, hashtags=[]):')
        for filename in no_hashtags_found:
            print(f'  {filename}')


if __name__ == '__main__':
    main()
