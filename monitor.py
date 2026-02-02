import requests
import time
import os
from hashlib import sha256
import hmac
import base64
from bilibili_api import user, sync, video

# 从GitHub Secrets读取配置（无需修改）
UP_UID = os.getenv("BILIBILI_UID")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
CHECK_INTERVAL = 60  # 单次检查间隔，不影响定时任务

# 飞书加签计算（适配飞书机器人加签，无需修改）
def get_feishu_sign(timestamp):
    if not FEISHU_SECRET:
        return ""
    secret_enc = FEISHU_SECRET.encode("utf-8")
    string_to_sign = f"{timestamp}\n{FEISHU_SECRET}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")

# 发送飞书消息（无需修改）
def send_feishu_msg(content):
    if not FEISHU_WEBHOOK:
        print("飞书Webhook未配置")
        return
    timestamp = str(int(time.time()))
    sign = get_feishu_sign(timestamp)
    headers = {"Content-Type": "application/json"}
    if sign:
        headers["timestamp"] = timestamp
        headers["sign"] = sign
    data = {
        "msg_type": "text",
        "content": {"text": content}
    }
    try:
        res = requests.post(FEISHU_WEBHOOK, headers=headers, json=data, timeout=10)
        if res.status_code == 200:
            print("飞书消息推送成功")
        else:
            print(f"飞书推送失败：{res.text}")
    except Exception as e:
        print(f"飞书推送异常：{str(e)}")

# 读取上次最后评论ID（GitHub Actions临时存储，防单次重复）
def get_last_rpid():
    try:
        with open("last_rpid.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return ""

# 保存最新评论ID
def save_last_rpid(rpid):
    with open("last_rpid.txt", "w", encoding="utf-8") as f:
        f.write(str(rpid))

# 核心：监控B站UP主最新视频评论
def monitor_comments():
    try:
        # 获取UP主信息
        u = user.User(UP_UID)
        up_info = sync(u.get_info())
        up_name = up_info["name"]
        print(f"开始监控UP主：{up_name}（UID：{UP_UID}）")

        # 获取UP主最新发布的视频（优先最新，避免抓旧视频）
        videos = sync(u.get_videos(pn=1, ps=1, order="pubdate"))
        if not videos:
            send_feishu_msg(f"⚠️ UP主{up_name}暂无公开视频，监控失败")
            return
        latest_vid = videos[0]["bvid"]
        latest_vtitle = videos[0]["title"]
        v = video.Video(bvid=latest_vid)

        # 获取视频最新评论（前20条，足够监控新增）
        comments = sync(v.get_comments(page=1, size=20, sort=0))
        if not comments.get("replies"):
            print("暂无新评论")
            return
        replies = comments["replies"]
        last_rpid = get_last_rpid()
        new_comments = []

        # 筛选新增评论（去重）
        for rep in replies:
            rpid = rep["rpid"]
            if str(rpid) != last_rpid:
                new_comments.append(rep)
            else:
                break  # 按时间排序，找到上次的ID则停止
        if not new_comments:
            print("无新增评论")
            return

        # 保存最新评论ID，防重复
        save_last_rpid(new_comments[0]["rpid"])

        # 拼接消息并推送（多条评论合并）
        msg_prefix = f"🎉 UP主【{up_name}】最新视频新评论\n视频：{latest_vtitle}\n链接：https://www.bilibili.com/video/{latest_vid}\n\n"
        msg_content = ""
        for idx, rep in enumerate(new_comments[:5]):  # 最多推送5条新增，避免刷屏
            uname = rep["member"]["uname"]
            content = rep["content"]["message"].replace("\n", " ")
            comment_link = f"https://www.bilibili.com/video/{latest_vid}#reply{rep['rpid']}"
            msg_content += f"{idx+1}. 【{uname}】：{content}\n链接：{comment_link}\n\n"
        final_msg = msg_prefix + msg_content.strip()
        send_feishu_msg(final_msg)
        print(f"推送{len(new_comments)}条新评论")

    except Exception as e:
        error_msg = f"⚠️ B站评论监控异常：{str(e)[:200]}"
        print(error_msg)
        send_feishu_msg(error_msg)

if __name__ == "__main__":
    monitor_comments()
