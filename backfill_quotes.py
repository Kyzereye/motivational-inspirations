#!/usr/bin/env python3
"""Backfill missing `quote` text in captions.json by having Claude read the
images directly (vision), for entries where OCR (generate_captions.py) came
back empty. Does not touch the `caption` field — that's a separate step.

Processes one batch per run (queue order, most urgent first) so you can
review quality before continuing. Uses the Claude Code CLI in headless mode
against your existing subscription — no separate API key.

Large batches are split into chunks internally; if a chunk fails (e.g. one
image trips content filtering), it's bisected to isolate the problem file(s)
instead of losing the whole chunk's progress. Problem files are recorded in
list/backfill_flagged.json and skipped on future runs until retried with
--retry-flagged, with a clickable backfill_flagged.html to inspect them.
"""
import argparse
import html
import json
import os
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

from caption_lib import load_captions, save_captions, slug_to_title

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(BASE_DIR, 'list', 'queue.txt')
POSTED_LOG_PATH = os.path.join(BASE_DIR, 'list', 'posted_log.txt')
SCRATCH_PATH = os.path.join(BASE_DIR, '.backfill_scratch.json')
REVIEW_PATH = os.path.join(BASE_DIR, 'backfill_review.html')
FLAGGED_PATH = os.path.join(BASE_DIR, 'list', 'backfill_flagged.json')
FLAGGED_REVIEW_PATH = os.path.join(BASE_DIR, 'backfill_flagged.html')

DEFAULT_BATCH_SIZE = 25
DEFAULT_CHUNK_SIZE = 25
DEFAULT_MODEL = 'claude-sonnet-5'


def read_queue():
    with open(QUEUE_PATH, encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip()]


def read_posted_log():
    if not os.path.exists(POSTED_LOG_PATH):
        return []
    with open(POSTED_LOG_PATH, encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip()]


def source_filenames(include_posted):
    """Queue items first (live, upcoming posts) — those matter most. Already-posted
    history is appended after, only when explicitly requested, since backfilling
    their quotes is data hygiene, not fixing anything currently broken."""
    sources = read_queue()
    if include_posted:
        seen = set(sources)
        for filename in read_posted_log():
            if filename not in seen:
                sources.append(filename)
                seen.add(filename)
    return sources


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
        if (entry.get('quote') or '').strip():
            continue
        if filename in flagged and not include_flagged:
            continue
        pending.append(filename)
    return pending


def build_prompt(batch):
    lines = []
    for filename in batch:
        kind = 'PNG' if filename.lower().endswith('.png') else 'JPG'
        lines.append(f'- images/{filename} ({kind})')
    file_list = '\n'.join(lines)
    return f'''You are transcribing quote text directly off image files for a data-entry task —
read each image with your Read tool and report back exactly what text is visible. Do not
paraphrase, summarize, correct wording, or add commentary. This is transcription, not editing.

For PNG files: these have a bold title line plus smaller supporting/body text below it.
Transcribe ONLY the body text below the title — not the title itself. If there is no separate
body text, use an empty string for that file.

For JPG files: these are quote photos. Transcribe the exact quote text shown on the image. If an
author name appears as a separate line/overlay near the quote (not part of the quote sentence
itself), leave it out — just the quote text.

If an image is unreadable, too low-contrast, or you are not confident of the exact text, use an
empty string for that file rather than guessing.

Files to process:
{file_list}

When you have read all of them, write a single JSON object to the exact path
`{SCRATCH_PATH}` mapping each filename above (exactly as given, without the `images/` prefix) to
its transcribed text as a string. Write to no other file in this repository.'''


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
        text = (results.get(filename) or '').strip()
        entry = captions.setdefault(filename, {'quote': '', 'caption': ''})
        if filename.lower().endswith('.png'):
            title = slug_to_title(filename)
            entry['quote'] = f'{title}.\n{text}' if text else f'{title}.'
        else:
            entry['quote'] = text
        (filled if text else empty).append(filename)

    os.remove(SCRATCH_PATH)
    return filled, empty


