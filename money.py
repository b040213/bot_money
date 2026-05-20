from datetime import datetime

# 允許的群組ID（之後從LINE webhook來）
ALLOW_GROUP_ID = "C04659c2a5b648d1bb6d1ba0644ab6b69"


def parse_message(text, group_id, user="unknown"):

    # 1️⃣ 先過濾群組（關鍵）
    if group_id != ALLOW_GROUP_ID:
        return None

    text = text.strip()

    # 2️⃣ 格式過濾
    if not text.startswith("/"):
        return None

    try:
        content = text[1:]
        parts = content.split()

        item = " ".join(parts[:-1])
        amount = float(parts[-1])

        return {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "item": item,
            "amount": amount,
            "user": user,
            "group_id": group_id
        }

    except:
        return None