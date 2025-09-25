import os
import json

DESCRIPTION = "- list_todos(): storage/todos/todo_list.json 파일에서 모든 Todo 목록을 조회합니다."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TODO_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../storage/todos"))
TODO_FILE = os.path.join(TODO_DIR, "todo_list.json")

def run():
    """
    storage/todos/todo_list.json 파일에서 모든 todo 목록을 읽어옵니다.
    """
    if not os.path.exists(TODO_FILE):
        return {"status": "error", "message": f"Todo 파일이 존재하지 않습니다: {TODO_FILE}"}

    try:
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            todos = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"파일 로드 실패: {e}"}

    return {
        "status": "success",
        "todos": todos,
    }
