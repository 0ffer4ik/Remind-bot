import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PER_DAY = 3  # сколько вопросов за один раз


def pick(questions, today):
    """Каждый день новые вопросы по кругу, пока не закончится список."""
    start = (today.toordinal() * PER_DAY) % len(questions)
    return [questions[(start + i) % len(questions)] for i in range(PER_DAY)]


def send_poll(q):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPoll"
    body = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "question": q["q"],
        "options": json.dumps(q["options"], ensure_ascii=False),
        "type": "quiz",
        "correct_option_id": q["correct"],
        "explanation": q["explain"],
        "is_anonymous": "false",
    }).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30)
    except urllib.error.HTTPError as e:
        print("Ответ Телеграма:", e.read().decode())
        raise


def main():
    with open("quiz.json", encoding="utf-8") as f:
        questions = json.load(f)
    today = datetime.now(ZoneInfo("Europe/Saratov")).date()
    for q in pick(questions, today):
        if TOKEN and CHAT_ID:
            send_poll(q)
        else:
            print("Токена нет, вопрос:", q["q"])
    print("Готово")


if __name__ == "__main__":
    main()
