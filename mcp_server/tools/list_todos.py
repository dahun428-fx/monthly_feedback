import os
import json
from datetime import datetime

DESCRIPTION = "- list_todos(month: str, today: bool): 특정 달의 Todo 목록을 조회. month='YYYY-MM' 형식. today=True 이면 현재 달을 조회."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TODO_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../storage/todos"))
os.makedirs(TODO_DIR, exist_ok=True)

def run(month: str = None, today: bool = False):
    # today=True가 우선순위가 가장 높다.
    if today:
        month = datetime.now().strftime("%Y-%m")
    
    if not month:
        return {"status": "error", "message": "month 또는 today=True 가 필요합니다."}

    filepath = os.path.join(TODO_DIR, f"{month}.json")

    if not os.path.exists(filepath):
        return {"status": "error", "message": f"Todo 파일이 존재하지 않습니다: {filepath}"}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            todos = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"파일 로드 실패: {e}"}

    return {
        "status": "success",
        "todos": todos,
    }
