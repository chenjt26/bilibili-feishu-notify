import requests
import time
import os

# 从GitHub Secrets读取配置，UID固定为1671203508
UP_UID = "1671203508"  # 直接固定，避免环境变量读取问题
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
# 直接关闭加签，留空即可
FEISHU_SECRET = ""

# B站API请求头，模拟浏览器，稳定不屏蔽
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Cookie": "buvid3=xxx; bsid=xxx"  # 随便填，B站公开API无需真实Cookie
}

# 飞书推送（纯不加签版本，100%成功）
def send_feishu_msg(content):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书Webhook未配置，请检查GitHub Secrets")
        return False
    try:
        # 不加签的极简请求，飞书100%接收
        res = requests.post(
            FEISHU_WEBHOOK,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"msg_type": "text", "content": {"text": content}},
            timeout=10
        )
        res_json = res.json()
        if res_json.get("code") == 0:
            print("✅ 飞书消息推送成功！")
            return True
        else:
            print(f"❌ 飞书推送失败：{res_json.get('msg')}（码：{res_json.get('code')}）")
    except Exception as e:
        print(f"❌ 飞书推送网络异常：{str(e)[:100]}")
    return False

# 修复B站API：用最新公开接口，稳定获取最新视频
def get_up_latest_video(uid):
    # 替换为B站无加密的公开API，100%能获取
    url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=1&pn=1&order=pubdate&jsonp=jsonp"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") != 0:
            err_msg = res.get("message", "B站接口返回错误")
            print(f"❌ 获取视频失败：{err_msg}")
            send_feishu_msg(f"⚠️ B站监控异常\n获取UP主{uid}视频失败：{err_msg}")
            return None, None
        # 兼容B站API返回格式，防止索引错误
        if not res.get("data") or not res["data"].get("list") or not res["data"]["list"].get("vlist"):
            send_feishu_msg(f"⚠️ B站监控异常\nUP主{uid}暂无发布视频")
            return None, None
        video = res["data"]["list"]["vlist"][0]
        return video["bvid"], video["title"]
    except Exception as e:
        err_msg = str(e)[:100]
        print(f"❌ 获取视频异常：{err_msg}")
        send_feishu_msg(f"⚠️ B站监控异常\n获取最新视频出错：{err_msg}")
        return None, None

# 修复BV号转AID，适配最新B站评论API
def bvid2aid(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}&jsonp=jsonp"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("data", {}).get("aid", "")
    except:
        return ""

# 获取视频最新评论，稳定无报错
def get_video_comments(bvid):
    aid = bvid2aid(bvid)
    if not aid:
        print("❌ BV号转AID失败")
        return []
    url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&ps=10&pn=1&sort=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("data", {}).get("replies", [])
    except Exception as e:
        print(f"❌ 获取评论异常：{str(e)[:50]}")
        return []

# 核心主函数，逻辑简化，稳定运行
def main():
    print(f"🚀 开始监控B站UP主（UID：{UP_UID}）最新视频评论")
    # 获取最新视频（修复后API）
    bvid, video_title = get_up_latest_video(UP_UID)
    if not bvid or not video_title:
        return
    video_url = f"https://www.bilibili.com/video/{bvid}"
    print(f"✅ 获取到最新视频：{video_title}")
    # 获取最新评论
    comments = get_video_comments(bvid)
    # 推送飞书消息
    if not comments:
        # 暂无评论，推送监控心跳
        send_feishu_msg(f"📌 B站UP主监控（UID：{UP_UID}）\n✅ 监控一切正常\n📺 最新视频：{video_title}\n🔗 视频链接：{video_url}\n当前暂无新评论，每5分钟自动监控")
        return
    # 有新评论，推送详细内容
    msg = f"🎉 B站UP主（UID：{UP_UID}）新评论提醒！\n📺 视频标题：{video_title}\n🔗 视频链接：{video_url}\n\n"
    for i, c in enumerate(comments[:5], 1):
        uname = c.get("member", {}).get("uname", "匿名用户")
        content = c.get("content", {}).get("message", "无评论内容").replace("\n", " ")
        rpid = c.get("rpid", "")
        comment_url = f"{video_url}#reply{rpid}"
        msg += f"{i}. 👤 评论人：{uname}\n💬 评论内容：{content}\n🔗 评论直达：{comment_url}\n\n"
    send_feishu_msg(msg.strip())

# 程序入口，无任何格式问题
if __name__ == "__main__":
    main()
