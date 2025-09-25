import os
from pathlib import Path
from datetime import datetime
import json
import uuid
import streamlit as st
from dotenv import load_dotenv

# === 외부 도구 ===
from mcp_server.tools import (
    parse_pdf, summarize_text, generate_feedback,
    export_report, export_to_notion
)

# ------------------------
# 경로/스토리지 설정
# ------------------------
APP_ROOT = Path(__file__).resolve().parent
TODO_DIR = APP_ROOT / "storage" / "todos"
KPI_STORAGE_ROOT = APP_ROOT / "storage" / "pdf"
TODO_DIR.mkdir(parents=True, exist_ok=True)
KPI_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
TODO_FILE = TODO_DIR / "todo_list.json"

# .env 로드
load_dotenv()

# ------------------------
# 유틸
# ------------------------
def ensure_unique_name(dirpath: Path, filename: str) -> str:
    base, ext = os.path.splitext(filename or "uploaded.pdf")
    if ext.lower() != ".pdf":
        ext = ".pdf"
    candidate = f"{base}{ext}"
    counter = 1
    while (dirpath / candidate).exists():
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate

def load_all_tasks():
    if not TODO_FILE.exists():
        return []
    try:
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 과거 주차 구조 → 평탄화
        if isinstance(data, list) and data and isinstance(data[0], dict) and "week" in data[0]:
            flat = []
            for wk in data:
                if isinstance(wk, dict) and isinstance(wk.get("tasks"), list):
                    flat.extend(wk["tasks"])
            data = flat

        tasks = data if isinstance(data, list) else []

        # id 보정
        changed = False
        for t in tasks:
            if isinstance(t, dict) and "id" not in t:
                t["id"] = str(uuid.uuid4())
                changed = True

        if changed:
            save_all_tasks(tasks)

        return tasks
    except Exception:
        return []

def save_all_tasks(all_tasks):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, ensure_ascii=False, indent=2)

# ------------------------
# Streamlit UI
# ------------------------
st.set_page_config(page_title="월간 피드백 생성기", layout="wide")
st.sidebar.title("월간 피드백 생성기")

