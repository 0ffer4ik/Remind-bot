import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PER_DAY = 3

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def pick(questions, state):
    idx = state.get("idx", -1) + 1
    picked = []
    for i in range(PER_DAY):
        q_idx = (idx + i) % len(questions)
        picked.append(questions[q_idx])
    state["idx"] = (idx + PER_DAY - 1) % len(questions)
    return picked, state

def send_poll(q):
    if not TOKEN or not CHAT_ID:
        print("Токен не задан, вопрос:", q["q"])
        return
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
    questions = load_json("quiz.json", [])
    if not questions:
        print("Нет вопросов")
        return
    state = load_json("quiz_state.json", {"idx": -1})
    
    picked, new_state = pick(questions, state)
    for q in picked:
        send_poll(q)
    
    save_json("quiz_state.json", new_state)
    print(f"Отправлено {len(picked)} вопросов, новый idx: {new_state['idx']}")

if __name__ == "__main__":
    main()