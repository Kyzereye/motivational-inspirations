#!/usr/bin/env python3
"""Write genuinely specific captions (not canned templates) for queue items that
have a quote but no caption, using Claude to engage with each quote's actual
content. Hashtags stay deterministic (caption_lib.pick_hashtags) and are
appended after the generated prose — hashtag strategy is a separate decision
(see trend research recommendation 0003), not bundled into this.

Same resilience pattern as backfill_quotes.py: large batches are chunked, a
failing chunk bisects to isolate the problem entry, and problem entries are
flagged (list/caption_flagged.json) and skipped on future runs until retried.
"""
import argparse
import html
import json
import os
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

from caption_lib import (
    detect_theme,
    load_captions,
    parse_author_from_filename,
    pick_hashtags,
    quote_body_for_theme,
    save_captions,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(BASE_DIR, 'list', 'queue.txt')
SCRATCH_PATH = os.path.join(BASE_DIR, '.caption_scratch.json')
REVIEW_PATH = os.path.join(BASE_DIR, 'caption_review.html')
FLAGGED_PATH = os.path.join(BASE_DIR, 'list', 'caption_flagged.json')
FLAGGED_REVIEW_PATH = os.path.join(BASE_DIR, 'caption_flagged.html')

DEFAULT_BATCH_SIZE = 25
DEFAULT_CHUNK_SIZE = 25
DEFAULT_MODEL = 'claude-sonnet-5'

FEW_SHOT = '''Example A:
Quote: "You cannot travel the path until you have become the path itself." — Buddha
Commentary:
This isn't about reaching some destination called peace or growth — it's about becoming the
kind of person for whom that destination is just where you already live. You don't follow
discipline forever; at some point you simply are disciplined. The goal stops being "out there"
the moment it's inside how you already move through the day.

Example B:
Quote: "To understand your fear is the beginning of really seeing." — Bruce Lee
Commentary:
Fear distorts things before you've even looked at them closely — it makes the thing seem bigger
and more permanent than it is. The moment you stop running from what scares you and actually
examine it, most of that power disappears. Not because the fear was fake, but because you
finally saw it clearly instead of through the panic.'''


def read_queue():
    with open(QUEUE_PATH, encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip()]


def load_flagged():
    if not os.path.exists(FLAGGED_PATH):
        return {}
    with open(FLAGGED_PATH, encoding='utf-8') as handle:
        return json.load(handle)


def save_flagged(flagged):
    os.makedirs(os.path.dirname(FLAGGED_PATH), exist_ok=True)
    with open(FLAGGED_PATH, 'w', encoding='utf-8') as handle:
        json.dump(flagged, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write('\n')


def flag_failure(filename, error):
    flagged = load_flagged()
    entry = flagged.get(filename, {'attempts': 0})
    entry['attempts'] = entry.get('attempts', 0) + 1
    entry['error'] = str(error)
    entry['last_attempt'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    flagged[filename] = entry
    save_flagged(flagged)


def unflag(filenames):
    flagged = load_flagged()
    changed = False
    for filename in filenames:
        if filename in flagged:
            del flagged[filename]
            changed = True
    if changed:
        save_flagged(flagged)


def pending_filenames(queue, captions, flagged, include_flagged=False):
    pending = []
    for filename in queue:
        entry = captions.get(filename, {})
        if not (entry.get('quote') or '').strip():
            continue  # no quote yet — that's backfill_quotes.py's job
        if (entry.get('caption') or '').strip():
            continue  # already has a caption
        if filename in flagged and not include_flagged:
            continue
        pending.append(filename)
    return pending


def build_prompt(batch, captions):
    lines = []
    for filename in batch:
        quote = (captions.get(filename, {}).get('quote') or '').strip()
        author = parse_author_from_filename(filename)
        lines.append(f'- {filename} | quote: {quote!r} | author: {author or "none"}')
    entries = '\n'.join(lines)

    return f'''You are writing Instagram/Facebook captions for a motivational quote page. The
quote is already visible as text in the image itself, and is also stored separately — it will be
shown before your commentary when the post goes out. Do not repeat or requote it. Your job is
only to add real value: genuine commentary, not restated decoration.

For each entry below, write 2-4 sentences of genuine commentary that engages with what THIS
SPECIFIC quote is actually saying — not a generic motivational filler that could be pasted under
any quote. Think about the actual idea in the quote (its wording, its implication, what it pushes
back against) and write something a thoughtful person would actually say about it. Vary your
approach entry to entry — do not reuse the same sentence structure or opening phrase across
different entries in this batch.

Avoid: restating or quoting the text in any form, generic "today, take one step" calls-to-action
unless genuinely the sharpest thing to say about that specific quote, corporate or preachy tone,
filler phrases like "In today's fast-paced world." Keep the commentary tight — 2-4 sentences, not
an essay. Do not add hashtags — those are added separately afterward.

{FEW_SHOT}

Entries to write captions for:
{entries}

When done, write a single JSON object to the exact path `{SCRATCH_PATH}` mapping each filename
above (exactly as given) to its commentary string only — no quote, no attribution line, just the
commentary, exactly like the examples. Write to no other file in this repository.'''


def run_claude(prompt, model):
    result = subprocess.run(
        ['claude', '-p', prompt, '--model', model, '--allowedTools', 'Read,Write'],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(f'claude exited with status {result.returncode}')


def merge_batch(batch, captions):
    if not os.path.exists(SCRATCH_PATH):
        raise RuntimeError(f'Expected output not found: {SCRATCH_PATH}')
    with open(SCRATCH_PATH, encoding='utf-8') as handle:
        results = json.load(handle)

    filled, empty = [], []
    for filename in batch:
        prose = (results.get(filename) or '').strip()
        if not prose:
            empty.append(filename)
            continue
        quote = captions.get(filename, {}).get('quote', '')
        theme = detect_theme(quote_body_for_theme(quote))
        hashtags = pick_hashtags(filename, theme)
        captions[filename]['caption'] = prose
        captions[filename]['hashtags'] = hashtags
        filled.append(filename)

    os.remove(SCRATCH_PATH)
    return filled, empty


def process_chunk(batch, model, captions):
    if not batch:
        return [], [], []

    try:
        run_claude(build_prompt(batch, captions), model)
    except RuntimeError as exc:
        if len(batch) == 1:
            print(f'  SKIPPED (flagged, left pending): {batch[0]} — {exc}')
            flag_failure(batch[0], exc)
            return [], [], list(batch)
        mid = len(batch) // 2
        print(f'  Chunk of {len(batch)} failed ({exc}); splitting to isolate the problem entry...')
        f1, e1, x1 = process_chunk(batch[:mid], model, captions)
        f2, e2, x2 = process_chunk(batch[mid:], model, captions)
        return f1 + f2, e1 + e2, x1 + x2

    filled, empty = merge_batch(batch, captions)
    save_captions(captions, BASE_DIR)
    unflag(filled + empty)
    return filled, empty, []


def write_review_html(batch, captions):
    rows = []
    for filename in batch:
        entry = captions.get(filename, {})
        quote = entry.get('quote', '')
        caption = entry.get('caption', '')
        hashtags = ' '.join(entry.get('hashtags') or [])
        img_src = urlquote(f'images/{filename}')
        quote_html = html.escape(quote).replace('\n', '<br>')
        caption_html = html.escape(caption).replace('\n', '<br>')
        rows.append(f'''
    <div class="row">
      <a href="{img_src}" target="_blank"><img src="{img_src}" loading="lazy"></a>
      <div class="text">
        <div class="filename">{html.escape(filename)}</div>
        <div class="quote">Quote: {quote_html}</div>
        <div class="caption">{caption_html}</div>
        <div class="hashtags">{html.escape(hashtags)}</div>
      </div>
    </div>''')

    page = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Caption review</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  .row {{ display: flex; gap: 1rem; align-items: flex-start; border-bottom: 1px solid #ddd; padding: 1rem 0; }}
  .row img {{ max-width: 220px; max-height: 220px; object-fit: contain; border: 1px solid #ccc; }}
  .text {{ flex: 1; font-size: 1rem; }}
  .filename {{ font-size: 0.85rem; color: #666; margin-bottom: 0.4rem; font-family: monospace; }}
  .quote {{ font-size: 0.85rem; color: #888; font-style: italic; margin-bottom: 0.5rem; }}
  .caption {{ white-space: pre-line; }}
  .hashtags {{ color: #0a5; margin-top: 0.4rem; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Caption review — {len(batch)} images</h1>
<p>Click an image to open it full-size. Judge whether the caption actually engages with that
specific quote, not generic filler.</p>
{''.join(rows)}
</body>
</html>
'''
    with open(REVIEW_PATH, 'w', encoding='utf-8') as handle:
        handle.write(page)


def write_flagged_html(flagged):
    if not flagged:
        if os.path.exists(FLAGGED_REVIEW_PATH):
            os.remove(FLAGGED_REVIEW_PATH)
        return

    rows = []
    for filename, info in sorted(flagged.items()):
        img_src = urlquote(f'images/{filename}')
        rows.append(f'''
    <div class="row">
      <a href="{img_src}" target="_blank"><img src="{img_src}" loading="lazy"></a>
      <div class="quote">
        <div class="filename">{html.escape(filename)}</div>
        <div>Attempts: {info.get('attempts', '?')} &middot; Last: {html.escape(info.get('last_attempt', ''))}</div>
        <div class="error">{html.escape(info.get('error', ''))}</div>
      </div>
    </div>''')

    page = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Captions — flagged images</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  .row {{ display: flex; gap: 1rem; align-items: flex-start; border-bottom: 1px solid #ddd; padding: 1rem 0; }}
  .row img {{ max-width: 220px; max-height: 220px; object-fit: contain; border: 1px solid #ccc; }}
  .quote {{ flex: 1; font-size: 1.05rem; }}
  .filename {{ font-size: 0.85rem; color: #666; margin-bottom: 0.4rem; font-family: monospace; }}
  .error {{ color: #b00020; margin-top: 0.4rem; }}
</style>
</head>
<body>
<h1>Captions — {len(flagged)} flagged image(s)</h1>
<p>These failed caption generation and are skipped by default on future runs. Re-run with
<code>--retry-flagged</code> to try them again.</p>
{''.join(rows)}
</body>
</html>
'''
    with open(FLAGGED_REVIEW_PATH, 'w', encoding='utf-8') as handle:
        handle.write(page)


def main():
    parser = argparse.ArgumentParser(
        description='Write non-canned captions for queue items that have a quote but no caption.'
    )
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--dry-run', action='store_true',
                         help='Show what would be processed without calling claude')
    parser.add_argument('--retry-flagged', action='store_true',
                         help='Include previously-flagged entries in this run')
    parser.add_argument('--list-flagged', action='store_true',
                         help='Print flagged entries and exit without processing anything')
    args = parser.parse_args()

    flagged = load_flagged()

    if args.list_flagged:
        if not flagged:
            print('No flagged entries.')
        else:
            print(f'{len(flagged)} flagged entries:')
            for filename, info in sorted(flagged.items()):
                print(f'  {filename} — attempts: {info.get("attempts")}, '
                      f'last: {info.get("last_attempt")}, error: {info.get("error")}')
            print(f'\nSee {FLAGGED_REVIEW_PATH}, or re-run with --retry-flagged.')
        return

    queue = read_queue()
    captions = load_captions(BASE_DIR)
    pending = pending_filenames(queue, captions, flagged, include_flagged=args.retry_flagged)

    if not pending:
        skipped_note = f' ({len(flagged)} flagged and skipped)' if flagged else ''
        print(f'No queue items need a caption.{skipped_note} Nothing to do.')
        return

    target = pending[:args.batch_size]
    print(f'{len(pending)} items pending. Processing {len(target)} this run '
          f'in chunks of {args.chunk_size}:')
    for filename in target:
        print(f'  {filename}')

    if args.dry_run:
        return

    all_filled, all_empty, all_failed = [], [], []
    for start in range(0, len(target), args.chunk_size):
        chunk = target[start:start + args.chunk_size]
        print(f'\n--- chunk {start // args.chunk_size + 1} ({len(chunk)} images) ---')
        filled, empty, failed = process_chunk(chunk, args.model, captions)
        all_filled += filled
        all_empty += empty
        all_failed += failed

    reviewed = all_filled + all_empty
    if reviewed:
        write_review_html(reviewed, captions)

    flagged = load_flagged()
    write_flagged_html(flagged)

    print(f'\nDone. {len(all_filled)} filled, {len(all_empty)} came back empty, '
          f'{len(all_failed)} flagged/skipped.')
    if all_failed:
        print('Flagged this run:')
        for filename in all_failed:
            print(f'  {filename}')

    remaining = len(pending_filenames(read_queue(), load_captions(BASE_DIR), flagged))
    print(f'\n{remaining} items still pending (excluding {len(flagged)} flagged) '
          f'— run again to continue.')
    if reviewed:
        print(f'Review: file://{REVIEW_PATH}')
    if flagged:
        print(f'Flagged: file://{FLAGGED_REVIEW_PATH}')


if __name__ == '__main__':
    main()
