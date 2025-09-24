import os

DESCRIPTION = "- list_pdf_files(): storage/pdf 폴더에 있는 모든 PDF 파일의 목록을 반환합니다."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_STORAGE_ROOT = os.path.normpath(os.path.join(BASE_DIR, "../../storage/pdf"))

def run():
    if not os.path.exists(PDF_STORAGE_ROOT):
        return {"status": "error", "message": f"PDF 루트 폴더를 찾을 수 없습니다: {PDF_STORAGE_ROOT}"}

    try:
        pdf_files = [f for f in os.listdir(PDF_STORAGE_ROOT) if f.endswith(".pdf")]
    except Exception as e:
        return {"status": "error", "message": f"PDF 폴더를 읽는 중 오류 발생: {e}"}

    return {
        "status": "success",
        "files": pdf_files
    }
