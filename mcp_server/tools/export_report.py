import os

DESCRIPTION = "- export_report(month: str, content: str): 생성된 피드백 보고서 내용을 월별 마크다운 파일로 저장합니다. 동일한 파일이 있으면 덮어쓰지 않고 새 버전을 만듭니다."

# 📌 보고서 저장 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../reports"))
os.makedirs(REPORT_DIR, exist_ok=True)

def run(month: str = None, content: str = None):
    """
    Args:
        month (str): 보고서 대상 월 (예: '2025-09')
        content (str): generate_feedback에서 생성된 마크다운 텍스트
    """
    if not all([month, content]):
        return {"status": "error", "message": "month와 content 인자가 모두 필요합니다."}

    # 기본 파일 경로 생성
    base_filename = f"{month}.md"
    filepath = os.path.join(REPORT_DIR, base_filename)
    
    # 파일이 이미 존재할 경우, 새 이름 찾기 (예: 2025-09 (1).md)
    counter = 1
    while os.path.exists(filepath):
        name, ext = os.path.splitext(base_filename)
        filepath = os.path.join(REPORT_DIR, f"{name} ({counter}){ext}")
        counter += 1

    # 파일 저장
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[export_report] 보고서 저장 완료: {filepath}")
    except Exception as e:
        return {"status": "error", "message": f"파일 저장 실패: {str(e)}"}

    return {
        "status": "success",
        "path": filepath
    }
