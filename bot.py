from flask import Flask, request, abort
from datetime import datetime
import json
import os
import gspread

from google.oauth2.service_account import Credentials
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# ======================
# LINE
# ======================
LINE_CHANNEL_ACCESS_TOKEN = "NdQgEeqPR/bzgOEX1gvydpikg3WIAyA//hZaF19OFrLj3NvBBKcqLr7rnmLXjpL9rDejK1vsbJJqKrTJoD0ENEh6gUq8n/4U7P6l+MUDH02Ax634f1nUD8aEastG785XN38SoJwtyMTjFfNvyttLkQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "e2d716d3b728530a1697951ace1047e5"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ======================
# Google Sheets
# ======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

client = gspread.authorize(creds)

SPREADSHEET_ID = os.environ["SHEET_ID"]
spreadsheet = client.open_by_key("1t95fFq7niKoxW2b2vH8fE3n4t1TgcqbBiBANvKI5ri0")

# users sheet（一定要先建立）
users_ws = spreadsheet.worksheet("users")


# ======================
# 工具：查 sheet
# ======================
def get_user_sheet(user_id):
    records = users_ws.get_all_records()
    for r in records:
        if r["user_id"] == user_id:
            return r["sheet_name"]
    return None


def set_user_sheet(user_id, sheet_name):
    users_ws.append_row([user_id, sheet_name])


# ======================
# 記帳解析
# ======================
def parse(text, user, group_id):
    text = text.strip()

    if not text.startswith("/"):
        return None

    try:
        content = text[1:]
        parts = content.split()

        item = " ".join(parts[:-1])
        amount = float(parts[-1])

        return {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "item": item,
            "amount": amount,
            "user": user
        }
    except:
        return None


# ======================
# 寫入 sheet
# ======================
def write(data, sheet_name):
    ws = spreadsheet.worksheet(sheet_name)

    ws.append_row([
        data["date"],
        data["item"],
        data["amount"],
        data["user"]
    ])

    update_total(ws)


# ======================
# 更新總和
# ======================
def update_total(ws):
    values = ws.col_values(3)

    total = 0
    for v in values[1:]:
        try:
            total += float(v)
        except:
            pass

    row = len(values) + 1

    ws.update_cell(row, 2, "總和")
    ws.update_cell(row, 3, total)


# ======================
# 刪除最後一筆
# ======================
def delete_last_row(ws):
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return False

    ws.delete_rows(len(rows))
    return True


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
# LINE 主邏輯
# ======================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    text = event.message.text.strip()
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", "private")

    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
    except:
        user_name = "unknown"

    # ======================
    # /新增 帳本
    # ======================
    if text.startswith("/新增"):
        sheet_name = text.replace("/新增", "").strip()

        if not sheet_name:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage("用法：/新增 A123")
            )
            return

        if get_user_sheet(user_id):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage("你已經有帳本了")
            )
            return

        ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
        ws.append_row(["日期", "品項", "金額", "記錄人"])

        set_user_sheet(user_id, sheet_name)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(f"已建立帳本：{sheet_name}")
        )
        return


    # ======================
    # /刪除
    # ======================
    if text == "/刪除":
        sheet_name = get_user_sheet(user_id)

        if not sheet_name:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage("請先 /新增 帳本")
            )
            return

        ws = spreadsheet.worksheet(sheet_name)

        ok = delete_last_row(ws)

        msg = "已刪除最後一筆" if ok else "沒有資料"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(msg)
        )
        return


    # ======================
    # /記帳
    # ======================
    data = parse(text, user_name, group_id)

    if data:
        sheet_name = get_user_sheet(user_id)

        if not sheet_name:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage("請先 /新增 帳本")
            )
            return

        write(data, sheet_name)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("記帳成功")
        )
        return


# ======================
# 啟動
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
