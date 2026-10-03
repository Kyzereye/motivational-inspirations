# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Rules

1. **Only do what you're told.** Don't add things that weren't asked for or signed off on.
   Suggesting something important or relevant is fine — just suggest it, don't implement it unprompted.
2. **Keep it simple.** No complexity that isn't needed. As simple as possible, no simpler.
3. **DRY.** If code is used more than once and factoring it makes sense, make it a function. No redundant code.

## Project Overview

This is a social media automation system for posting motivational and inspirational quotes to Facebook and Instagram. The system:

- Uses OCR to extract quotes from images
- Generates contextual captions with theme-based hashtags
- Maintains a queue of posts to be published
- Posts to both Facebook and Instagram via their Graph APIs
- Runs on a cron schedule (typically multiple times daily based on post.log timestamps)

## Key Concepts

**Queue-based Publishing**: Images are queued in `list/queue.txt`. The `autoPost.py` script runs periodically, posts the first image in the queue, then moves it to `list/posted_log.txt`.

**Caption Generation**: Captions are generated deterministically based on the image filename and detected quote theme (love, discipline, ownership, mindset, courage, growth, success, peace, or default). The same filename always generates the same caption, but `--force` regenerates. Generated captions stored in `list/captions.json`.

**Theme Detection**: Quote themes are detected by keyword matching in the quote body. Each theme has 3 sentences (S1/S2/S3) that cycle based on a seed hash of the filename, plus 2 discovery hashtags + 2 brand hashtags.

**OCR Pipeline**: Images are OCR'd using pytesseract with multiple PSM (Page Segmentation Mode) attempts and contrast enhancement. Different quote extraction logic for PNG vs JPG images.

## Common Development Tasks

### Generate or regenerate captions
```bash
python3 generate_captions.py
```
- Scans `list/queue.txt` and `list/posted_log.txt` for filenames
- OCR's images in `images/` directory
- Stores results in `list/captions.json`
- Skips existing entries unless you pass `--force` to regenerate all
- Use `--limit N` to process only first N files, `--prefix PREFIX` to filter by filename prefix

### Create review symlinks
```bash
python3 build_review_links.py
```
- Creates numbered symlinks in `review/` directory (0001_..., 0002_..., etc.) matching `list/queue_backup.txt` order
- Allows easy browsing/editing of captions in file manager with correct sort order
- Symlinks point back to `images/` directory

### Post to social media (runs via cron)
```bash
python3 autoPost.py
```
- Takes first image from `list/queue.txt`
- Loads caption from `list/captions.json`
- Posts to Facebook, then Instagram (if enabled)
- Moves posted filename to `list/posted_log.txt`
- All output logged to `post.log` with ISO timestamps

### Monitor posting activity
```bash
tail -20 ~/Projects/IM-FB-post/post.log
```

### Backfill missing quotes via image reading (not OCR)
```bash
python3 backfill_quotes.py                       # process next batch (default 25)
python3 backfill_quotes.py --dry-run              # see what would be processed
python3 backfill_quotes.py --batch-size 100       # bigger batch, auto-chunked internally
python3 backfill_quotes.py --list-flagged         # see images that failed transcription
python3 backfill_quotes.py --retry-flagged        # include flagged images in this run
python3 backfill_quotes.py --include-posted       # also backfill already-posted images (data hygiene)
```
- For queue items where `generate_captions.py`'s tesseract OCR came back empty (as of
  2026-09-30, 1,359 of 1,377 queued items), this has Claude read the image directly and
  transcribe the quote text — far more reliable than OCR on stylized/decorative graphics.
- Only fills the `quote` field in `list/captions.json`; does not touch `caption` (that's a
  separate, later step — see `write_captions.py` below).
- Skips any entry that already has a `quote`. Processes queue order; `--batch-size` is the
  total for this run, internally split into `--chunk-size` (default 25) calls to `claude -p` so
  you can review transcription quality before requesting more, or just run larger batches.
- By default only looks at `list/queue.txt` (upcoming posts — what actually matters for live
  posting). `--include-posted` additionally backfills already-posted images from
  `list/posted_log.txt`, appended after any queue items — this is pure data hygiene (those
  posts already went out bare; nothing gets reposted or changed on Facebook/Instagram).
