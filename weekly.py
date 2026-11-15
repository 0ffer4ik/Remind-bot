import os
from datetime import date, datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

# ─── Палитра ─────────────────────────────────────────────────
BG         = (0, 0, 0)
CARD_LEC   = (24, 14, 18)
CARD_PRA   = (14, 20, 16)
CARD_EMPTY = (8, 8, 10)
EDGE       = (230, 45, 55)
EDGE_DIM   = (70, 22, 26)
EDGE_HEAD  = (230, 45, 55)
TEXT_MAIN  = (242, 242, 248)
TEXT_SUB   = (150, 150, 165)
TEXT_DIM   = (90, 90, 100)
PILL_BG    = (28, 10, 13)
PILL_EDGE  = (230, 45, 55)

# ─── Шрифты ──────────────────────────────────────────────────
FONT_DIRS = [
    "fonts",
    "/usr/share/fonts/truetype/consolas",
    "/mnt/c/Windows/Fonts",
    "C:/Windows/Fonts",
    "C:\\Windows\\Fonts",
    "/usr/share/fonts/truetype/inconsolata",
    "/usr/share/fonts/truetype/dejavu",
]


def _font(size, bold=False):
    names = (
        ["consolab.ttf", "Inconsolata-Bold.ttf", "DejaVuSansMono-Bold.ttf"]
        if bold else
        ["consola.ttf", "Inconsolata-Regular.ttf", "DejaVuSansMono.ttf"]
    )
    for d in FONT_DIRS:
        for n in names:
            try:
                return ImageFont.truetype(os.path.join(d, n), size)
            except OSError:
                continue
    return ImageFont.load_default()


def short_name(name):
    return SHORT_NAMES.get(name, name)


def short_room(room):
    return room.replace(" корпус, ", "-").replace(" корпус", "")


def _fit(text, font, max_w, draw):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return (text + "…") if text else ""


_glow_cache = {}


def _glow(size, radius, blur=10, color=EDGE, alpha=90):
    key = (size, radius, blur, color, alpha)
    if key in _glow_cache:
        return _glow_cache[key]
    w, h = size
    pad = blur * 2
    g = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    d.rounded_rectangle([(pad, pad), (pad + w, pad + h)],
                        radius=radius, fill=color + (alpha,))
    res = (g.filter(ImageFilter.GaussianBlur(blur)), pad)
    _glow_cache[key] = res
    return res


def week_monday(now):
    """В воскресенье — уже следующая неделя, иначе — текущая."""
    if now.weekday() == 6:
        return now.date() + timedelta(days=1)
    return now.date() - timedelta(days=now.weekday())


def build_grid(sched, monday):
    """grid[slot_idx][day_idx] = lesson или None."""
    grid = []
    for slot_start, _ in SLOTS:
        row = []
        for d in range(6):
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

    # ─── Геометрия: квадратные ячейки ────────────────────────
    cell = 140
    cell_gap = 10
    time_col = 96
    header_h = 44
    title_h = 72
    pad = 24
    cols = len(DAY_SHORT)

    w = pad * 2 + time_col + cols * cell + (cols - 1) * cell_gap
    h = (pad * 2 + title_h + header_h + 10
         + len(rows) * cell + (len(rows) - 1) * cell_gap + 16)

    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    f_title  = _font(22, bold=True)
    f_day    = _font(14, bold=True)
    f_time   = _font(14, bold=True)
    f_time_s = _font(11)
    f_name   = _font(13, bold=True)
    f_sub    = _font(11)
    f_meta   = _font(11)
    f_footer = _font(11)

    # ─── Заголовок ───────────────────────────────────────────
    mon = monday.strftime("%d.%m")
    sat = (monday + timedelta(days=5)).strftime("%d.%m")
    draw.text((pad, pad), f"{mon} — {sat}", font=f_title, fill=TEXT_MAIN)

    pill_text = f"{'Ч' if wt == 'Ч' else 'З'} · {wt_label}"
    pw = draw.textlength(pill_text, font=f_day) + 26
    px = pad + draw.textlength(f"{mon} — {sat}", font=f_title) + 20
    py = pad + 8
    draw.rounded_rectangle([(px, py), (px + pw, py + 32)],
                           radius=16, fill=PILL_BG, outline=EDGE, width=2)
    draw.text((px + 13, py + 9), pill_text, font=f_day, fill=EDGE)

    draw.rounded_rectangle([(pad, pad + title_h - 12),
                            (w - pad, pad + title_h - 8)],
                           radius=2, fill=EDGE)

    # ─── Шапка: дни недели ───────────────────────────────────
    y0 = pad + title_h
    for c, dname in enumerate(DAY_SHORT):
        x = pad + time_col + c * (cell + cell_gap)
        draw.rounded_rectangle([(x, y0), (x + cell, y0 + header_h)],
                               radius=12, fill=(16, 10, 12),
                               outline=EDGE_HEAD, width=2)
        tw = draw.textlength(dname, font=f_day)
        draw.text((x + (cell - tw) / 2, y0 + (header_h - 18) / 2),
                  dname, font=f_day, fill=TEXT_MAIN)

    # ─── Тело ────────────────────────────────────────────────
    for r, (slot_start, slot_end) in enumerate(rows):
        y = y0 + header_h + 10 + r * (cell + cell_gap)

        draw.text((pad + 4, y + 18), slot_start, font=f_time, fill=TEXT_MAIN)
        draw.text((pad + 4, y + 40), slot_end, font=f_time_s, fill=TEXT_SUB)

        for c in range(cols):
            x = pad + time_col + c * (cell + cell_gap)
            lesson = grid_active[r][c]

            if not lesson:
                draw.rounded_rectangle([(x, y), (x + cell, y + cell)],
                                       radius=16, fill=CARD_EMPTY,
                                       outline=EDGE_DIM, width=2)
                continue

            glow, gpad = _glow((cell, cell), radius=16)
            img.paste(glow, (x - gpad, y - gpad), glow)

            fill = CARD_LEC if lesson.get("type") == "лекция" else CARD_PRA
            draw.rounded_rectangle([(x, y), (x + cell, y + cell)],
                                   radius=16, fill=fill,
                                   outline=EDGE, width=2)

            tx = x + 12
            tw = cell - 22

            name = _fit(short_name(lesson["name"]), f_name, tw, draw)
            draw.text((tx, y + 14), name, font=f_name, fill=TEXT_MAIN)

            teacher = (lesson.get("teacher") or "").split(" ")[0]
            if teacher:
                draw.text((tx, y + 36), _fit(teacher, f_sub, tw, draw),
                          font=f_sub, fill=TEXT_SUB)

            room = short_room(lesson.get("room") or "")
            if room:
                rw = draw.textlength(room, font=f_meta) + 16
                ry = y + cell - 30
                draw.rounded_rectangle([(tx, ry), (tx + rw, ry + 22)],
                                       radius=11, fill=PILL_BG,
                                       outline=PILL_EDGE, width=1)
                draw.text((tx + 8, ry + 5), room, font=f_meta, fill=EDGE)

    # ─── Футер ───────────────────────────────────────────────
    ft = "142 · мех-мат"
    fw = draw.textlength(ft, font=f_footer)
    draw.text((w - pad - fw, h - pad - 2), ft, font=f_footer, fill=TEXT_DIM)

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