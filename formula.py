import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

from bot import TZ

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def main():
    try:
        with open("formulas.json", encoding="utf-8") as f:
            formulas = json.load(f)
    except FileNotFoundError:
        print("formulas.json не найден")
        return

    today = datetime.now(TZ).date()
    idx = today.toordinal() % len(formulas)
    f = formulas[idx]

    text = (
        f"📐 <b>Формула дня: {f['title']}</b>\n\n"
        f"<code>{f['formula']}</code>\n\n"
        f"<i>{f['note']}</i>"
    )

    if not TOKEN or not CHAT_ID:
        print("Токен не задан:\n" + text)
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": CHAT_ID, 
        "text": text,
        "parse_mode": "HTML"
    }).encode()
    
    urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)
    print("Формула отправлена:", f['title'])

if __name__ == "__main__":
    main()