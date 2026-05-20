from flask import Flask, request, abort
from datetime import datetime

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ======================
# LINE 設定（v2 穩定版）
# ======================
LINE_CHANNEL_ACCESS_TOKEN = "NdQgEeqPR/bzgOEX1gvydpikg3WIAyA//hZaF19OFrLj3NvBBKcqLr7rnmLXjpL9rDejK1vsbJJqKrTJoD0ENEh6gUq8n/4U7P6l+MUDH02Ax634f1nUD8aEastG785XN38SoJwtyMTjFfNvyttLkQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "e2d716d3b728530a1697951ace1047e5"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ======================
# Google Sheet
# ======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)
sheet = client.open_by_key("1t95fFq7niKoxW2b2vH8fE3n4t1TgcqbBiBANvKI5ri0").sheet1

# ======================
# 允許群組
# ======================
ALLOW_GROUP_ID = "C04659c2a5b648d1bb6d1ba0644ab6b69"


# ======================
# 記帳解析
# ======================
def parse(text, user, group_id):

    if group_id != ALLOW_GROUP_ID:
        return None

    text = text.strip()

    if not text.startswith("/"):
        return None
    
    try:
        content = text[1:]
        parts = content.split()

        item = " ".join(parts[:-1])
        raw_amount = parts[-1]

        if raw_amount.startswith("+"):
            amount = float(raw_amount)
        else:
            amount = -float(raw_amount)
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "item": item,
            "amount": amount,
            "user": user,
        }

    except:
        return None


# ======================
# 寫入 Sheet
# ======================
def write(data):
    delete_last_row()
    sheet.append_row([
        data["date"],
        data["item"],
        data["amount"],
        data["user"],
    ])
    update_total()

# ======================
# Webhook
# ======================
@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# ======================
# LINE 訊息處理
# ======================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    text = event.message.text

    # 安全取得 user / group
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", "private")

    # 取得暱稱（v2 正確寫法）
    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
    except:
        user_name = "謝小豬"

    # 記帳解析
    data = parse(text, user_name, group_id)
    
    if text.strip() == "/刪除":
        ok = delete_last_row()

        msg = "✔ 已刪除最近一筆" if ok else "⚠ 沒有資料可刪"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg)
        )
        return
    if data:
        write(data)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✔ 已記帳完成")
        )

def delete_last_row():
    rows = sheet.get_all_values()

    if len(rows) <= 1:
        return False

    last_index = len(rows)

    sheet.delete_rows(last_index)
    return True
def update_total():
    values = sheet.col_values(3)

    total = 0
    for v in values[1:]:
        try:
            total += float(v)
        except:
            pass

    last_data_row = len([v for v in values if v != ""])

    total_row = last_data_row + 1

    # 先清掉舊總和（避免重複）

    sheet.update_cell(total_row, 2, "總和")
    sheet.update_cell(total_row, 3, total)
# ======================
# 啟動
# ======================
if __name__ == "__main__":
    app.run(port=5000)