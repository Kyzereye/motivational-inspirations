#!/usr/bin/env python3
"""Re-run after changing caption_lib.py's DISCOVERY_POOLS: recompute the
`hashtags` field for every entry that has a caption, using the current pools.
Pure local recomputation (pick_hashtags() is deterministic, no LLM call), so
this is free and instant regardless of how many captions exist, and applies
to already-posted history and still-queued items alike. Does not repost or
change anything already live on Facebook/Instagram — only updates local
list/captions.json records.

Now that hashtags are their own field (see split_hashtags_field.py), this is
a straight overwrite — no string-splitting needed.
"""
from caption_lib import (
    detect_theme,
    load_captions,
    pick_hashtags,
    quote_body_for_theme,
    save_captions,
)

BASE_DIR = '.'


def main():
    captions = load_captions(BASE_DIR)

    updated, unchanged = [], []
    for filename, entry in captions.items():
        if not (entry.get('caption') or '').strip():
            continue

        quote = entry.get('quote', '')
        theme = detect_theme(quote_body_for_theme(quote))
        new_tags = pick_hashtags(filename, theme)

        if entry.get('hashtags') != new_tags:
            entry['hashtags'] = new_tags
            updated.append(filename)
        else:
            unchanged.append(filename)

    save_captions(captions, BASE_DIR)

    print(f'Updated: {len(updated)}')
    print(f'Unchanged (already matched current pools): {len(unchanged)}')


if __name__ == '__main__':
    main()
