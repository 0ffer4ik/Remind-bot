import json
import os
import urllib.error
import urllib.parse
import urllib.request
import html
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TZ = ZoneInfo("Europe/Saratov")
LEAD_MINUTES = 90      # за сколько минут до первой пары писать
WINDOW_MINUTES = 50    # допуск на опоздание/раннее срабатывание GitHub
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

LAT, LON = 51.53, 46.03  # Саратов
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    "&timezone=Europe%2FSaratov&forecast_days=3"
)

def weather_text(code):
    if code == 0: return "☀️ ясно"
    if code in (1, 2, 3): return "⛅ облачно"
    if code in (45, 48): return "🌫 туман"
    if code in (51, 53, 55, 56, 57): return "🌦 морось"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "🌧 дождь"
    if code in (71, 73, 75, 77, 85, 86): return "❄️ снег"
    if code in (95, 96, 99): return "⛈ гроза"
    return "🌡 погода"

def parse_weather(data, day):
    """Строка про погоду на день или None."""
    d = data["daily"]
    i = d["time"].index(day.isoformat())
    lo, hi = round(d["temperature_2m_min"][i]), round(d["temperature_2m_max"][i])
    rain = d["precipitation_probability_max"][i] or 0
    line = f"{weather_text(d['weathercode'][i])}, {lo:+d}…{hi:+d}°C, осадки {rain}%"
    if rain >= 50:
        line += " — возьми зонт"
    return line

def fetch_weather(day):
    try:
        url = WEATHER_URL.format(lat=LAT, lon=LON)
        with urllib.request.urlopen(url, timeout=15) as r:
            return parse_weather(json.load(r), day)
    except Exception as e:
        print("Погода недоступна:", e)
        return None

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
        if l["day"] != today.weekday(): continue
        if l.get("week") and l["week"] != wt: continue
        if l.get("tag") and l["tag"] not in tags: continue
        if "from" in l and today < date.fromisoformat(l["from"]): continue
        if "until" in l and today > date.fromisoformat(l["until"]): continue
        if l.get("group"):
            if my_group:
                if l["group"] != my_group: continue
            else:
                if l["start"] in seen_placeholder: continue
                seen_placeholder.add(l["start"])
                l = {**l, "name": "Иностранный язык (подгруппа не выбрана)",
                     "teacher": "", "room": ""}
        result.append(l)
    result.sort(key=lambda x: x["start"])
    return result, wt

def build_message(sched, reminders, today, evening=False, weather=None):
    lessons, wt = lessons_for(sched, today)
    lines = []
    
    # Заголовок
    if evening:
        title = f"🌙 <b>Завтра, {DAYS[today.weekday()]} {today.strftime('%d.%m')}</b>"
    else:
        title = f"☀️ <b>Сегодня, {DAYS[today.weekday()]} {today.strftime('%d.%m')}</b>"
        
    wt_name = "числитель" if wt == "Ч" else "знаменатель"
    lines.append(f"{title} · {wt_name}")
    
    if weather:
        lines.append(f"<i>{html.escape(weather)}</i>")
        
    if lessons:
        lines.append(f"\n⏰ <b>Первая пара в {lessons[0]['start']}</b>\n")
        
        # Сами пары в цитате
        sched_lines = []
        for l in lessons:
            name = html.escape(l['name'])
            room = html.escape(l.get('room', ''))
            teacher = html.escape(l.get('teacher', ''))
            
            time_str = f"<code>{l['start']}–{l['end']}</code>"
            extra = " · ".join(filter(None, [room, teacher]))
            
            if extra:
                sched_lines.append(f"{time_str} <b>{name}</b>\n<i>{extra}</i>")
            else:
                sched_lines.append(f"{time_str} <b>{name}</b>")
                
        lines.append("<blockquote>" + "\n\n".join(sched_lines) + "</blockquote>")
        lines.append(f"<i>Всего пар: {len(lessons)}, до {lessons[-1]['end']}.</i>")
    else:
        lines.append("\n📭 <b>Пар нет.</b>")

    # Дедлайны
    soon = []
    for d in reminders.get("deadlines", []):
        left = (date.fromisoformat(d["date"]) - today).days
        if 0 <= left <= 7:
            when = "сегодня!" if left == 0 else f"через {left} дн."
            soon.append((left, f"• {html.escape(d['text'])} — {when}"))
            
    if soon:
        lines.append("\n⏳ <b>Скоро дедлайны:</b>")
        lines += [t for _, t in sorted(soon)]
        
    return "\n".join(lines), lessons

def should_send(lessons, now, manual):
    if manual: return True
    if not lessons: return False
    h, m = map(int, lessons[0]["start"].split(":"))
    first = datetime.combine(now.date(), time(h, m), tzinfo=TZ)
    target = first - timedelta(minutes=LEAD_MINUTES)
    return abs((now - target).total_seconds()) <= WINDOW_MINUTES * 60

def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": CHAT_ID, 
        "text": text,
        "parse_mode": "HTML"  # ← Включаем HTML-форматирование
    }).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)
    except urllib.error.HTTPError as e:
        print("Ответ Телеграма:", e.read().decode())
        raise

def main():
    sched = load("schedule.json", None)
    reminders = load("reminders.json", {})
    now = datetime.now(TZ)
    event = os.environ.get("GITHUB_EVENT_NAME")
    manual = event == "workflow_dispatch"
    mode = (os.environ.get("MODE") or "").strip()
    if mode not in ("morning", "evening"):
        mode = "evening" if now.hour >= 18 else "morning"
    evening = mode == "evening"

    day = now.date() + timedelta(days=1) if evening else now.date()
    weather = fetch_weather(day)
    message, lessons = build_message(sched, reminders, day, evening, weather)

    if evening:
        ok = manual or bool(lessons)
    else:
        ok = should_send(lessons, now, manual)

    # Для отладки в GitHub Actions
    print(f"now={now.strftime('%H:%M')} mode={mode} evening={evening} "
          f"day={day} lessons={len(lessons)} ok={ok}")

    if not ok:
        print("Сейчас не время напоминать.")
    elif not TOKEN or not CHAT_ID:
        print("Токен не задан, показываю текст:\n" + message)
    else:
        send(message)
        print("Отправлено")

if __name__ == "__main__":
    main()