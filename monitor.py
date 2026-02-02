import requests
import time
import os
from hashlib import sha256
import hmac
import base64

# 从GitHub Secrets读取配置，适配你的UID=1671203508
UP_UID = os.getenv("BILIBILI_UID") or "1671203508"
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")

# B站API请求头，模拟浏览器防屏蔽
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}

# 飞书官方标准加签计算
def get_feishu_sign(timestamp, secret):
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")

# 飞书消息推送（适配加签，修复时间戳）
def send_feishu_msg(content):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书Webhook未配置")
        return False
    timestamp = str(int(time.time()))
    headers = {"Content-Type": "application/json; charset=utf-8"}
    # 加签逻辑
    if FEISHU_SECRET and FEISHU_SECRET.strip():
        headers["timestamp"] = timestamp
        headers["sign"] = get_feishu_sign(timestamp, FEISHU_SECRET)
    # 发送请求
    try:
        res = requests.post(
            FEISHU_WEBHOOK,
            headers=headers,
            json={"msg_type": "text", "content": {"text": content}},
            timeout=15,
            allow_redirects=False
        )
        res_json = res.json()
        if res_json.get("code") == 0:
            print("✅ 飞书消息推送成功")
            return True
        else:
            print(f"❌ 飞书推送失败：{res_json.get('msg')}（码：{res_json.get('code')}）")
    except Exception as e:
        print(f"❌ 飞书推送异常：{str(e)[:150]}")
    return False

# 获取UP主最新视频（B站原生API）
def get_up_latest_video(uid):
    url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=1&pn=1&order=pubdate"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") != 0:
            send_feishu_msg(f"⚠️ 获取UP主视频失败：{res.get('message', '接口错误')}")
            return None, None
        video = res["data"]["list"]["vlist"][0]
        return video["bvid"], video["title"]
    except Exception as e:
        send_feishu_msg(f"⚠️ 获取最新视频异常：{str(e)[:150]}")
        return None, None

# BV号转AID（适配B站评论API）
def bvid2aid(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("data", {}).get("aid", "")
    except:
        return ""

# 获取视频最新评论
def get_video_comments(bvid):
    aid = bvid2aid(bvid)
    if not aid:
        print("❌ BV号转AID失败，无法获取评论")
        return []
    url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&ps=10&pn=1&sort=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("data", {}).get("replies", [])
    except Exception as e:
        print(f"❌ 获取评论异常：{str(e)}")
        return []

# 核心主函数
def main():
    print(f"🚀 开始监控B站UP主（UID：{UP_UID}）最新视频评论")
    # 获取最新视频
    bvid, video_title = get_up_latest_video(UP_UID)
    if not bvid or not video_title:
        print("❌ 未获取到UP主最新视频")
        return
    video_url = f"https://www.bilibili.com/video/{bvid}"
    # 获取评论
    comments = get_video_comments(bvid)
    # 推送消息
    if not comments:
        send_feishu_msg(f"📌 B站UP主监控（UID：{UP_UID}）\n✅ 监控正常\n最新视频：{video_title}\n🔗 视频链接：{video_url}\n当前暂无新评论")
        return
    # 拼接新评论消息
    msg = f"🎉 B站UP主（UID：{UP_UID}）新评论提醒\n📺 视频：{video_title}\n🔗 视频链接：{video_url}\n\n"
    for i, c in enumerate(comments[:5], 1):
        uname = c.get("member", {}).get("uname", "匿名")
        content = c.get("content", {}).get("message", "无内容").replace("\n", " ")
        rpid = c.get("rpid", "")
        msg += f"{i}. 👤 {uname}：{content}\n💬 直达：{video_url}#reply{rpid}\n\n"
    send_feishu_msg(msg.strip())

# 程序入口
if __name__ == "__main__":
    main()
