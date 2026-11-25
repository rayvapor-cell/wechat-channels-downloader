# wechat-channels-downloader

一个 WorkBuddy Skill：把微信视频号（WeChat Channels）分享链接下载为本地 MP4。

> 仅用于个人学习与技术研究。视频号内容受版权保护，请遵守相关法律法规与平台规则，尊重创作者版权。文中涉及的接口为腾讯非公开接口，随时可能变更或失效。

## 背景

视频号分享页（约 2.6 KB 的空壳 SPA）通过 `WeixinJSBridge` 隐藏真实播放地址，普通浏览器和公开解析服务均无法直接获取。本技能使用腾讯元宝的登录态解析接口换取临时凭证，再调用视频号 feed 接口取得 MP4 直链。

## 功能

- 解析分享链接 → 获取真实播放地址 → 下载并校验 MP4 完整性
- 三种输入模式：
  - `--parse-json`（推荐）：使用浏览器控制台输出的解析结果，Cookie 全程不进入对话
  - `--cookie-file`：本地 Cookie 文件（有元宝账号风险，需自行承担）
  - `--video-url`：已有直链，零凭证
- 下载带正确的 `Referer` / `User-Agent` 请求头，写入 `.part` 后校验 `ftyp` / `moov` / `mdat` 原子，通过后再改名为正式文件

## 安装

将整个目录放到 WorkBuddy 用户技能目录：

```bash
~/.workbuddy/skills/wechat-channels-downloader/
```

即包含 `SKILL.md`、`scripts/`、`references/`、`assets/` 的完整目录。WorkBuddy 会在用户提到视频号下载链接时自动触发。

## 使用示例

```bash
# 1) 浏览器控制台模式（推荐）
python scripts/wx_download.py --parse-json result.json --output video.mp4

# 2) 本地 Cookie 模式
python scripts/wx_download.py --cookie-file cookie.txt \
  --share-url "https://weixin.qq.com/sph/XXX" --output video.mp4

# 3) 已有直链模式
python scripts/wx_download.py --video-url "https://finder.video.qq.com/..." --output video.mp4

# 只解析、不下载
python scripts/wx_download.py --parse-json result.json --resolve-only
```

如何获取模式 1 所需的解析结果：在已登录 <https://yuanbao.tencent.com/> 的浏览器页面按 F12 → Console，粘贴 `assets/console_snippet.js`（把 `SHARE_URL` 换成实际链接），把打印出的 JSON 保存为文件即可。

## 文件结构

```
wechat-channels-downloader/
├── SKILL.md                     # 触发条件、工作流、安全边界
├── README.md
├── scripts/
│   └── wx_download.py           # 解析 + 下载 + MP4 校验
├── assets/
│   └── console_snippet.js       # 浏览器控制台代码片段
└── references/
    └── api_reference.md         # 接口细节、错误码、已知限制
```

## 说明

- 需要 Python 3，无第三方依赖。
- 元宝 Cookie 约一个月过期；HTTP 401 表示需要重新获取。
- 不绕过鉴权、不伪造 token、不使用他人 Cookie。
- 建议只用闲置账号低频自用，不要公开分享 Cookie 或把它做成公开服务。

## License

MIT
