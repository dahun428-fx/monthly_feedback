import os
import json
from datetime import datetime

# --- 전역 설정 ---
TODO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "todos")
TODO_FILE = os.path.join(TODO_DIR, "todo_list.json")
os.makedirs(TODO_DIR, exist_ok=True)

KPI_STORAGE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "pdf")

def load_all_tasks():
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # 기존 주차별 데이터 형식도 처리할 수 있도록 유연성 추가
                if data and isinstance(data[0], dict) and 'week' in data[0]:
                    # 주차별 데이터를 평평한 리스트로 변환
                    flat_tasks = []
                    for week_data in data:
                        if isinstance(week_data, dict) and 'tasks' in week_data and isinstance(week_data['tasks'], list):
                            for task_item in week_data['tasks']:
                                flat_tasks.append(task_item)
                    return flat_tasks
                return data # 이미 평평한 리스트인 경우
            else:
                return [] # 알 수 없는 형식
    except (json.JSONDecodeError, IOError):
        return []

def save_all_tasks(all_tasks):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, ensure_ascii=False, indent=2)

def get_filtered_and_sorted_tasks(selected_month_current):
    all_tasks = load_all_tasks()
    all_tasks.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
    
    filtered_tasks = [t for t in all_tasks if t.get('date', '').startswith(selected_month_current)]
    return filtered_tasks

def delete_task_from_file(task_name_to_delete):
    all_tasks = load_all_tasks()
    all_tasks = [t for t in all_tasks if t.get('task') != task_name_to_delete]
    save_all_tasks(all_tasks)

def update_task_in_file(original_task_name, updated_task_data):
    all_tasks = load_all_tasks()
    for i, t in enumerate(all_tasks):
        if t.get('task') == original_task_name:
            all_tasks[i] = updated_task_data
            break
    save_all_tasks(all_tasks)
