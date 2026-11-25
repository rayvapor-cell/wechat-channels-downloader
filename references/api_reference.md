# WeChat Channels Download — API Reference & Troubleshooting

## Why resolution is needed

`https://weixin.qq.com/sph/<ID>` 301-redirects to
`https://channels.weixin.qq.com/finder-preview/pages/sph?id=<ID>`, a ~2.6 KB empty
SPA. Its public API `POST /finder-preview/api/feed/get_feed_info` returns only
cover/metadata **unless** a valid short-lived `generalToken` + `exportId` are
supplied. Those credentials come from Tencent Yuanbao's logged-in parse API.

Public third-party resolver `sph.litao.workers.dev` is dead (HTTP 401 since
2026-08; upstream Yuanbao account was banned and auth was added). Do not try to
bypass its auth.

## Two-step chain

### 1. Yuanbao parse (requires login)

```
POST https://yuanbao.tencent.com/api/weixin/get_parse_result
Content-Type: application/json
X-Source: web
X-Requested-With: XMLHttpRequest
Cookie: <yuanbao web cookie>          # or browser credentials:'include'

{"type":"video_channel_url","url":"<share url>","scene":1}
```

- `type` and `scene` are mandatory; omitting them yields `code:0` with empty data.
- Anonymous/no-cookie call → HTTP 401 `{"error":{"code":"20000","message":"未知错误"}}`.
- Cookie essentials: `hy_user`, `hy_token`, `hy_source=web` (on `.tencent.com` parent domain).
- Success shape (key fields):

```json
{"code":0,"msg":"success","data":{
  "wx_export_id":"export/UzFf...",
  "cover_url":"https://finder.video.qq.com/...",
  "author":"Deler的Ai日记",
  "desc":"...",
  "playable_url":"https://channels.weixin.qq.com/finder-preview/pages/feed?...&token=cixi...%3D&eid=export%2F..."
}}
```

- Extract `token` and `eid` from `playable_url` query string (URL-decoded).
  Fall back to top-level `wx_export_id` if `eid` is absent.

### 2. Feed info (no login, but needs token + eid)

```
POST https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info
Content-Type: application/json
Origin: https://channels.weixin.qq.com
Referer: https://channels.weixin.qq.com/finder-preview/pages/feed

{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}
```

- **HTTP 201 is a valid success response** — check the 2xx range, not `== 200`.
- Without a valid token → HTTP 401 `permission verification failed`.
- Playback URL priority: `feedInfo.videoUrl` → `feedInfo.h264VideoInfo.videoUrl`
  → `feedInfo.h265VideoInfo.videoUrl`. Prefer H.264 for compatibility.
- Metadata: `data.feedInfo.description`, `data.feedInfo.coverUrl`,
  `data.authorInfo.nickname`.

### 3. Download the MP4

```
GET <videoUrl>
User-Agent: Mozilla/5.0 (...) Chrome/120.0.0.0 Safari/537.36
Referer: https://channels.weixin.qq.com/
```

- Keep the CDN URL **exactly** as returned. Removing any query param
  (`encfilekey`, `token`, `hy`, `idx`, `uzid`, `X-snsvideoflag`, `basedata`,
  `sign`, ...) → 400 Bad Request.
- Write to a `.part` file, verify MP4 atoms (`ftyp` in first 64 bytes, atom sizes
  sum to file size, `mdat` present), then rename. `mdat` absence may indicate
  ISAAC encryption — do not present such a file as a valid video.

## Known limitations / what NOT to do

- Do not use `yt-dlp`; official yt-dlp has no WeChat Channels extractor.
- Do not try to grab the URL by opening the share page in a normal browser:
  the stream-fetch branch is gated behind `WeixinJSBridge` (WeChat client only).
  For packet capture, capture inside the WeChat client and supply a HAR/URL list.
- Do not bypass authentication, forge tokens, or use third-party cookies.
- Cookie expires in roughly one month; HTTP 401 means re-login and re-extract.
- Account risk falls on the **Yuanbao** account, not WeChat. Upstream bans were
  triggered by abnormal traffic volume from a shared public service. Recommend
  an idle/secondary account for cookie-based runs, lowest local frequency, and
  never share the cookie or publish it as a service.
