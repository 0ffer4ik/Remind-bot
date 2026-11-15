import os
import urllib.parse
import urllib.request
from datetime import date, datetime

from bot import load, TZ

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_message(text):
    if not TOKEN or not CHAT_ID:
        print(text)
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)

def main():
    reminders = load("reminders.json", {})
    today = datetime.now(TZ).date()
    
    for d in reminders.get("deadlines", []):
        d_date = date.fromisoformat(d["date"])
        left = (d_date - today).days
        if left == 7:
            msg = (
                f"⚠️ <b>Напоминание о дедлайне:</b>\n\n"
                f"Ровно через неделю (<b>{d_date.strftime('%d.%m')}</b>) нужно сдать:\n"
                f"🔹 <i>{d['text']}</i>"
            )
            send_message(msg)
            print(f"Отправлено напоминание: {d['text']}")
            break # отправляем только одно, чтобы не спамить

if __name__ == "__main__":
    main()