- **Resilient to bad images**: if a chunk fails (e.g. one image trips content-filtering), it's
  automatically bisected to isolate the specific problem file(s) rather than losing the whole
  chunk's progress. Problem files are recorded in `list/backfill_flagged.json` (filename, error,
  attempt count) and skipped on future runs — view them via `backfill_flagged.html` (clickable
  thumbnails, same format as `backfill_review.html`) or `--list-flagged`.
- Uses the Claude Code CLI headlessly (`claude -p`), same subscription-based approach as the
  trend research agent below, not a separate API key.
- After each run, `backfill_review.html` (repo root) shows every image processed that run as a
  clickable thumbnail next to its transcribed quote, for fast visual verification.

### Write non-canned captions for quoted-but-uncaptioned entries
```bash
python3 write_captions.py                       # process next batch (default 25)
python3 write_captions.py --dry-run              # see what would be processed
python3 write_captions.py --batch-size 100
python3 write_captions.py --list-flagged
python3 write_captions.py --retry-flagged
```
- For the 1,349 queue items (as of 2026-10-01) that have a `quote` (via `backfill_quotes.py`)
  but no `caption`: has Claude write a caption that engages with that specific quote's content —
  deliberately NOT `caption_lib.py`'s `build_caption()`, which only ever outputs 3 canned
  template sentences regardless of the quote (see trend research `0002`).
- `caption` field = quote + attribution + Claude-generated prose; `hashtags` field computed
  separately via deterministic `caption_lib.pick_hashtags()` (pool contents per `0003`, now live).
- Same chunking/bisection/flagging resilience as `backfill_quotes.py`: large batches survive a
  single bad entry, problem entries land in `list/caption_flagged.json` and are skipped until
  retried, with `caption_flagged.html` to inspect them.
- After each run, `caption_review.html` shows image + quote + generated caption together so you
  can judge whether it actually engages with that quote, not generic filler.
- Uses the Claude Code CLI headlessly (`claude -p`, default `claude-sonnet-5`), same
  subscription-based approach as `backfill_quotes.py` — no separate API key.

### Run trend & content research (advisory, not wired into posting)
```bash
./trends/run_research.sh              # interactive — approve each tool call
./trends/run_research.sh --unattended # no prompts, for cron once trusted
```
- Invokes the `claude` CLI headlessly against `trends/TASK.md` (uses the Claude Code
  subscription, not a separate API key)
- Researches current Facebook/Instagram trends in the motivational/inspirational niche via
  WebSearch, grounded in this repo's actual theme taxonomy (`caption_lib.py`) and dormant
  image-generation capability (`createImage.py`)
- Writes dated, numbered recommendation files to `trends/runs/<date>_<n>/` (gitignored) —
  never touches `list/queue.txt` or any pipeline file
- **Never reads or references `heros-journey.md`** — that file is reserved for an unrelated
  future book project and is a hard exclusion in `trends/TASK.md`
- Review output at `trends/runs/latest/`; approve/reject by editing the `status:` field in
  each recommendation's YAML front matter (see `trends/README.md`)

## Core Files and Architecture

### Data Files
- `list/queue.txt` — Filenames of images to post (FIFO order, each post removes first line)
- `list/posted_log.txt` — History of all posted filenames (appended to by autoPost.py)
- `list/queue_backup.txt` — Canonical ordering; used by `build_review_links.py` to create ordered review symlinks
- `list/captions.json` — JSON object mapping filename → {quote, caption, hashtags}. `caption`
  is prose/body text only; `hashtags` is a list of tag strings. `caption_lib.get_post_text_for_image()`
  recombines them into the actual text posted (body + blank line + space-joined tags) — this is
  what `autoPost.py` calls. The two were split into separate fields in 2026-10; before that,
  hashtags were embedded as the last line of `caption` itself.

### Scripts

**`autoPost.py`** (the posting engine)
- Runs on cron schedule
- Loads queue.txt, posts first image to Facebook + Instagram
- Handles caption lookup, token refresh, Instagram container polling (60s timeout)
- Logs all operations with timestamps to post.log
- Uses environment variables: FB_ACCESS_TOKEN, FB_PAGE_ID, META_USER_ACCESS_TOKEN, IG_ENABLED, IG_BUSINESS_ACCOUNT_ID

