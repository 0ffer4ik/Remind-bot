import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Импортируем только то, что точно есть в ваших файлах
from bot import load, TZ
from weekly import render, send_photo

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def get_monday(now):
    """Вычисляет понедельник текущей недели (или следующей, если сегодня Вс)."""
    if now.weekday() == 6:  # Если воскресенье
        return now.date() + timedelta(days=1)
    return now.date() - timedelta(days=now.weekday())

def build_digest_text(reminders, monday):
    next_sunday = monday + timedelta(days=6)
    lines = ["📋 <b>Дедлайны на предстоящую неделю:</b>\n"]
    found = False
    for d in reminders.get("deadlines", []):
        d_date = date.fromisoformat(d["date"])
        if monday <= d_date <= next_sunday:
            found = True
            lines.append(f"• {d['text']} — <b>{d_date.strftime('%d.%m')}</b>")
    
    if not found:
        lines.append("<i>На этой неделе дедлайнов нет. Отдыхай!</i>")
    return "\n".join(lines)

def send_message(text):
    if not TOKEN or not CHAT_ID:
        print(text)
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)

def main():
    sched = load("schedule.json", None)
    reminders = load("reminders.json", {})
    now = datetime.now(TZ)
    
    # Используем локальную функцию вместо импорта из weekly
    monday = get_monday(now) 
    
    # 1. Отправляем картинку с расписанием
    png, wt_label = render(sched, monday)
    if png:
        mon = monday.strftime("%d.%m")
        sat = (monday + timedelta(days=5)).strftime("%d.%m")
        caption = f"📅 <b>Расписание на неделю {mon}–{sat}</b> · {wt_label}"
        send_photo(png, caption)
    else:
        send_message("На предстоящей неделе пар нет.")

    # 2. Отправляем дедлайны
    text = build_digest_text(reminders, monday)
    send_message(text)
    print("Дайджест отправлен")

if __name__ == "__main__":
    main()