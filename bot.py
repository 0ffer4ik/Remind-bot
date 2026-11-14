import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("9119990409:AAGy73lyCXc85OXXnnjz-HttmDUSHNRJYhY")
CHAT_ID = os.environ.get("1129650289")
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def build_message(data, today):
    lines = [f"Доброе утро! Сегодня {DAYS[today.weekday()]}, {today.strftime('%d.%m')}."]

    # Регулярные дела этого дня недели (0 = понедельник)
    todays = [w["text"] for w in data.get("weekly", []) if w["day"] == today.weekday()]
    if todays:
        lines.append("\nСегодня:")
        lines += [f"• {t}" for t in todays]

    # Дедлайны: показываем за 7 дней и ближе
    soon = []
    for d in data.get("deadlines", []):
        left = (date.fromisoformat(d["date"]) - today).days
        if 0 <= left <= 7:
            when = "сегодня!" if left == 0 else f"через {left} дн."
            soon.append((left, f"• {d['text']} — {when}"))
    if soon:
        lines.append("\nСкоро дедлайны:")
        lines += [text for _, text in sorted(soon)]

    if not todays and not soon:
        return None  # нечего напоминать, молчим
    return "\n".join(lines)


def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)


def main():
    with open("reminders.json", encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(ZoneInfo("Europe/Saratov")).date()
    message = build_message(data, today)
    if message is None:
        print("Сегодня напоминать нечего")
    elif not TOKEN or not CHAT_ID:
        print("Токен не задан, показываю текст:\n" + message)
    else:
        send(message)
        print("Отправлено")


if __name__ == "__main__":
    main()
