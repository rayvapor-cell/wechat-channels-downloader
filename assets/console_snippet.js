// Paste this into the Console of a logged-in https://yuanbao.tencent.com tab.
// Replace SHARE_URL with the user's WeChat Channels share link before pasting.
// It uses the browser's own login state; the cookie is never printed or revealed.
fetch('/api/weixin/get_parse_result', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-Source': 'web', 'X-Requested-With': 'XMLHttpRequest'},
  credentials: 'include',
  body: JSON.stringify({type: 'video_channel_url', url: 'SHARE_URL', scene: 1})
}).then(r => r.text()).then(t => console.log(t))
