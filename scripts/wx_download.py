#!/usr/bin/env python3
"""Download a WeChat Channels (微信视频号) video to a local MP4 file.

Resolution chain (why it exists): the public finder-preview page only returns
cover/metadata; the real playback URL requires a short-lived token + exportId
obtained from Tencent Yuanbao's logged-in parse API.

Three input modes (mutually exclusive):
  1. --parse-json FILE   Preferred. JSON pasted from the browser console snippet
                         (assets/console_snippet.js). No cookie ever enters chat.
  2. --cookie-file FILE  Yuanbao cookie on disk; this script calls the Yuanbao
                         parse API itself. Requires --share-url. ACCOUNT RISK.
  3. --video-url URL     Already-resolved finder.video.qq.com direct URL; skips
                         all resolution. Zero credential use.

Examples:
  python wx_download.py --parse-json result.json --output video.mp4
  python wx_download.py --cookie-file cookie.txt --share-url "https://weixin.qq.com/sph/XXX" --output video.mp4
  python wx_download.py --video-url "https://finder.video.qq.com/..." --output video.mp4
  python wx_download.py --parse-json result.json --resolve-only
"""

import argparse
import json
import os
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request

YUANBAO_PARSE_API = "https://yuanbao.tencent.com/api/weixin/get_parse_result"
FEED_API = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
REFERER = "https://channels.weixin.qq.com/"


def _post_json(url, payload, headers, timeout=30):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = {"Content-Type": "application/json", "User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def yuanbao_parse(share_url, cookie):
    """Call Yuanbao parse API. Returns parsed data dict or raises with a clear message."""
    headers = {
        "Origin": "https://yuanbao.tencent.com",
        "Referer": "https://yuanbao.tencent.com/",
        "X-Source": "web",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie.strip(),
    }
    status, raw = _post_json(
        YUANBAO_PARSE_API,
        {"type": "video_channel_url", "url": share_url, "scene": 1},
        headers,
    )
    if status == 401:
        raise RuntimeError("元宝 Cookie 已失效或无效（HTTP 401），请重新从浏览器获取。")
    try:
        obj = json.loads(raw)
    except Exception:
        raise RuntimeError(f"元宝接口返回非 JSON（HTTP {status}）: {raw[:300]!r}")
    if obj.get("code") != 0 or not obj.get("data"):
        raise RuntimeError(f"元宝解析失败（HTTP {status}）: {json.dumps(obj, ensure_ascii=False)[:400]}")
    return obj["data"]


def extract_token_eid(parse_data):
    """Pull generalToken and exportId out of parse_data.playable_url query string."""
    playable = parse_data.get("playable_url") or ""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(playable).query)
    token = q.get("token", [None])[0]
    eid = q.get("eid", [None])[0] or parse_data.get("wx_export_id")
    if not token:
        raise RuntimeError("playable_url 中没有 token 参数，无法解析视频。")
    if not eid:
        raise RuntimeError("playable_url 中没有 eid，且返回体也没有 wx_export_id。")
    return token, eid


def get_feed(token, eid):
    """Call the finder feed API. HTTP 201 also counts as success."""
    headers = {
        "Origin": "https://channels.weixin.qq.com",
        "Referer": "https://channels.weixin.qq.com/finder-preview/pages/feed",
    }
    status, raw = _post_json(
        FEED_API,
        {"baseReq": {"generalToken": token}, "exportId": eid},
        headers,
    )
    if not (200 <= status < 300):
        raise RuntimeError(f"视频号 feed 接口失败（HTTP {status}）: {raw[:300]!r}")
    obj = json.loads(raw)
    if obj.get("errCode") not in (0, None):
        raise RuntimeError(f"视频号 feed 接口返回错误: {json.dumps(obj, ensure_ascii=False)[:400]}")
    feed = ((obj.get("data") or {}).get("feedInfo")) or {}
    author = ((obj.get("data") or {}).get("authorInfo") or {}).get("nickname", "")

    video_url = None
    for key in ("videoUrl", "h264VideoInfo", "h265VideoInfo"):
        v = feed.get(key)
        if isinstance(v, str) and v.startswith("http"):
            video_url = v
            break
        if isinstance(v, dict) and (v.get("videoUrl") or "").startswith("http"):
            video_url = v["videoUrl"]
            break
    if not video_url:
        raise RuntimeError(
            "响应中没有播放地址（仅有封面/元数据）。通常意味着 token/eid 不匹配或已过期。"
        )
    return {
        "video_url": video_url,
        "author": author,
        "description": feed.get("description", ""),
        "cover_url": feed.get("coverUrl", ""),
    }


