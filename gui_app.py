import os
from pathlib import Path
from datetime import datetime
import json
import uuid
import shutil
import streamlit as st
from dotenv import load_dotenv
from client.llm_agent import agent_step, get_system_prompt

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
GUIDE_DIR = APP_ROOT / "storage" / "guide"
TODO_DIR.mkdir(parents=True, exist_ok=True)
KPI_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
GUIDE_DIR.mkdir(parents=True, exist_ok=True)
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

def truncate_text(text, max_lines=3):
    if not isinstance(text, str):
        text = str(text)
    lines = text.split('\n')
    if len(lines) > max_lines:
        return '\n'.join(lines[:max_lines]) + '\n...'
    return text

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
# Tabs (Replaced with Radio)
# ------------------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "할 일 관리"

# Define tab options
tab_options = ["할 일 관리", "KPI 관리", "월별 피드백", "LLM 채팅"]

# Use st.radio to simulate tabs
st.session_state.active_tab = st.radio(
    "Navigation", 
    tab_options, 
    horizontal=True, 
    label_visibility="collapsed",
    index=tab_options.index(st.session_state.active_tab) # Ensure state is respected
)

# ========================
# Content for selected tab
# ========================

if st.session_state.active_tab == "할 일 관리":
    st.header("할 일 관리")

    from calendar import monthrange

    # --- 현재 선택 월의 기본값/경계 계산 ---
    sel_year, sel_month = map(int, st.session_state.selected_month.split("-"))
    last_day = monthrange(sel_year, sel_month)[1]

    today_date = datetime.now().date()
    default_date = (
        today_date if today_date.strftime("%Y-%m") == st.session_state.selected_month
        else datetime(sel_year, sel_month, 1).date()
    )

    # 일괄 입력 날짜(달력) 세션 상태 준비
    if "bulk_task_date" not in st.session_state:
        st.session_state.bulk_task_date = default_date

    st.subheader("일괄 입력 날짜")

    # 1) 기본 달력
    st.session_state.bulk_task_date = st.date_input(
        "새로 추가되는 할 일의 기본 날짜를 선택하세요",
        value=st.session_state.bulk_task_date,
        key="bulk_task_date_date_input",
    )


    # ---- 입력: Enter만으로 추가 (버튼 제거) ----
    def _add_task_on_enter():
        val = (st.session_state.get("new_task_input") or "").strip()
        if not val:
            st.warning("할 일을 입력하세요.")
            return
        all_tasks = load_all_tasks()
        all_tasks.append({
            "id": str(uuid.uuid4()),
            "task": val,
            "status": "pending",
            "impact": st.session_state.get("impact_select", "mid"),
            "date": st.session_state.bulk_task_date.strftime("%Y-%m-%d"),
        })
        save_all_tasks(all_tasks)
        st.session_state.new_task_input = ""  # 입력창 초기화
        st.success(f"[{st.session_state.bulk_task_date.strftime('%Y-%m-%d')}] 할 일이 추가되었습니다.")


    col1, col2 = st.columns([6, 3])
    with col1:
        st.text_input(
            "새로운 할 일",
            key="new_task_input",
            placeholder="할 일을 입력 후 Enter",
            on_change=_add_task_on_enter,   # ✅ Enter 시 자동 등록
        )
    with col2:
        # 임팩트와 입력창을 같은 행에 유지 (버튼 없음)
        st.selectbox(
            "임팩트",
            ["high", "mid", "low"],
            index=1,
            key="impact_select"
        )

    # ---- 목록 표시 (선택 월만) ----
    st.subheader(f"{selected_month}의 할 일")
    tasks = [t for t in load_all_tasks() if t.get("date", "").startswith(selected_month)]
    if not tasks:
        st.info("현재 월의 할 일 없음")
    else:
        # 최신 날짜 우선 정렬
        tasks_sorted = sorted(tasks, key=lambda x: (x.get("date", ""), x.get("task", "")), reverse=True)

        all_items = load_all_tasks()
        all_by_id = {x.get("id"): x for x in all_items}

        for t in tasks_sorted:
            # id 보정
            if "id" not in t or not t["id"]:
                t["id"] = str(uuid.uuid4())
            t_id = t["id"]

            cols = st.columns([0.55, 0.15, 0.15, 0.15])
            with cols[0]:
                status_label = "✅" if t.get("status") == "done" else "⏳"
                st.markdown(f"{status_label} **{t.get('date','')}** - {t.get('task','')}")
                st.caption(f"임팩트: **{t.get('impact','mid')}** | 상태: **{t.get('status','pending')}**")

            with cols[1]:
                # 완료 토글 버튼
                is_done = t.get("status") == "done"
                toggle_label = "되돌리기" if is_done else "완료"
                if st.button(toggle_label, key=f"done_{t_id}", help="상태 토글"):
                    t["status"] = "pending" if is_done else "done"
                    all_by_id[t_id] = t
                    save_all_tasks(list(all_by_id.values()))
                    st.rerun()

            with cols[2]:
                # 팝오버: 버튼을 누르면 그 자리 위/옆에 달력이 뜸
                pop = st.popover("날짜변경")  # key 없이
                with pop:
                    # 현재 값 기본 세팅
                    current_date = t.get("date") or f"{selected_month}-01"
                    try:
                        base_dt = datetime.strptime(current_date, "%Y-%m-%d").date()
                    except Exception:
                        base_dt = datetime(sel_year, sel_month, 1).date()

                    # ✅ min/max 제한 제거 → 연/월 자유 변경 가능
                    new_dt = st.date_input(
                        "날짜 선택",
                        value=base_dt,
                        key=f"edit_date_{t_id}",
                    )

                    btn1, btn2 = st.columns(2)
                    with btn1:
                        if st.button("저장", key=f"save_date_{t_id}"):
                            t["date"] = new_dt.strftime("%Y-%m-%d")
                            all_by_id[t_id] = t
                            save_all_tasks(list(all_by_id.values()))
                            st.success("날짜 변경 완료")
                            st.rerun()
                    with btn2:
                        st.button("취소", key=f"cancel_date_{t_id}")


            with cols[3]:
                if st.button("삭제", key=f"del_{t_id}"):
                    save_all_tasks([x for x in all_by_id.values() if x.get("id") != t_id])
                    st.warning("삭제됨")
                    st.rerun()


