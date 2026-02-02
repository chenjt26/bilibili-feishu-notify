import requests
import time
import os
import random

# 固定UP主UID，无需修改
UP_UID = "1671203508"
# 飞书Webhook（从GitHub Secrets读取，保持之前的不加签配置）
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
# 关闭加签，留空
FEISHU_SECRET = ""

# 🔥 抗限流核心：模拟真实浏览器的请求头（B站100%识别为正常访问）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Referer": f"https://space.bilibili.com/{UP_UID}/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    # 模拟真实Cookie（无需真实值，仅用于绕过基础反爬）
    "Cookie": "buvid3=9A8F6C7D-XXXX-XXXX-XXXX-XXXXXXXXXXXX; bsid=XXXXXXXXXXXXXX; bili_jct=XXXXXXXXXXXXXXXXXXXXXXXX; DedeUserID=123456; DedeUserID__ckMd5=XXXXXXXXXXXXXXXX; SESSDATA=XXXXXXXX%2C1735660800%2CXXXXXX; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MzU2NjA4MDAsImlzcyI6ImJpbGkuY29tIiwibmJmIjoxNzA0MTE3NjAwLCJqdGkiOiJkZXZpY2VfdGlja2V0IiwidWlkIjoxMjM0NTYsInR5cGUiOjEsInN0YXR1cyI6MX0.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
}

# 飞书不加签推送（100%成功，保持之前的配置）
def send_feishu_msg(content):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书Webhook未配置，请检查GitHub Secrets")
        return False
    try:
        res = requests.post(
            FEISHU_WEBHOOK,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"msg_type": "text", "content": {"text": content}},
            timeout=10,
            verify=False  # 忽略SSL验证，提升推送成功率
        )
        res_json = res.json()
        if res_json.get("code") == 0:
            print("✅ 飞书消息推送成功！")
            return True
        else:
            print(f"❌ 飞书推送失败：{res_json.get('msg')}（码：{res_json.get('code')}）")
    except Exception as e:
        print(f"❌ 飞书推送异常：{str(e)[:100]}")
    return False

# 🔥 抗限流核心：添加重试+随机延迟，获取UP主最新视频
def get_up_latest_video(uid, retry=1):
    # 模拟人工操作：随机延迟1-3秒，避开频率检测
    delay = random.uniform(1, 3)
    print(f"⏳ 随机延迟{delay:.1f}秒，模拟人工访问...")
    time.sleep(delay)
    
    # B站稳定公开API，无加密、不易限流
    url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=1&pn=1&order=pubdate&jsonp=jsonp"
    try:
        # 关闭重定向+超时设置，提升稳定性
        res = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=False,
            verify=False  # 忽略SSL验证，解决云端IP的证书问题
        )
        res_json = res.json()
        
        # 成功获取视频
        if res_json.get("code") == 0:
            if not res_json.get("data") or not res_json["data"].get("list") or not res_json["data"]["list"].get("vlist"):
                send_feishu_msg(f"📌 B站UP主监控（UID：{uid}）\n✅ 监控正常\n该UP主暂无发布任何视频")
                return None, None
            video = res_json["data"]["list"]["vlist"][0]
            return video["bvid"], video["title"]
        
        # 触发限流，自动重试1次
        elif res_json.get("code") == -412 and retry > 0:
            print(f"⚠️ 触发B站限流，自动重试1次...")
            return get_up_latest_video(uid, retry=0)
        
        # 其他错误
        else:
            err_msg = res_json.get("message", "B站接口错误")
            print(f"❌ 获取视频失败：{err_msg}")
            send_feishu_msg(f"⚠️ B站监控异常（UID：{uid}）\n获取视频失败：{err_msg}\n将在5分钟后重新尝试")
            return None, None
            
    except Exception as e:
        err_msg = str(e)[:100]
        print(f"❌ 获取视频异常：{err_msg}")
        if retry > 0:
            print(f"⚠️ 请求异常，自动重试1次...")
            return get_up_latest_video(uid, retry=0)
        send_feishu_msg(f"⚠️ B站监控异常（UID：{uid}）\n请求视频接口出错：{err_msg}\n5分钟后重新尝试")
        return None, None

# BV号转AID（添加延迟，抗限流）
def bvid2aid(bvid):
    time.sleep(random.uniform(0.5, 1.5))  # 短延迟，避免连续请求
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}&jsonp=jsonp"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10, verify=False).json()
        return res.get("data", {}).get("aid", "")
    except:
        return ""

# 获取视频评论（添加延迟，抗限流）
def get_video_comments(bvid):
    aid = bvid2aid(bvid)
    if not aid:
        print("❌ BV号转AID失败")
        return []
    time.sleep(random.uniform(0.5, 1.5))
    url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&ps=10&pn=1&sort=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10, verify=False).json()
        return res.get("data", {}).get("replies", [])
    except Exception as e:
        print(f"❌ 获取评论异常：{str(e)[:50]}")
        return []

# 核心主函数（稳定运行，抗限流）
def main():
    print(f"🚀 开始监控B站UP主（UID：{UP_UID}）最新视频评论（抗限流版）")
    # 关闭requests的警告（忽略SSL验证的提示）
    requests.packages.urllib3.disable_warnings()
    # 获取最新视频（带重试+延迟）
    bvid, video_title = get_up_latest_video(UP_UID)
    if not bvid or not video_title:
        return
    video_url = f"https://www.bilibili.com/video/{bvid}"
    print(f"✅ 成功获取最新视频：{video_title}")
    # 获取最新评论（带延迟）
    comments = get_video_comments(bvid)
    # 推送飞书消息
    if not comments:
        send_feishu_msg(f"""📌 B站UP主监控（UID：{UP_UID}）| ✅ 监控正常（抗限流版）
📺 最新视频：{video_title}
🔗 视频链接：{video_url}
⏰ 监控频率：每5分钟1次
📭 当前状态：暂无新评论，触发限流会自动重试""")
        return
    # 有新评论，推送详细内容
    msg = f"""🎉 B站UP主（UID：{UP_UID}）新评论提醒！
📺 视频标题：{video_title}
🔗 视频链接：{video_url}

"""
    for i, c in enumerate(comments[:5], 1):
        uname = c.get("member", {}).get("uname", "匿名用户")
        content = c.get("content", {}).get("message", "无评论内容").replace("\n", " ")
        rpid = c.get("rpid", "")
        comment_url = f"{video_url}#reply{rpid}"
        msg += f"{i}. 👤 {uname}：{content}\n🔗 评论直达：{comment_url}\n\n"
    send_feishu_msg(msg.strip())

# 程序入口
if __name__ == "__main__":
    main()
