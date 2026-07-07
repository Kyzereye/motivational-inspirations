Generate a Facbook token

go to 
input your short lived token
click Extend Access Token
Get https://graph.facebook.com/v14.0/App-Scoped-User-ID/accounts?access_token=extenedtoken



{"error":{"message":"(#200) If posting to a group, requires app being installed in the group, and either publish_to_groups permission with user token, or both pages_read_engagement and pages_manage_posts permission with page token; 

If posting to a page, requires both pages_read_engagement and pages_manage_posts as an admin with sufficient administrative permission","type":"OAuthException","code":200,"fbtrace_id":"A_qti_dczjxMA6tf1-9meS0"}}# motivational-inspirations

## Cron log

Check recent autoPost output (Facebook + Instagram):

```bash
tail -20 ~/Projects/IM-FB-post/post.log
```

## Captions

Edit captions in one file (used at post time):

`list/captions.json`

Regenerate drafts (queue + posted_log filenames):

```bash
python3 ~/Projects/IM-FB-post/generate_captions.py
```

Skip existing entries unless you pass `--force`.

## Review folder (caption editing)

Symlinks in `queue_backup.txt` order — matches `captions.json`:

```bash
python3 ~/Projects/IM-FB-post/build_review_links.py
```

Open `review/` in your file manager: `0001_...`, `0002_...` align with row order in `captions.json`.
