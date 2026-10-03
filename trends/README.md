# Trend & Content Research Agent (v1)

Researches what's currently working in the motivational/inspirational content niche on
Facebook and Instagram, and writes concrete, reviewable recommendations. It does not post
anything and does not touch the live queue (`list/queue.txt`) — it's purely advisory.

## Run it

```bash
./trends/run_research.sh
```

This runs interactively the first several times — you'll see and approve each tool call
(reading files, web searches, writing output). Once you trust the output, unattended runs
(e.g. for cron) skip those prompts:

```bash
./trends/run_research.sh --unattended
```

## Review output

```bash
open trends/runs/latest/   # or your file manager / editor of choice
```

- Read `brief.md` first — it's the research summary and methodology, plus a standing
  reminder that every recommendation is a hypothesis (there's no analytics feedback loop yet).
- Each numbered file (`0001_*.md`, `0002_*.md`, ...) is one recommendation. Open it, read it,
  and edit the `status:` field in the YAML front matter to `approved` or `rejected` — add
  reasoning under "Owner notes" if you want. There's no separate index to keep in sync; the
  file itself is the record.

After each run, it's worth a quick `git status` to confirm only `trends/runs/` changed.

## What it does NOT do (by design, in v1)

- Doesn't touch `list/queue.txt`, `autoPost.py`, `caption_lib.py`, or `generate_captions.py`.
- Doesn't read or reference `heros-journey.md` — that's reserved for a separate future book
  project and is off-limits to this tool.
- No video/Reels production, no Facebook/Instagram Insights integration.

## Changing scope later

Edit the "Config" block at the top of `trends/TASK.md` (target platforms, recommendation
count, lookback window) — nothing else in the task spec needs to change to, say, add a third
platform.

## Once you trust it: scheduling

Add one line to the existing crontab, in the same style as the four `autoPost.py` entries:

```
0 8 * * 1 /home/jeff/Projects/IM-FB-post/trends/run_research.sh --unattended >> /home/jeff/Projects/IM-FB-post/trends/research.log 2>&1
```

No code changes needed to get here — it's the same script, same task spec.
