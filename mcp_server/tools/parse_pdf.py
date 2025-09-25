import os
import pdfplumber

DESCRIPTION = "- parse_pdf(filename: str = None): PDF 파일의 텍스트를 추출합니다. filename에 '@designated'를 전달하면 지정된 대표 KPI 파일을 읽습니다."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_STORAGE_ROOT = os.path.normpath(os.path.join(BASE_DIR, "../../storage/pdf"))
GUIDE_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../storage/guide"))

def run(filename: str = None):
    pdf_path = None

    if filename == '@designated':
        pdf_path = os.path.join(GUIDE_DIR, "selected_KPI.pdf")
        if not os.path.exists(pdf_path):
            return {"status": "error", "message": "대표 KPI 파일('selected_KPI.pdf')이 지정되지 않았습니다. 'KPI 관리' 탭에서 먼저 지정해주세요."}
        # For logging, use the designated name
        filename = "selected_KPI.pdf"
    elif filename:
        # Security check to prevent path traversal
        if '/' in filename or '\\' in filename:
            return {"status": "error", "message": "filename에는 순수한 파일명만 입력해야 합니다."}
        pdf_path = os.path.join(PDF_STORAGE_ROOT, filename)
        if not os.path.exists(pdf_path):
            return {"status": "error", "message": f"PDF 파일을 찾을 수 없습니다: {pdf_path}"}
    else:
        # If no filename is given, scan the default PDF storage
        if not os.path.exists(PDF_STORAGE_ROOT):
            return {"status": "error", "message": f"PDF 루트 폴더를 찾을 수 없습니다: {PDF_STORAGE_ROOT}"}
        
        pdf_files = [f for f in os.listdir(PDF_STORAGE_ROOT) if f.endswith(".pdf")]
        
        if len(pdf_files) == 1:
            filename = pdf_files[0]
            pdf_path = os.path.join(PDF_STORAGE_ROOT, filename)
            print(f"[parse_pdf] 폴더에서 유일한 PDF 파일 '{filename}'을 대상으로 지정합니다.")
        elif len(pdf_files) == 0:
            return {"status": "error", "message": "처리할 PDF 파일이 storage/pdf 폴더에 없습니다."}
        else:
            return {"status": "error", "message": f"여러 개의 PDF 파일이 있습니다. 어떤 파일을 처리할지 filename으로 지정해주세요. (파일 목록: {pdf_files})"}

    print(f"[parse_pdf] PDF 파일 처리 시작: {filename}")

    try:
        extracted = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted.append(text.strip())
        
        full_text = "\n".join(extracted)

        if not full_text:
            return {"status": "success", "text": "[추출 실패: 파일에 텍스트가 없음]"}

    except Exception as e:
        return {"status": "error", "message": f"PDF 처리 중 오류 발생: {e}"}

    print(f"[parse_pdf] 처리 완료: {filename}")

    return {
        "status": "success",
        "text": full_text
    }
