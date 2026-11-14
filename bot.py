import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TZ = ZoneInfo("Europe/Saratov")
LEAD_MINUTES = 90      # за сколько минут до первой пары писать
WINDOW_MINUTES = 50    # допуск на опоздание/раннее срабатывание GitHub
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def week_type(today, anchor):
    """Ч (числитель) или З (знаменатель)."""
    monday = today - timedelta(days=today.weekday())
    anchor_monday = anchor - timedelta(days=anchor.weekday())
    weeks = (monday - anchor_monday).days // 7
    return "Ч" if weeks % 2 == 0 else "З"


def lessons_for(sched, today):
    s = sched["settings"]
    wt = week_type(today, date.fromisoformat(s["week_anchor"]))
    my_group = s.get("language_group")
    tags = set(s.get("tags", []))
    result, seen_placeholder = [], set()
    for l in sched["lessons"]:
        if l["day"] != today.weekday():
            continue
        if l.get("week") and l["week"] != wt:
            continue
        if l.get("tag") and l["tag"] not in tags:
            continue
        if "from" in l and today < date.fromisoformat(l["from"]):
            continue
        if "until" in l and today > date.fromisoformat(l["until"]):
            continue
        if l.get("group"):
            if my_group:
                if l["group"] != my_group:
                    continue
            else:  # подгруппа не выбрана: одна общая строка вместо 12
                if l["start"] in seen_placeholder:
                    continue
                seen_placeholder.add(l["start"])
                l = {**l, "name": "Иностранный язык (подгруппа не выбрана)",
                     "teacher": "", "room": ""}
        result.append(l)
    result.sort(key=lambda x: x["start"])
    return result, wt


def build_message(sched, reminders, today):
    lessons, wt = lessons_for(sched, today)
    lines = []
    if lessons:
        lines.append(f"⏰ Первая пара в {lessons[0]['start']}.")
    wt_name = "числитель" if wt == "Ч" else "знаменатель"
    lines.append(f"{DAYS[today.weekday()].capitalize()}, {today.strftime('%d.%m')} · неделя: {wt_name}")
    if lessons:
        lines.append("")
        for l in lessons:
            extra = ", ".join(x for x in (l["room"], l["teacher"]) if x)
            lines.append(f"{l['start']}–{l['end']} {l['name']}" + (f" ({extra})" if extra else ""))
    else:
        lines.append("\nПар сегодня нет.")

    soon = []
    for d in reminders.get("deadlines", []):
        left = (date.fromisoformat(d["date"]) - today).days
        if 0 <= left <= 7:
            when = "сегодня!" if left == 0 else f"через {left} дн."
            soon.append((left, f"• {d['text']} — {when}"))
    if soon:
        lines.append("\nСкоро дедлайны:")
        lines += [t for _, t in sorted(soon)]
    return "\n".join(lines), lessons


def should_send(lessons, now, manual):
    if manual:
        return True
    if not lessons:
        return False
    h, m = map(int, lessons[0]["start"].split(":"))
    first = now.replace(hour=h, minute=m, second=0, microsecond=0)
    target = first - timedelta(minutes=LEAD_MINUTES)
    return abs((now - target).total_seconds()) <= WINDOW_MINUTES * 60


def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)
    except urllib.error.HTTPError as e:
        print("Ответ Телеграма:", e.read().decode())
        raise


def main():
    sched = load("schedule.json", None)
    reminders = load("reminders.json", {})
    now = datetime.now(TZ)
    message, lessons = build_message(sched, reminders, now.date())
    manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if not should_send(lessons, now, manual):
        print("Сейчас не время напоминать:", now.strftime("%H:%M"))
    elif not TOKEN or not CHAT_ID:
        print("Токен не задан, показываю текст:\n" + message)
    else:
        send(message)
        print("Отправлено")


if __name__ == "__main__":
    main()