**`generate_captions.py`** (OCR + caption generation)
- Command-line tool to generate `list/captions.json` from images
- For each image: OCR → extract quote → detect theme → build caption with tagged sentences and hashtags
- PNG images use different quote extraction logic (looks for title line, then body)
- JPG images: looks for longest high-quality text block, then extracts main quote
- Deterministic: same filename always generates same caption (unless forced)
- Saves incrementally every 10 images

**`caption_lib.py`** (shared utilities)
- `detect_theme(text)` — Keyword matching to classify quote as one of 8 themes (or 'default')
- `build_caption(quote, filename)` — Returns `(body, hashtags)` tuple — 3 template sentences +
  hashtag list (does not concatenate them; callers store each in its own `captions.json` field)
- `get_post_text_for_image(filename, base_dir=None)` — Recombines a stored `caption` + `hashtags`
  into the actual text to post. Used by `autoPost.py`.
- `get_caption_for_image(filename, base_dir=None)` — Returns just the caption body (no hashtags)
- `load_captions()` / `save_captions()` — JSON I/O with proper ordering
- `parse_author_from_filename()` — Extract author name from filename pattern (e.g., "31_40_Rumi_Quote_027.jpg" → "Rumi")
- S1_BY_THEME, S2_BY_THEME, S3_BY_THEME — 3-sentence templates per theme
- DISCOVERY_POOLS — Hashtag pools per theme for discovery (seeded by filename hash); 4-6 tags
  per theme, no tag shared across two themes (redesigned 2026-10, see trend research `0003`)
- BRAND_TAGS, BRAND_PAIRS — Consistent brand hashtags (#InspirationalMotivation, #KeepMovingForward, #PositivelyMovingForward)

**`resync_hashtags.py`** / **`split_hashtags_field.py`** (one-off/maintenance migrations)
- `split_hashtags_field.py` — one-time migration that split the old combined `caption` string
  into separate `caption`/`hashtags` fields (already run; safe to leave in place for reference)
- `resync_hashtags.py` — re-run any time `DISCOVERY_POOLS` changes, to recompute the `hashtags`
  field for every captioned entry from the current pools (pure local recomputation, no API calls)

**`build_review_links.py`** (caption review workflow)
- Creates numbered symlinks in `review/` matching `list/queue_backup.txt` order
- Clears old symlinks and recreates from scratch
- Allows editing captions in file manager with visual alignment to queue_backup.txt

### Image Organization
- `images/` — All source images (JPG and PNG formats)
- `review/` — Numbered symlinks (0001_..., 0002_...) for caption review/editing
- PNG images: Often have text overlaid (quote + author), extracted via OCR
- JPG images: Quote images, typically tagged with author in filename

### Configuration
- `.env` — Facebook/Instagram API credentials (FB_ACCESS_TOKEN, FB_PAGE_ID, META_USER_ACCESS_TOKEN, IG_ENABLED, IG_BUSINESS_ACCOUNT_ID)

### Logging
- `post.log` — All autoPost.py runs with ISO timestamps, including Facebook/Instagram response IDs
- `caption_batch.log` — Legacy log of caption generation runs

## Technical Notes

### OCR Challenges
- Multiple PSM modes (3, 6, 11) tried with both RGB and contrast-enhanced grayscale
- Best result (by text quality score) is used
- PNG-specific patterns filtered (taglines like "motivation - author", footers like "keep moving forward")

### Determinism
- Caption generation is deterministic: hash(filename) % modulo picks sentence index and hashtag index
- Regeneration only occurs if: new image, no existing caption, quote theme changed, or `--force` flag

### Instagram Integration
- Two-step process: create container, poll for FINISHED status (up to 60s), publish
- Requires both Facebook photo upload AND Instagram Graph API setup
- Gracefully falls back if Instagram disabled or token not set

### File Encoding
- All JSON and text files use UTF-8 encoding explicitly
- Captions may contain Unicode (quotes, author names)

## Dependencies
- `facebook-sdk` — Facebook/Instagram Graph API client
- `Pillow` — Image processing (resize, convert, enhance)
- `pytesseract` — Python wrapper for Tesseract OCR (requires `tesseract-ocr` system package)
- `python-dotenv` — Load environment variables from `.env`
