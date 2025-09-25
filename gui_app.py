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
    "할일 내역 월 선택",
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
tab_options = ["할 일 관리", "KPI 관리", "월별 피드백", "템플릿 관리", "LLM 채팅"]

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

        # 선택된 날짜 (YYYY-MM-DD)
        selected_date = st.session_state.bulk_task_date
        # 현재 시간 붙이기
        now_time = datetime.now().strftime("%H:%M:%S")
        full_datetime = f"{selected_date.strftime('%Y-%m-%d')} {now_time}"

        all_tasks.append({
            "id": str(uuid.uuid4()),
            "task": val,
            "status": "pending",
            "impact": st.session_state.get("impact_select", "mid"),
            "date": full_datetime,   # ✅ YYYY-MM-DD hh:mm:ss 저장
        })

        save_all_tasks(all_tasks)
        st.session_state.new_task_input = ""  # 입력창 초기화
        st.success(f"[{full_datetime}] 할 일이 추가되었습니다.")



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
    selected_month = st.session_state.selected_month  # 안전하게 지역변수로
    st.subheader(f"{selected_month}의 할 일")

    # 현재 월의 할 일만 로드
    tasks = [t for t in load_all_tasks() if t.get("date", "").startswith(selected_month)]

    if not tasks:
        st.info("현재 월의 할 일 없음")
    else:
        # 최신 날짜 우선 정렬
        tasks_sorted = sorted(
            tasks, key=lambda x: (x.get("date", ""), x.get("task", "")), reverse=True
        )

        # 전체 원본(저장용) 로딩
        all_items = load_all_tasks()
        all_by_id = {x.get("id"): x for x in all_items}

        # === 상단 일괄 버튼 영역 직전 ===
        # 화면의 현재 선택 상태 추정
        all_selected_now = (
            len(tasks_sorted) > 0 and
            all(st.session_state.get(f"sel_{t.get('id')}", False) for t in tasks_sorted)
        )

        # 세션 키 사전 초기화
        if "_prev_select_all" not in st.session_state:
            st.session_state["_prev_select_all"] = all_selected_now
        if "select_all_state" not in st.session_state:
            st.session_state["select_all_state"] = all_selected_now

        col_bulk0, col_bulk1, col_bulk2, col_bulk3 = st.columns([0.15, 0.2, 0.2, 0.45])
        with col_bulk0:
            select_all = st.checkbox(
                "전체",
                key="select_all_state",
                help="현재 목록의 모든 항목을 선택/해제",
            )
            if st.session_state["select_all_state"] != st.session_state["_prev_select_all"]:
                for t in tasks_sorted:
                    t_id = t.get("id")
                    if t_id:
                        st.session_state[f"sel_{t_id}"] = st.session_state["select_all_state"]
                st.session_state["_prev_select_all"] = st.session_state["select_all_state"]
                st.rerun()


        with col_bulk1:
            bulk_done = st.button("완료", key="bulk_set_done", help="선택 항목을 완료 처리")
        with col_bulk2:
            bulk_pending = st.button("미완료", key="bulk_set_pending", help="선택 항목을 미완료로 되돌리기")
        with col_bulk3:
            # 현재 선택된 수 재계산(위에서 토글했을 수 있으므로)
            sel_count = sum(st.session_state.get(f"sel_{t.get('id')}", False) for t in tasks_sorted)
            st.caption(f"선택됨: **{sel_count}건**")



        # === 목록 렌더링 ===
        # 일괄 상태 변경 처리
        if bulk_done or bulk_pending:
            target_status = "done" if bulk_done else "pending"

            # 선택된 항목 수 체크
            selected_ids = [
                t.get("id") for t in tasks_sorted
                if st.session_state.get(f"sel_{t.get('id')}", False)
            ]
            if not selected_ids:
                st.warning("일괄 처리할 항목을 선택하세요.")
            else:
                changed = False
                for t_id in selected_ids:
                    item = all_by_id.get(t_id)
                    if not item:
                        continue
                    # status 기본값 보정
                    if "status" not in item or item["status"] not in ("pending", "done"):
                        item["status"] = "pending"
                    if item["status"] != target_status:
                        item["status"] = target_status
                        all_by_id[t_id] = item
                        changed = True

                if changed:
                    # 모든 아이템(현재 월 외 항목 포함)을 통째로 저장
                    save_all_tasks(list(all_by_id.values()))
                    st.success(f"선택한 {len(selected_ids)}건을 '{target_status}' 상태로 변경했습니다.")
                else:
                    st.info("변경할 상태가 없습니다.")

                st.rerun()

        for t in tasks_sorted:
            # id 보정
            if "id" not in t or not t["id"]:
                t["id"] = str(uuid.uuid4())
            t_id = t["id"]

            # 4열: [체크박스 | 본문 | 날짜변경 | 삭제]
            cols = st.columns([0.07, 0.48, 0.23, 0.22])

            # (1) 선택 체크박스
            with cols[0]:
                # (목록의 개별 체크박스 부분)
                st.checkbox(
                    "선택",                         # ← 빈 문자열 금지
                    key=f"sel_{t_id}",
                    help="일괄 처리용 선택",
                    label_visibility="collapsed",   # ← 화면에선 숨김
                )



            # (2) 본문(상태/텍스트)
            with cols[1]:
                status_label = "✅" if t.get("status") == "done" else "⏳"
                st.markdown(f"{status_label} **{t.get('date','')}** - {t.get('task','')}")
                st.caption(f"임팩트: **{t.get('impact','mid')}** | 상태: **{t.get('status','pending')}**")

            # (3) 날짜 변경(팝오버)
            with cols[2]:
                pop = st.popover("날짜변경")
                with pop:
                    current_date = t.get("date") or f"{selected_month}-01"
                    date_only = current_date.split(" ")[0]  # "YYYY-MM-DD hh:mm:ss" → "YYYY-MM-DD"
                    try:
                        base_dt = datetime.strptime(date_only, "%Y-%m-%d").date()
                    except Exception:
                        base_dt = datetime(sel_year, sel_month, 1).date()


                    new_dt = st.date_input(
                        "날짜 선택",
                        value=base_dt,
                        key=f"edit_date_{t_id}",
                    )
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        if st.button("저장", key=f"save_date_{t_id}"):
                            old_time = (current_date.split(" ") + ["00:00:00"])[1]
                            t["date"] = f"{new_dt.strftime('%Y-%m-%d')} {old_time}"
                            all_by_id[t_id] = t
                            save_all_tasks(list(all_by_id.values()))
                            st.success("날짜 변경 완료")
                            st.rerun()
                    with btn2:
                        st.button("취소", key=f"cancel_date_{t_id}")

            # (4) 완료 토글 / 삭제
            with cols[3]:
                # 완료 토글
                is_done = t.get("status") == "done"
                toggle_label = "되돌리기" if is_done else "완료"
                if st.button(toggle_label, key=f"done_{t_id}", help="상태 토글"):
                    t["status"] = "pending" if is_done else "done"
                    all_by_id[t_id] = t
                    save_all_tasks(list(all_by_id.values()))
                    st.rerun()

                # 삭제
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
        if (
            "selected_kpi_pdf" not in st.session_state
            or st.session_state.selected_kpi_pdf not in pdf_files
        ):
            st.session_state.selected_kpi_pdf = pdf_files[0]

        selected_pdf = st.selectbox(
            "저장된 PDF",
            options=pdf_files,
            index=pdf_files.index(st.session_state.selected_kpi_pdf),
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
        # Always try to use the designated KPI file
        with st.spinner("대표 KPI 파일 파싱 중..."):
            parse_res = parse_pdf.run(filename='@designated')
        
        if parse_res.get("status") != "success":
            fb_status.error(f"대표 KPI 파일 파싱 오류: {parse_res.get('message', '파싱 실패')}")
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
            
            # Load template content if it exists
            template_content = ""
            try:
                TEMPLATE_FILE = GUIDE_DIR / "feedback_template.md"
                with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                    template_content = f.read()
                if template_content:
                    fb_status.info("저장된 템플릿을 참고하여 보고서를 생성합니다.")
            except FileNotFoundError:
                pass # Template is optional

            with st.spinner("보고서 생성 중..."):
                rep_res = generate_feedback.run(
                    month=st.session_state.selected_month,
                    todos=todos_json,
                    kpi_summary=st.session_state.kpi_summary,
                    template=template_content # Pass the template content
                )
            if rep_res.get("status") == "success":
                st.session_state.generated_report = rep_res.get("content", "")
                fb_status.success("보고서 생성 완료")
            else:
                fb_status.error(f"보고서 오류: {rep_res.get('message', '보고서 생성 실패')}")

    st.markdown("---")
    st.subheader("생성된 보고서")
    report_content = st.session_state.get("generated_report") or "*보고서가 아직 생성되지 않았습니다.*"
    with st.container(border=True):
        st.markdown(report_content)

    colA, colB, colC = st.columns(3)

    # 진행 플래그 초기화 (중복 방지)
    if "is_exporting_notion" not in st.session_state:
        st.session_state["is_exporting_notion"] = False

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

    # ✅ 단일 버튼 + 2단계 처리 (placeholder 사용/이중 렌더 제거)
    with colB:
        export_clicked = st.button(
            "Notion으로 내보내기",
            disabled=st.session_state["is_exporting_notion"],
            key="btn_export_notion",
            help="생성된 보고서를 Notion 페이지로 업로드합니다."
        )
        if export_clicked:
            if not st.session_state.get("generated_report"):
                fb_status.error("생성된 보고서 없음")
            else:
                # 1단계: 플래그만 켜고 즉시 재실행 → 다음 렌더에서 실제 업로드
                st.session_state["is_exporting_notion"] = True
                st.rerun()

    with colC:
        try:
            st.link_button("Notion 이동", "https://www.notion.so/TEST-PAGE-27809ae27c27807da3d2e6cd7e74b836")
        except Exception:
            # 구버전 호환: 일반 링크로 대체
            st.markdown(
                "[Notion 이동](https://www.notion.so/TEST-PAGE-27809ae27c27807da3d2e6cd7e74b836)",
                unsafe_allow_html=True
            )

    # 2단계: 실제 업로드 수행 구간 (버튼 밖에서, 렌더 1회에 딱 한 번만 실행)
    if st.session_state.get("is_exporting_notion"):
        with st.spinner("Notion 업로드 중..."):
            res = export_to_notion.run(
                month=st.session_state.selected_month,
                content=st.session_state.generated_report
            )

        # 업로드 종료 → 버튼 다시 활성화
        st.session_state["is_exporting_notion"] = False

        if res.get("status") == "success":
            st.toast("Notion 내보내기 완료!", icon="🎉")
            fb_status.success(f"업로드 완료: {res.get('url')}")
        else:
            fb_status.error(f"Notion 오류: {res.get('message', '업로드 실패')}")

        # 최종 상태 반영을 위해 1회 재렌더
        st.rerun()


elif st.session_state.active_tab == "템플릿 관리":
    st.header("월간 피드백 템플릿 관리")
    
    TEMPLATE_FILE = GUIDE_DIR / "feedback_template.md"
    
    # Load existing template if it exists
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template_content = f.read()
    except FileNotFoundError:
        template_content = ""

    st.markdown("""
    월간 피드백 보고서의 기본 템플릿을 작성하고 저장할 수 있습니다.
    LLM 에이전트는 여기에 저장된 템플릿의 구조와 스타일을 참고하여 보고서를 생성합니다.
    """)
    
    new_template = st.text_area(
        "템플릿 내용 (Markdown 지원)", 
        value=template_content, 
        height=500,
        key="template_content_area"
    )

    if st.button("템플릿 저장"):
        try:
            with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
                f.write(new_template)
            st.success("템플릿이 성공적으로 저장되었습니다.")
        except Exception as e:
            st.error(f"템플릿 저장 중 오류가 발생했습니다: {e}")

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

                # 교체: 반환 개수에 따라 유연 언패킹
                result = agent_step(st.session_state.llm_messages, st.session_state.llm_context)

                # 기본값
                wip_content = None

                if isinstance(result, (list, tuple)):
                    if len(result) >= 4:
                        new_llm_messages, new_context, ui_message, is_final = result[:4]
                        if len(result) >= 5:
                            wip_content = result[4]
                    else:
                        raise RuntimeError(f"agent_step 반환값 개수가 예상보다 적습니다: {len(result)}")
                else:
                    raise RuntimeError("agent_step 반환값이 tuple/list가 아닙니다.")


                # Update state for the next iteration
                st.session_state.llm_messages = new_llm_messages
                st.session_state.llm_context = new_context
                
                # Show the result of the current step
                placeholder.markdown(ui_message)
                if wip_content:
                    with st.expander("작업 상세 내용 보기", expanded=False):
                        display_content = json.dumps(wip_content, indent=2, ensure_ascii=False)
                        st.code(display_content, language='json')
            
            # Add the agent's step output to the UI history
            st.session_state.ui_messages.append({"role": "assistant", "content": ui_message})

            if is_final:
                break