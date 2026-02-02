import requests
import time
import os
from hashlib import sha256
import hmac
import base64

# 从GitHub Secrets读取配置，无需修改
UP_UID = os.getenv("BILIBILI_UID") or "1671203508"
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")

# B站原生API请求头，模拟浏览器，避免被屏蔽
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/"
}

# 飞书加签计算，适配你的机器人加签，无需修改
def get_feishu_sign(timestamp):
    if not FEISHU_SECRET:
        return ""
    secret_enc = FEISHU_SECRET.encode("utf-8")
    string_to_sign = f"{timestamp}\n{FEISHU_SECRET}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")

# 发送飞书消息，无需修改
def send_feishu_msg(content):
    if not FEISHU_WEBHOOK:
        print("飞书Webhook未配置！")
        return
    timestamp = str(int(time.time()))
    sign = get_feishu_sign(timestamp)
    headers = {"Content-Type": "application/json"}
    if sign:
        headers["timestamp"] = timestamp
        headers["sign"] = sign
    data = {"msg_type": "text", "content": {"text": content}}
    try:
        res = requests.post(FEISHU_WEBHOOK, headers=headers, json=data, timeout=10)
        if res.status_code == 200 and res.json().get("code") == 0:
            print("✅ 飞书消息推送成功！")
        else:
            print(f"❌ 飞书推送失败：{res.text}")
    except Exception as e:
        print(f"❌ 飞书推送异常：{str(e)}")
        send_feishu_msg(f"⚠️ B站监控飞书推送异常：{str(e)[:150]}")

# 获取UP主最新视频（B站原生API）
def get_up_latest_video(uid):
    url = f"https://api.bilibili.com/x/space/wbi/arc/search?mid={uid}&ps=1&pn=1&order=pubdate"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") != 0:
            send_feishu_msg(f"⚠️ 获取UP主{uid}视频失败：{res.get('message')}")
            return None, None
        video_data = res["data"]["list"]["vlist"][0]
        bvid = video_data["bvid"]  # 视频BV号
        title = video_data["title"]  # 视频标题
        return bvid, title
    except Exception as e:
        send_feishu_msg(f"⚠️ 获取最新视频异常：{str(e)[:150]}")
        return None, None

# 获取视频最新评论（B站原生API）
def get_video_comments(bvid):
    # B站评论API，取最新10条
    url = f"https://api.bilibili.com/x/v2/reply/wbi?type=1&oid={get_oid_by_bvid(bvid)}&ps=10&pn=1&sort=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") != 0:
            print(f"获取评论失败：{res.get('message')}")
            return []
        return res.get("data", {}).get("replies", [])
    except Exception as e:
        print(f"获取评论异常：{str(e)}")
        return []

# 辅助：BV号转OID（B站评论API需要OID）
def get_oid_by_bvid(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    res = requests.get(url, headers=HEADERS, timeout=10).json()
    return res.get("data", {}).get("aid", "")

# 核心监控逻辑
def main():
    print(f"🚀 开始监控B站UP主（UID：{UP_UID}）最新视频评论")
    # 获取UP主最新视频
    bvid, video_title = get_up_latest_video(UP_UID)
    if not bvid or not video_title:
        return
    video_url = f"https://www.bilibili.com/video/{bvid}"
    # 获取最新评论
    comments = get_video_comments(bvid)
    if not comments:
        print("📭 暂无新评论")
        send_feishu_msg(f"📌 B站UP主监控（UID：{UP_UID}）\n最新视频：{video_title}\n{video_url}\n当前暂无新评论")
        return
    # 拼接评论消息
    msg = f"🎉 B站UP主（UID：{UP_UID}）最新视频新评论\n📺 视频：{video_title}\n🔗 视频链接：{video_url}\n\n"
    for idx, c in enumerate(comments[:5], 1):  # 最多推送5条，避免刷屏
        uname = c.get("member", {}).get("uname", "匿名用户")
        content = c.get("content", {}).get("message", "无内容").replace("\n", " ")
        rpid = c.get("rpid", "")
        comment_url = f"{video_url}#reply{rpid}"
        msg += f"{idx}. 👤 {uname}：{content}\n💬 评论链接：{comment_url}\n\n"
    # 推送飞书
    send_feishu_msg(msg.strip())

if __name__ == "__main__":
    main()
