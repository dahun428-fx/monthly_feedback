import os

DESCRIPTION = "- get_feedback_template(): 월간 피드백 생성 시 참고할 사용자 지정 템플릿을 가져옵니다."

# Define the exact path to the template file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDE_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../storage/guide"))
TEMPLATE_FILE = os.path.join(GUIDE_DIR, "feedback_template.md")

def run():
    """
    Checks for 'feedback_template.md' and returns its content if it exists.
    Returns an empty template if the file does not exist.
    """
    template_content = ""
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                template_content = f.read()
            return {
                "status": "success",
                "template": template_content
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"템플릿 파일 읽기 오류: {e}"
            }
    else:
        # It's not an error if the template doesn't exist.
        return {
            "status": "success",
            "template": "" # Return empty string
        }