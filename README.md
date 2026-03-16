# 월간 피드백 생성기

> 월별 할 일, KPI PDF, LLM 요약을 결합해 월간 피드백 보고서를 생성하고 Notion까지 내보내는 업무 자동화 프로젝트입니다.

---

## 1. 프로젝트 소개

### 프로젝트 개요

- 월별 업무 내역을 직접 입력하고 관리할 수 있습니다.
- KPI PDF를 업로드하고 대표 문서로 지정할 수 있습니다.
- Gemini 기반 LLM이 KPI를 요약하고 월간 피드백 보고서를 생성합니다.
- 생성된 보고서는 Markdown 파일로 저장하거나 Notion으로 내보낼 수 있습니다.
- Streamlit UI, FastAPI 기반 MCP 서버, LLM 에이전트가 함께 동작합니다.

---

### 기획 배경

- 월간 피드백이나 성과 보고서를 작성할 때 반복적으로 해야 하는 정리 작업을 줄이기 위해 만들었습니다.
- 흩어진 할 일 기록과 KPI 문서를 한 화면에서 연결해 보고서 초안을 빠르게 만들 수 있도록 구성했습니다.
- 단순 텍스트 생성이 아니라, PDF 파싱 → 요약 → 템플릿 반영 → 보고서 생성 → 내보내기 흐름까지 자동화하는 것을 목표로 했습니다.

---

### 프로젝트 목표

- 월 단위 업무 기록을 구조적으로 관리
- KPI PDF 기반 자동 요약
- 템플릿 기반 월간 피드백 초안 생성
- Notion 연동을 통한 공유 효율화
- MCP 스타일 도구 호출 구조를 활용한 LLM 에이전트 실험

---

## 2. 개발 환경 및 기술 스택

### 프레임워크 & 라이브러리

- **Frontend / UI**: Streamlit
- **Backend / Tool Server**: FastAPI, Uvicorn
- **LLM**: Google Gemini (`gemini-2.0-flash`)
- **Document Parsing**: pdfplumber
- **External Integration**: Notion API

### 언어 및 도구

- **Language**: Python
- **환경 변수 관리**: python-dotenv
- **HTTP Client**: requests
- **MCP 스타일 도구 실행 구조**: Custom FastAPI tool server

---

## 3. 핵심 기능

### 할 일 관리

- 월별 할 일 등록
- 임팩트(`high`, `mid`, `low`) 지정
- 완료 / 미완료 상태 변경
- 여러 항목 일괄 선택 후 상태 변경
- 날짜 수정 및 삭제 기능 제공

### KPI PDF 관리

- PDF 업로드 및 저장
- 저장된 PDF 목록 조회
- PDF 본문 미리보기
- 대표 KPI 파일 지정

### 월별 피드백 생성

- 대표 KPI PDF 파싱
- KPI 요약본 생성
- 선택한 월의 할 일과 KPI 요약을 결합하여 피드백 보고서 생성
- 사용자 템플릿이 있으면 해당 템플릿 우선 반영
- Markdown 다운로드 지원
- Notion 페이지로 내보내기 지원

### LLM 에이전트 채팅

- 에이전트가 툴을 한 단계씩 호출하며 작업 수행
- `get_today`, `list_todos`, `parse_pdf`, `summarize_text`, `generate_feedback`, `export_to_notion` 등의 툴을 조합해 자동화 가능

---

## 4. 동작 구조

```text
Streamlit GUI
  ├─ 할 일 / KPI / 템플릿 관리
  ├─ 보고서 생성 요청
  └─ LLM 채팅 인터페이스

LLM Agent
  ├─ 사용자 요청 해석
  ├─ 다음 단일 툴 결정
  └─ MCP 서버로 툴 실행 요청

FastAPI MCP Server
  ├─ PDF 파싱
  ├─ 텍스트 요약
  ├─ 보고서 생성
  ├─ Markdown 저장
  └─ Notion 내보내기
```

---

## 5. 프로젝트 구조

```bash
monthly_feedback/
├── client/                  # LLM 에이전트, 실행기, CLI 진입점
├── mcp_server/              # FastAPI 기반 툴 서버
│   ├── tools/               # 개별 업무 툴
│   └── utils/               # Gemini 호출 유틸
├── reports/                 # 생성된 월간 보고서 저장 경로
├── storage/
│   ├── guide/               # 대표 KPI PDF, 템플릿 저장
│   ├── pdf/                 # 업로드한 PDF 저장
│   └── todos/               # 할 일 데이터 JSON 저장
├── gui_app.py               # Streamlit 메인 앱
├── requirements.txt
└── command.txt              # 실행 참고 명령
```

---

## 6. 실행 방법

### 1) 패키지 설치

```bash
pip install -r requirements.txt
```

### 2) 환경 변수 설정

루트에 `.env` 파일을 만들고 아래 값을 설정합니다.

```env
GEMINI_API_KEY=your_gemini_api_key
NOTION_API_KEY=your_notion_api_key
NOTION_PAGE_ID=your_notion_page_id
```

### 3) MCP 서버 실행

```bash
uvicorn mcp_server.server:app --reload --port 8000
```

### 4) Streamlit 앱 실행

```bash
streamlit run gui_app.py
```

### 5) 선택 사항: CLI 에이전트 실행

```bash
python -m client.main
```

---

## 7. 사용 흐름

### 1. 할 일 입력

- `할 일 관리` 탭에서 월별 업무를 등록합니다.

### 2. KPI 문서 업로드

- `KPI 관리` 탭에서 PDF를 업로드하고 대표 KPI 파일로 지정합니다.

### 3. KPI 요약 생성

- `월별 피드백` 탭에서 대표 KPI 문서를 파싱하고 요약본을 생성합니다.

### 4. 보고서 생성

- 같은 탭에서 선택한 월의 할 일과 KPI 요약본을 기반으로 피드백 보고서를 생성합니다.

### 5. 결과 저장 / 공유

- Markdown 파일로 다운로드하거나 Notion으로 내보낼 수 있습니다.

---

## 8. 주요 MCP 툴

- `list_todos`: 저장된 할 일 목록 조회
- `list_pdf_files`: 업로드된 PDF 목록 조회
- `get_pdf_filename`: 대표 KPI 파일 확인
- `parse_pdf`: PDF 텍스트 추출
- `summarize_text`: 추출 텍스트 요약
- `get_feedback_template`: 템플릿 조회
- `generate_feedback`: 월간 피드백 보고서 생성
- `export_report`: Markdown 파일 저장
- `export_to_notion`: Notion 페이지 생성

---

## 9. 생성 결과물

- 보고서 파일: `reports/YYYY-MM.md`
- 할 일 데이터: `storage/todos/todo_list.json`
- 업로드 PDF: `storage/pdf/`
- 대표 KPI 파일: `storage/guide/selected_KPI.pdf`
- 사용자 템플릿: `storage/guide/feedback_template.md`

---

## 10. 프로젝트 특징

- UI에서 바로 사용할 수 있는 업무형 도구
- LLM 에이전트와 툴 서버를 분리한 구조
- 단순 채팅이 아니라 실제 파일/문서 흐름과 연결
- 템플릿 기반 보고서 생성으로 조직 스타일 반영 가능

---

## 11. 향후 개선 아이디어

- 월별 리포트 이력 비교 기능
- PDF 다중 선택 및 비교 요약
- 보고서 품질 평가 지표 추가
- Notion 데이터베이스 직접 연동
- 배포 환경 구성 및 사용자 인증 추가