# 상태 초기화
for key, default in [
    ("selected_month", datetime.now().strftime("%Y-%m")),
    ("selected_kpi_pdf", None),
    ("kpi_summary", None),
    ("generated_report", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# 월 셀렉터
all_tasks_for_months = load_all_tasks()
months = sorted({t.get("date","")[:7] for t in all_tasks_for_months if t.get("date")}, reverse=True)
current_month = datetime.now().strftime("%Y-%m")
if current_month not in months:
    months = [current_month] + months
selected_month = st.sidebar.selectbox(
    "월 선택",
    options=months,
    index=months.index(st.session_state.selected_month) if st.session_state.selected_month in months else 0,
)
st.session_state.selected_month = selected_month

# ------------------------
# Tabs
# ------------------------
tab_todo, tab_kpi, tab_feedback = st.tabs(["할 일 관리", "KPI 관리", "월별 피드백"])

# ========================
# 탭 1: 할 일 관리
# ========================
with tab_todo:
    st.header("할 일 관리")

    # 추가
    col1, col2, col3 = st.columns([6, 2, 1])
    with col1:
        new_task = st.text_input("새로운 할 일", key="new_task_input")
    with col2:
        impact = st.selectbox("임팩트", ["high","mid","low"], index=1, key="impact_select")
    with col3:
        if st.button("추가"):
            if new_task.strip():
                all_tasks = load_all_tasks()
                all_tasks.append({
                    "id": str(uuid.uuid4()),
                    "task": new_task.strip(),
                    "status": "pending",
                    "impact": impact,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                })
                save_all_tasks(all_tasks)
                st.success("할 일이 추가되었습니다.")
                st.experimental_rerun()

    st.subheader(f"{selected_month}의 할 일")
    tasks = [t for t in load_all_tasks() if t.get("date","").startswith(selected_month)]
    if not tasks:
        st.info("현재 월의 할 일 없음")
    else:
        changed = False
        for t in sorted(tasks, key=lambda x: x.get("date",""), reverse=True):
            if "id" not in t:
                t["id"] = str(uuid.uuid4())
                changed = True
            t_id = t["id"]
            cols = st.columns([0.7, 0.15, 0.15])
            with cols[0]:
                checked = st.checkbox(
                    f"{t.get('date','')} - {t.get('task','')}",
                    value=(t.get("status") == "done"),
                    key=f"chk_{t_id}",
                )
                new_status = "done" if checked else "pending"
                if new_status != t.get("status"):
                    t["status"] = new_status
                    changed = True
            with cols[1]:
                st.write(f"임팩트: **{t.get('impact','mid')}**")
            with cols[2]:
                if st.button("삭제", key=f"del_{t_id}"):
                    save_all_tasks([x for x in load_all_tasks() if x.get("id") != t_id])
                    st.warning("삭제됨")
                    st.experimental_rerun()

        if changed:
            # 현재 월의 변경사항을 전체 파일에 반영
            all_items = load_all_tasks()
            by_id = {x.get("id"): x for x in all_items}
            for t in tasks:
                by_id[t["id"]] = t
            save_all_tasks(list(by_id.values()))

# ========================
# 탭 2: KPI 관리
# ========================
with tab_kpi:
    st.header("KPI PDF 관리")

    # --- 업로드는 '제출' 눌렀을 때만 수행 (무한 업로드 방지) ---
    with st.form("pdf_upload_form", clear_on_submit=True):
        up = st.file_uploader("PDF 파일 업로드", type=["pdf"], key="pdf_uploader")
        submitted = st.form_submit_button("업로드")

    if submitted:
        if up is None:
            st.warning("업로드할 PDF를 선택하세요.")
        else:
            final_name = ensure_unique_name(KPI_STORAGE_ROOT, up.name)
            final_path = KPI_STORAGE_ROOT / final_name
            with open(final_path, "wb") as f:
                f.write(up.getbuffer())
            st.session_state.selected_kpi_pdf = final_name
            st.success(f"업로드 완료: {final_name}")

    # 저장된 PDF 목록 (업로드 기능 없음, 선택·미리보기만)
    pdf_files = [f.name for f in KPI_STORAGE_ROOT.glob("*.pdf")]
    pdf_files.sort(key=lambda n: (KPI_STORAGE_ROOT / n).stat().st_mtime, reverse=True)

    if pdf_files:
        selected_pdf = st.selectbox(
            "저장된 PDF",
            options=pdf_files,
            index=pdf_files.index(st.session_state.selected_kpi_pdf)
                  if st.session_state.selected_kpi_pdf in pdf_files else 0,
            key="pdf_select",
        )
        st.session_state.selected_kpi_pdf = selected_pdf

        if st.button("선택한 PDF 미리보기"):
            with st.spinner("PDF 파싱 중..."):
                res = parse_pdf.run(filename=selected_pdf)  # 도구는 "파일명만" 받는다고 가정
            if res.get("status") == "success":
                st.text_area("PDF 내용 미리보기", value=res.get("text", ""), height=300)
            else:
                st.error(f"PDF 파싱 오류: {res.get('message', '알 수 없는 오류')}")
    else:
        st.info("저장된 PDF가 없습니다. 상단에서 업로드하세요.")

# ========================
# 탭 3: 월별 피드백
# ========================
with tab_feedback:
    st.header("월별 피드백 보고서")

    # 상태/메시지 영역 (항상 같은 위치에 하나만)
    fb_status = st.empty()

    # KPI 요약 생성
    if st.button("KPI 요약본 생성"):
        if not st.session_state.get("selected_kpi_pdf"):
            fb_status.error("KPI PDF를 먼저 선택하세요.")
        else:
            with st.spinner("PDF 파싱 중..."):
                parse_res = parse_pdf.run(filename=st.session_state.selected_kpi_pdf)
            if parse_res.get("status") != "success":
                fb_status.error(f"PDF 파싱 오류: {parse_res.get('message', '파싱 실패')}")
            else:
                kpi_text = parse_res.get("text", "")
                with st.spinner("요약 생성 중..."):
                    sum_res = summarize_text.run(text_to_summarize=kpi_text)
                if sum_res.get("status") == "success":
                    st.session_state.kpi_summary = sum_res.get("summary", "")
                    fb_status.success("KPI 요약 완료")
                else:
                    fb_status.error(f"요약 오류: {sum_res.get('message', '요약 실패')}")

    st.text_area("KPI 요약본", value=st.session_state.get("kpi_summary") or "", height=200)

    # 피드백 보고서 생성
    if st.button("피드백 보고서 생성"):
        tasks = [t for t in load_all_tasks() if t.get("date","").startswith(st.session_state.selected_month)]
        if not tasks:
            fb_status.error("현재 월의 할 일 없음")
        elif not st.session_state.get("kpi_summary"):
            fb_status.error("KPI 요약본 먼저 생성하세요.")
        else:
            todos_json = json.dumps(tasks, ensure_ascii=False, indent=2)
            with st.spinner("보고서 생성 중..."):
                rep_res = generate_feedback.run(
                    month=st.session_state.selected_month,
                    todos=todos_json,
                    kpi_summary=st.session_state.kpi_summary
                )
            if rep_res.get("status") == "success":
                st.session_state.generated_report = rep_res.get("content", "")
                fb_status.success("보고서 생성 완료")
            else:
                fb_status.error(f"보고서 오류: {rep_res.get('message', '보고서 생성 실패')}")

    st.text_area("생성된 보고서", value=st.session_state.get("generated_report") or "", height=350)

    colA, colB, colC = st.columns(3)

    # 진행 플래그로 버튼 중복 클릭 방지
    is_exporting = st.session_state.get("is_exporting_notion", False)

    with colA:
        generated_report = st.session_state.get("generated_report")
        st.download_button(
            label="파일로 다운로드",
            data=generated_report if generated_report else "",
            file_name=f"{st.session_state.selected_month}.md",
            mime="text/markdown",
            disabled=not generated_report,
            help="보고서를 먼저 생성해야 다운로드할 수 있습니다."
        )

    with colB:
        # disabled로 중복 실행 방지
        if st.button("Notion으로 내보내기", disabled=is_exporting, key="btn_export_notion"):
            if not st.session_state.get("generated_report"):
                fb_status.error("생성된 보고서 없음")
            else:
                st.session_state["is_exporting_notion"] = True
                with st.spinner("Notion 업로드 중..."):
                    res = export_to_notion.run(
                        month=st.session_state.selected_month,
                        content=st.session_state.generated_report
                    )
                st.session_state["is_exporting_notion"] = False

                if res.get("status") == "success":
                    fb_status.success(f"업로드 완료: {res.get('url')}")
                else:
                    fb_status.error(f"Notion 오류: {res.get('message', '업로드 실패')}")
    with colC:
        try:
            st.link_button("Notion 이동", "https://www.notion.so/TEST-PAGE-27809ae27c27807da3d2e6cd7e74b836")
        except Exception:
            # 구버전 호환: 일반 링크로 대체
            st.markdown(
                "[Notion 이동](https://www.notion.so/TEST-PAGE-27809ae27c27807da3d2e6cd7e74b836)",
                unsafe_allow_html=True
            )