def download(video_url, output_path):
    """Stream-download with required headers, verify MP4 atoms, then atomically rename."""
    out_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    part = output_path + ".part"
    req = urllib.request.Request(
        video_url,
        headers={"User-Agent": UA, "Referer": REFERER},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as f:
        ctype = resp.headers.get("Content-Type", "")
        declared = resp.headers.get("Content-Length")
        total = 0
        while True:
            chunk = resp.read(1024 * 512)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    if declared and int(declared) != total:
        raise RuntimeError(f"下载不完整: 声明 {declared} 字节，实际 {total} 字节")

    size = os.path.getsize(part)
    with open(part, "rb") as f:
        if b"ftyp" not in f.read(64):
            raise RuntimeError("文件头没有 ftyp，可能是错误页或被加密，未保存为正式文件。")
        pos = 0
        atoms = []
        while pos + 8 <= size:
            f.seek(pos)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            atom_size, atom_type = struct.unpack(">I4s", hdr)
            atom_type = atom_type.decode("latin1")
            header_len = 8
            if atom_size == 1:
                ext = f.read(8)
                if len(ext) < 8:
                    break
                atom_size = struct.unpack(">Q", ext)[0]
                header_len = 16
            elif atom_size == 0:
                atom_size = size - pos
            atoms.append((atom_type, atom_size))
            pos += atom_size
            if atom_size <= 0:
                raise RuntimeError("MP4 atom 长度异常，文件可能损坏。")
    if pos != size:
        raise RuntimeError(f"MP4 atom 合计 {pos} != 文件大小 {size}，文件可能被截断。")
    if not any(a == "mdat" for a, _ in atoms):
        raise RuntimeError("缺少 mdat atom，文件可能无有效音视频数据。")

    os.replace(part, output_path)
    return {"path": os.path.abspath(output_path), "bytes": total,
            "atoms": [a for a, _ in atoms]}


def main():
    ap = argparse.ArgumentParser(description="下载微信视频号视频")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--parse-json", help="元宝解析结果 JSON 文件（浏览器控制台粘贴，推荐）")
    src.add_argument("--cookie-file", help="元宝 Cookie 文本文件（有账号风险）")
    src.add_argument("--video-url", help="已解析的 finder.video.qq.com 直链")
    ap.add_argument("--share-url", help="配合 --cookie-file 使用的视频号分享链接")
    ap.add_argument("--output", help="输出 MP4 路径")
    ap.add_argument("--resolve-only", action="store_true", help="只解析并打印信息，不下载")
    args = ap.parse_args()

    if args.parse_json:
        with open(args.parse_json, encoding="utf-8") as f:
            obj = json.load(f)
        # Accept both the raw console output and a wrapped {"data": {...}} shape.
        data = obj.get("data", obj)
        token, eid = extract_token_eid(data)
        info = get_feed(token, eid)
    elif args.cookie_file:
        if not args.share_url:
            ap.error("--cookie-file 需要同时提供 --share-url")
        with open(args.cookie_file, encoding="utf-8") as f:
            data = yuanbao_parse(args.share_url, f.read())
        token, eid = extract_token_eid(data)
        info = get_feed(token, eid)
    else:
        info = {"video_url": args.video_url, "author": "", "description": "", "cover_url": ""}

    if args.resolve_only:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    if not args.output:
        ap.error("下载模式需要 --output 指定输出路径")
    result = download(info["video_url"], args.output)
    print(json.dumps({**info, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