elif st.session_state.active_tab == "KPI 관리":
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

        col1, col2 = st.columns(2)
        with col1:
            if st.button("선택한 PDF 미리보기"):
                with st.spinner("PDF 파싱 중..."):
                    res = parse_pdf.run(filename=selected_pdf)
                if res.get("status") == "success":
                    st.text_area("PDF 내용 미리보기", value=res.get("text", ""), height=300)
                else:
                    st.error(f"PDF 파싱 오류: {res.get('message', '알 수 없는 오류')}")
        with col2:
            if st.button("대표 KPI 파일로 지정"):
                if not selected_pdf:
                    st.warning("지정할 PDF를 목록에서 선택하세요.")
                else:
                    source_path = KPI_STORAGE_ROOT / selected_pdf
                    dest_path = GUIDE_DIR / "selected_KPI.pdf"
                    try:
                        shutil.copy(source_path, dest_path)
                        st.success(f"'{selected_pdf}'을(를) 대표 KPI 파일로 지정했습니다.")
                    except Exception as e:
                        st.error(f"파일 지정 중 오류 발생: {e}")
    else:
        st.info("저장된 PDF가 없습니다. 상단에서 업로드하세요.")

elif st.session_state.active_tab == "월별 피드백":
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

elif st.session_state.active_tab == "LLM 채팅":
    st.header("LLM 에이전트와 대화")

    # Initialize chat state
    if "llm_messages" not in st.session_state:
        # LLM이 사용하는 메시지 형식
        st.session_state.llm_messages = [{"role": "user", "parts": [{"text": get_system_prompt("Streamlit GUI")}]}]
    if "ui_messages" not in st.session_state:
        # UI에 표시하기 위한 메시지
        st.session_state.ui_messages = [{"role": "assistant", "content": "안녕하세요! 월간 보고서 작성에 대해 무엇을 도와드릴까요?"}]
    if "llm_context" not in st.session_state:
        st.session_state.llm_context = {}

    # Display UI messages
    for message in st.session_state.ui_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("명령을 입력하세요..."):
        # Add user message to UI and LLM histories
        st.session_state.ui_messages.append({"role": "user", "content": prompt})
        st.session_state.llm_messages.append({"role": "user", "parts": [{"text": f"사용자 명령어: {prompt}"}]})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        # Loop until the agent provides a final answer
        while True:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("🤔 Thinking...")

                # Execute one step of the agent
                new_llm_messages, new_context, ui_message, is_final, wip_content = agent_step(
                    st.session_state.llm_messages, 
                    st.session_state.llm_context
                )

                # Update state for the next iteration
                st.session_state.llm_messages = new_llm_messages
                st.session_state.llm_context = new_context
                
                # Show the result of the current step
                placeholder.markdown(ui_message)
                if wip_content:
                    with st.expander("작업 상세 내용 보기", expanded=False):
                        # Truncate and display the content
                        display_content = json.dumps(wip_content, indent=2, ensure_ascii=False)
                        st.code(display_content, language='json')

            
            # Add the agent's step output to the UI history
            st.session_state.ui_messages.append({"role": "assistant", "content": ui_message})

            if is_final:
                break