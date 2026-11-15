import os
from datetime import date, datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

from bot import load, week_type, lessons_for

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TZ = ZoneInfo("Europe/Saratov")

SLOTS = [
    ("08:20", "09:50"), ("10:00", "11:35"), ("12:05", "13:40"),
    ("13:50", "15:25"), ("15:35", "17:10"), ("17:20", "18:40"),
    ("18:45", "20:05"), ("20:10", "21:30"),
]
DAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

SHORT_NAMES = {
    "Информационные технологии и программирование": "ИТиП",
    "Практика по изучению дополнительных глав математики. Часть 1": "Квитка",
    "Практика по изучению дополнительных глав математики. Часть 2": "Кувардина",
    "Практический курс иностранного языка": "Иностр. яз.",
    "Иностранный язык (английский)": "Англ.",
    "Иностранный язык (немецкий)": "Нем.",
    "Общая физическая подготовка": "ОФП",
    "Физическая культура и спорт": "Физ-ра",
    "Основы Российской государственности": "ОРГ",
    "Введение в учебный процесс": "Введ. в уч. пр.",
    "Кураторский час": "Кур. час",
    "Введение в языкознание (переводчики)": "Языкознание",
    "Web-дизайн: основы композиции и цветоведения": "Web: композиция",
    "Web-дизайн: введение в web-разметку": "Web: разметка",
    "Web-дизайн: введение в типографику и вёрстку печатного текста (дистанционно)": "Web: типографика",
    "Русский язык как иностранный": "РКИ",
    "Математика": "Математика",
}

def short_name(name):
    return SHORT_NAMES.get(name, name)

def short_room(room):
    return room.replace(" корпус, ", "-").replace(" корпус", "")

def fit_text(text, font, max_width, draw):
    """Обрезает строку с «…», чтобы влезла в ячейку."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return (text + "…") if text else ""

def week_monday(now):
    """Понедельник той недели, что показываем. В воскресенье — уже следующей."""
    if now.weekday() == 6:
        return now.date() + timedelta(days=1)
    return now.date() - timedelta(days=now.weekday())

def build_grid(sched, monday):
    """grid[slot_idx][day_idx] = lesson или None."""
    grid = []
    for slot_start, _ in SLOTS:
        row = []
        for d in range(6):  # Пн–Сб
            day = monday + timedelta(days=d)
            lessons, _ = lessons_for(sched, day)
            cell = next((l for l in lessons if l["start"] == slot_start), None)
            row.append(cell)
        grid.append(row)
    return grid

def render(sched, monday):
    wt = week_type(monday, date.fromisoformat(sched["settings"]["week_anchor"]))
    wt_label = "числитель" if wt == "Ч" else "знаменатель"

    grid = build_grid(sched, monday)
    active = [i for i in range(len(SLOTS)) if any(grid[i])]
    if not active:
        return None, wt_label

    rows = [SLOTS[i] for i in active]
    grid_active = [grid[i] for i in active]

    day_col, time_col, row_h, header_h = 180, 100, 100, 44
    pad, title_h = 10, 50
    w = pad * 2 + time_col + len(DAY_SHORT) * day_col
    h = pad * 2 + title_h + header_h + len(rows) * row_h

    img = Image.new("RGB", (w, h), (250, 250, 250))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except OSError:
        font = font_sm = font_bold = font_title = ImageFont.load_default()

    mon = monday.strftime("%d.%m")
    sat = (monday + timedelta(days=5)).strftime("%d.%m")
    title = f"Расписание {mon}–{sat} · {wt_label}"
    draw.text((pad, pad), title, font=font_title, fill=(20, 20, 20))

    y0 = pad + title_h
    # Шапка
    draw.rectangle([(pad, y0), (pad + time_col, y0 + header_h)],
                   fill=(220, 220, 220), outline=(120, 120, 120))
    draw.text((pad + 10, y0 + 12), "Время", font=font_bold, fill=(0, 0, 0))
    for i, d in enumerate(DAY_SHORT):
        x = pad + time_col + i * day_col
        draw.rectangle([(x, y0), (x + day_col, y0 + header_h)],
                       fill=(220, 220, 220), outline=(120, 120, 120))
        draw.text((x + 10, y0 + 12), d, font=font_bold, fill=(0, 0, 0))

    # Тело
    for r, (slot_start, slot_end) in enumerate(rows):
        y = y0 + header_h + r * row_h
        draw.rectangle([(pad, y), (pad + time_col, y + row_h)],
                       fill=(240, 240, 240), outline=(150, 150, 150))
        draw.text((pad + 8, y + 10), slot_start, font=font, fill=(0, 0, 0))
        draw.text((pad + 8, y + 32), slot_end, font=font_sm, fill=(100, 100, 100))

        for c in range(len(DAY_SHORT)):
            x = pad + time_col + c * day_col
            lesson = grid_active[r][c]
            fill = (255, 255, 255)
            if lesson:
                fill = (220, 235, 255) if lesson.get("type") == "лекция" else (225, 245, 225)
            draw.rectangle([(x, y), (x + day_col, y + row_h)],
                           fill=fill, outline=(150, 150, 150))
            if lesson:
                name = fit_text(short_name(lesson["name"]), font_sm, day_col - 16, draw)
                teacher = (lesson.get("teacher") or "").split(" ")[0]
                room = short_room(lesson.get("room") or "")
                extra = " · ".join(filter(None, [teacher, room]))
                extra = fit_text(extra, font_sm, day_col - 16, draw)
                draw.text((x + 8, y + 8), name, font=font_sm, fill=(0, 0, 0))
                if extra:
                    draw.text((x + 8, y + 30), extra, font=font_sm, fill=(80, 80, 80))

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue(), wt_label

def send_photo(png, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    files = {"photo": ("schedule.png", png, "image/png")}
    data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"}
    r = requests.post(url, files=files, data=data, timeout=60)
    if not r.ok:
        print(r.status_code, r.text)
        r.raise_for_status()

def main():
    sched = load("schedule.json", None)
    if not sched:
        print("schedule.json не найден")
        return

    now = datetime.now(TZ)
    monday = week_monday(now)
    png, wt_label = render(sched, monday)
    if png is None:
        print("На этой неделе пар нет")
        return

    mon = monday.strftime("%d.%m")
    sat = (monday + timedelta(days=5)).strftime("%d.%m")
    caption = f"📅 Расписание на {mon}–{sat} · <b>{wt_label}</b>"

    if TOKEN and CHAT_ID:
        send_photo(png, caption)
        print("Отправлено")
    else:
        with open("schedule.png", "wb") as f:
            f.write(png)
        print("PNG сохранён в schedule.png")

if __name__ == "__main__":
    main()