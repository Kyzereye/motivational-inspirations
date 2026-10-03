# Trend & Content Research Task

You are running as a scheduled/manual research pass for the Facebook + Instagram page
`InspirationForMotivation` (~20K followers, motivational/inspirational quote content).
This repo is `IM-FB-post`. Your job this run: research what is currently working in this
niche and write a set of concrete, actionable recommendations for the owner to review.

You are NOT posting anything, and you are NOT editing the live pipeline. This is a
read-mostly research task that writes new files into `trends/runs/` only.

## Config (edit these lines to change behavior — nothing else in this file should need to change)

- TARGET PLATFORMS: Facebook, Instagram
- RECOMMENDATION COUNT: 6 (aim for this many; fewer is fine if research doesn't support more, do not pad with filler to hit the number)
- LOOKBACK WINDOW: prefer sources from the last 30–90 days

## Step 1 — Ground yourself in this page's actual situation

Read directly from the repo (do not guess or assume):

- `caption_lib.py` — read the `THEME_KEYWORDS` dict to learn the current 8-theme taxonomy
  verbatim (love, discipline, ownership, mindset, courage, growth, success, peace). Also note
  this known limitation as fact: captions are built from `S1_BY_THEME`/`S2_BY_THEME`/`S3_BY_THEME`,
  roughly 3 canned template sentences per theme, picked by hashing the filename — around 30
  sentences total, recycled forever, with no awareness of what's currently resonating. Your
  recommendations should engage with this limitation specifically, not produce generic
  "post more consistently" filler.
- `createImage.py` — read it. It's a dormant proof-of-concept: the project can already render
  arbitrary text on a branded 1080x1080 canvas with a custom font (`angelina.TTF`). If you
  recommend a new visual format, point at this existing lever rather than assuming the owner
  needs a designer or new tooling.
- Scale facts only, cheaply — do not enumerate filenames:
  - `ls images/ | wc -l` and a rough count of `.jpg` vs `.png` (e.g. `ls images/*.jpg | wc -l`, `ls images/*.png | wc -l`)
  - `wc -l list/posted_log.txt` (a proxy for historical post volume)

**Hard constraint: do NOT read, open, or reference `heros-journey.md`.** That file is reserved
for a separate, unrelated future book project and must play no role in this task. If you notice
it while listing the repo root, skip it entirely — do not summarize it, do not quote it, do not
let it influence any recommendation.

## Step 2 — Research current trends

Use web search to research what is currently driving engagement in the motivational /
inspirational content niche specifically on the platforms listed under TARGET PLATFORMS above.
Favor sources from the LOOKBACK WINDOW that are platform-specific and niche-relevant (how
motivational/quote/inspiration pages are actually performing) over generic social-media-marketing
blog content.

For every trend or tactic you find, explicitly weigh it against what this page can realistically
execute TODAY (static image posts, a themed caption generator, no video pipeline, no analytics
integration) versus what would require building new capability. Both are valid recommendation
categories — just be explicit about which is which.

## Step 3 — Determine this run's output folder

1. List existing folders under `trends/runs/` (create the directory if it doesn't exist yet).
2. Today's date in `YYYY-MM-DD` format. If no folder for today exists, use `<date>_1`. If one or
   more already exist for today, use the next available `_N` suffix.
3. Create `trends/runs/<date>_<n>/`.
4. As your LAST action, refresh the symlink `trends/runs/latest` to point at this new folder
   (remove the old symlink first if present, e.g. `ln -sfn <date>_<n> trends/runs/latest`, run
   from inside `trends/runs/`).

## Step 4 — Write output

### `brief.md` in the run folder

A short prose summary: what you searched for and why, 3–5 top-line takeaways, and this exact
disclaimer verbatim near the top:

> **Note:** every recommendation in this run is a hypothesis grounded in external research and
> this page's existing asset library — it has not been validated against this page's own post
> performance, because no analytics/Insights integration exists yet.

### One file per recommendation: `NNNN_<short-slug>.md` (e.g. `0001_lean-into-first-line-hooks.md`)

Use this exact format:

```markdown
---
id: <N>
status: pending
category: <one of: narrative_arc | caption_refresh | new_image_concept | posting_cadence | format_experiment | hashtag_strategy>
platforms: [<subset of the TARGET PLATFORMS list, lowercase>]
confidence: hypothesis
related_assets: ["<reference to caption_lib.py theme(s) or createImage.py, if relevant — omit the field entirely if nothing concrete applies>"]
sources:
  - <url>
  - <url>
---

# <short, specific title>

## What's currently working (research finding)
<the actual trend/tactic, with enough specificity to act on>

## Why this fits this page specifically
<reference caption_lib.py's theme taxonomy or createImage.py by name where relevant; do not
invent capabilities the repo doesn't have>

## Concrete next step
<one clear, doable action — not a vague direction>

## Owner notes
<!-- the owner will add their reasoning here when approving/rejecting -->
```

Number files sequentially starting at `0001`. `status: pending` is always the initial value —
the owner edits it by hand later.

## Non-goals (do not do these, no matter what your research suggests)

- Do not edit `list/queue.txt`, `list/posted_log.txt`, `list/captions.json`, `autoPost.py`,
  `caption_lib.py`, or `generate_captions.py`.
- Do not read or reference `heros-journey.md` under any circumstances.
- Do not create, move, or post any actual content to Facebook or Instagram.
- Do not write anywhere outside `trends/runs/<this run's folder>/` (and the `trends/runs/latest`
  symlink refresh).

## When done

Print a one-line summary to the console: the run folder path and how many recommendations you
wrote.
