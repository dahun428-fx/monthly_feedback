import os

DESCRIPTION = "- get_pdf_filename(): 월별 피드백의 대상이 되는 대표 KPI PDF 파일명을 가져옵니다."

# Define the exact path to the target file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDE_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../storage/guide"))
TARGET_PDF_PATH = os.path.join(GUIDE_DIR, "selected_KPI.pdf")

def run():
    """
    Checks for the existence of 'storage/guide/selected_KPI.pdf' and returns the filename if it exists.
    """
    if os.path.exists(TARGET_PDF_PATH):
        return {
            "status": "success",
            "filename": "selected_KPI.pdf"
        }
    else:
        return {
            "status": "error",
            "message": "대표 KPI 파일('storage/guide/selected_KPI.pdf')이 지정되지 않았습니다. 'KPI 관리' 탭에서 먼저 파일을 지정해주세요."
        }