def process_chunk(batch, model, captions):
    """Transcribe one chunk and merge+save immediately on success. On failure
    (e.g. a single image tripping content filtering), bisect the chunk to
    isolate the problem file(s) instead of losing the whole chunk's progress.
    Returns (filled, empty, failed) filename lists."""
    if not batch:
        return [], [], []

    try:
        run_claude(build_prompt(batch), model)
    except RuntimeError as exc:
        if len(batch) == 1:
            print(f'  SKIPPED (flagged, left pending): {batch[0]} — {exc}')
            flag_failure(batch[0], exc)
            return [], [], list(batch)
        mid = len(batch) // 2
        print(f'  Chunk of {len(batch)} failed ({exc}); splitting to isolate the problem file...')
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
        quote = captions.get(filename, {}).get('quote', '')
        img_src = urlquote(f'images/{filename}')
        quote_html = html.escape(quote).replace('\n', '<br>')
        rows.append(f'''
    <div class="row">
      <a href="{img_src}" target="_blank"><img src="{img_src}" loading="lazy"></a>
      <div class="quote">
        <div class="filename">{html.escape(filename)}</div>
        <div>{quote_html}</div>
      </div>
    </div>''')

    page = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Backfill review</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  .row {{ display: flex; gap: 1rem; align-items: flex-start; border-bottom: 1px solid #ddd; padding: 1rem 0; }}
  .row img {{ max-width: 220px; max-height: 220px; object-fit: contain; border: 1px solid #ccc; }}
  .quote {{ flex: 1; font-size: 1.05rem; }}
  .filename {{ font-size: 0.85rem; color: #666; margin-bottom: 0.4rem; font-family: monospace; }}
</style>
</head>
<body>
<h1>Backfill review — {len(batch)} images</h1>
<p>Click an image to open it full-size. Compare against the transcribed text next to it.</p>
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
<title>Backfill — flagged images</title>
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
<h1>Backfill — {len(flagged)} flagged image(s)</h1>
<p>These failed to transcribe (often a content-filter block) and are skipped by default on future
runs. Open an image to see what might be tripping it. Re-run with <code>--retry-flagged</code> to
try them again.</p>
{''.join(rows)}
</body>
</html>
'''
    with open(FLAGGED_REVIEW_PATH, 'w', encoding='utf-8') as handle:
        handle.write(page)


def main():
    parser = argparse.ArgumentParser(
        description='Backfill missing quote text in captions.json via image reading.'
    )
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        '--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE,
        help='Images per claude invocation; large batches are split into chunks this '
             'size so one bad image cannot lose the whole run',
    )
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be processed without calling claude',
    )
    parser.add_argument(
        '--retry-flagged', action='store_true',
        help='Include previously-flagged (failed) images in this run instead of skipping them',
    )
    parser.add_argument(
        '--list-flagged', action='store_true',
        help='Print flagged images and exit without processing anything',
    )
    parser.add_argument(
        '--include-posted', action='store_true',
        help='Also backfill quotes for already-posted images (list/posted_log.txt), '
             'after any still-pending queue items. Data hygiene only — these have '
             'already gone out bare and this does not repost or change that.',
    )
    args = parser.parse_args()

    flagged = load_flagged()

    if args.list_flagged:
        if not flagged:
            print('No flagged images.')
        else:
            print(f'{len(flagged)} flagged image(s):')
            for filename, info in sorted(flagged.items()):
                print(f'  {filename} — attempts: {info.get("attempts")}, '
                      f'last: {info.get("last_attempt")}, error: {info.get("error")}')
            print(f'\nSee {FLAGGED_REVIEW_PATH} to view them, or re-run with --retry-flagged.')
        return

    sources = source_filenames(args.include_posted)
    captions = load_captions(BASE_DIR)
    pending = pending_filenames(sources, captions, flagged, include_flagged=args.retry_flagged)

    if not pending:
        skipped_note = f' ({len(flagged)} flagged and skipped — see --list-flagged)' if flagged else ''
        scope = 'queue + posted history' if args.include_posted else 'queue'
        print(f'No {scope} items with missing quotes.{skipped_note} Nothing to do.')
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
    if all_empty:
        print('Empty (unreadable or no text found):')
        for filename in all_empty:
            print(f'  {filename}')
    if all_failed:
        print('Flagged this run (content filter or API error — see backfill_flagged.html):')
        for filename in all_failed:
            print(f'  {filename}')

    remaining = len(pending_filenames(source_filenames(args.include_posted), load_captions(BASE_DIR), flagged))
    print(f'\n{remaining} items still pending (excluding {len(flagged)} flagged) '
          f'— run again to continue.')
    if reviewed:
        print(f'Review: file://{REVIEW_PATH}')
    if flagged:
        print(f'Flagged: file://{FLAGGED_REVIEW_PATH}')


if __name__ == '__main__':
    main()
