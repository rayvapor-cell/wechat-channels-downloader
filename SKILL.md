---
name: wechat-channels-downloader
description: Download videos from WeChat Channels (微信视频号) share links to local MP4 files. This skill should be used when a user provides a weixin.qq.com/sph/... or channels.weixin.qq.com/finder-preview/... link and asks to download, save, or extract the video. Handles the Tencent Yuanbao resolution chain required to obtain the real playback URL, downloads with correct CDN headers, and verifies MP4 integrity. Covers browser-console (no cookie exposure), local-cookie, and direct-URL paths.
agent_created: true
---

# WeChat Channels Downloader

## Overview

Download a WeChat Channels (微信视频号) video from a share link. The public
share page hides the playback URL; resolving it requires a short-lived token
from Tencent Yuanbao's logged-in parse API. This skill provides a tested script
for the full chain plus a browser-console route that keeps the user's Cookie
out of the conversation.

## Prerequisites

- Python 3 installed (`python` / `python3` on PATH).
- Network access to `yuanbao.tencent.com` and `channels.weixin.qq.com`.
- One of the three credential paths below.

## Workflow Decision Tree

Pick the input path by what the user already has, in this priority order:

1. **User has a direct CDN URL** (`finder.video.qq.com/...`) or a local video file
   → use `--video-url` mode (zero credentials). For a local file, no skill script
   is needed at all.
2. **Default for a plain share link** → use `--parse-json` mode. Ask the user to
   run the browser console snippet in a logged-in Yuanbao tab and paste back the
   JSON. No Cookie is exposed in chat. **This is the recommended path.**
3. **User explicitly provides their Yuanbao Cookie** → use `--cookie-file` mode.
   Warn about account risk first (see Safety section).
4. Do **not** attempt the dead public resolver, yt-dlp, or ordinary browser
   page scraping — see `references/api_reference.md` for why these fail.

## Step 1 — Obtain the Yuanbao parse result (paths 2 and 3)

### Path 2 (recommended): browser console, no Cookie in chat

1. Read `assets/console_snippet.js`.
2. Replace `SHARE_URL` with the user's actual share link.
3. Instruct the user to open **https://yuanbao.tencent.com/**, log in, press F12
   → Console, paste the snippet, press Enter, and copy the entire printed JSON.
   - Recommend an idle/secondary Yuanbao account.
   - Mention that if the console prints `401` or an error, paste that too.
4. Save the pasted JSON verbatim to a temp file, e.g.
   `<workdir>/yuanbao_parse_result.json`, then continue to Step 2 with
   `--parse-json`.

### Path 3: user supplies Cookie directly

1. Warn: the Cookie is a login credential, carries a risk of Yuanbao account
   restriction, and must never be shared or published as a service. Recommend
   an idle account.
2. Write the Cookie to a temp file with a restricted path (do not embed it in
   shell command lines or logs), then use `--cookie-file` with `--share-url`.
3. Delete the Cookie file after the download completes.

## Step 2 — Resolve and download

Run the bundled script (resolve + download + verify in one shot):

```bash
python <skill-dir>/scripts/wx_download.py \
  --parse-json <workdir>/yuanbao_parse_result.json \
  --output "<workdir>/<meaningful-name>.mp4"
```

Other modes:

```bash
# Already-resolved direct URL (no credentials)
python <skill-dir>/scripts/wx_download.py --video-url "<finder.video.qq.com URL>" --output "out.mp4"

# Cookie on disk (account risk; requires --share-url)
python <skill-dir>/scripts/wx_download.py --cookie-file <cookie.txt> \
  --share-url "https://weixin.qq.com/sph/XXX" --output "out.mp4"

# Inspect metadata / playback URL without downloading
python <skill-dir>/scripts/wx_download.py --parse-json result.json --resolve-only
```

The script:
- extracts `token` / `eid` from `playable_url` (fallback `wx_export_id`);
- calls the feed API (treats HTTP 201 as success) and picks the first available
  of `videoUrl` → `h264VideoInfo.videoUrl` → `h265VideoInfo.videoUrl`;
- downloads with the required `User-Agent` + `Referer` headers;
- writes to `.part`, verifies MP4 atoms (`ftyp`, atom-size sum, `mdat`), then
  renames to the final path;
- prints a JSON summary including author, description, output path, byte count
  and atom list. On failure it prints `{"error": "..."}` and exits non-zero.

Name the output file meaningfully from the video description/author when
possible (e.g. `视频号_声音克隆配音对比.mp4`), not a generic `video.mp4`.

## Step 3 — Report the result

Report the saved absolute path, file size, author, and a one-line topic summary.
Mention that integrity verification passed. If the script errored, relay the
error verbatim and follow the troubleshooting notes in
`references/api_reference.md`.

## Safety and scope

- Only download videos for personal/authorized use; respect creators' copyright
  and platform terms.
- Never bypass authentication, forge tokens, or use someone else's Cookie.
- Keep Cookie material out of chat, command lines, logs, and committed files.
- The API is non-public and may change at any time; if the chain breaks, update
  `references/api_reference.md` with the new endpoint/response shape.

## Resources

- `scripts/wx_download.py` — tested all-in-one resolver, downloader, MP4 verifier.
- `assets/console_snippet.js` — browser-console snippet for obtaining the parse
  result without exposing the Cookie.
- `references/api_reference.md` — full endpoint details, response shapes, error
  codes, integrity checks, and known limitations.
