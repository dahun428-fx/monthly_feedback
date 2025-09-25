import os
import json
from typing import Any, Dict, List, Tuple
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from .executor import execute_plan
from mcp_server.tools import DESCRIPTIONS

# === Gemini 모델 설정 ===
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    "gemini-2.0-flash",
    generation_config={
        "response_mime_type": "application/json",
        "temperature": 0.2,
        "top_p": 0.9,
        "max_output_tokens": 8192,
    },
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
)

# 각 도구가 컨텍스트에서 어떤 인자가 필요한지 정의
TOOL_CONTEXT_MAP: Dict[str, List[str]] = {
    "summarize_text": ["text_to_summarize"],
    "generate_feedback": ["month", "todos", "kpi_summary"],
    "export_to_notion": ["month", "content"],
    "export_report": ["month", "content"],
    # get_today / list_todos / parse_pdf 등은 인자 불필요 또는 실행 결과로 연결
}

# 1) 프롬프트 템플릿에서 DESCRIPTIONS 자리만 토큰으로 남깁니다.
SYSTEM_PROMPT_CORE = """당신은 도구를 호출하여 사용자를 돕는 AI 에이전트입니다. 목표는 사용자의 요청을 해결하기 위해
한 번에 '정확히 하나'의 도구만 호출하거나(final_answer) 다음 단계 결론을 반환하는 것입니다.

사용 가능한 도구 목록:
{DESCRIPTIONS}

[시나리오 예시: 월간 보고서 + Notion]
1) get_today → 2) list_todos → 3) get_pdf_filename → 4) parse_pdf → 5) summarize_text → 6) generate_feedback → 7) export_to_notion
항상 '한 단계씩만' 진행하세요.

[응답 규칙]
- 항상 JSON으로만 응답.
- 월간 보고서 작업 시 list_todos 툴을 사용 할때는, get_today 툴로부터 받은 date 중 동일한 month 에 해당하는 todo 목록을 조회하세요.
- 다음 중 하나의 최상위 키를 포함:
  - tool_code: {"tool": string, "args": object}
  - final_answer: string
- 하나의 작업이 `final_answer`로 완료되면, 그 작업은 끝난 것입니다. 다음 사용자 메시지는 이전 대화와 관련 없는 **새로운 요청**으로 간주해야 합니다. (단, 사용자가 이전 결과에 대해 직접 질문하는 경우는 예외입니다.)
- 할 일 목록(todos)을 사용자에게 보여줄 때는, 각 항목을 글머리 기호(-)를 사용하여 날짜, 할 일, 상태 순서로 보기 좋게 정리해서 보여주세요.
- 도구 호출 실패 피드백을 받으면, 원인 해결을 위한 '다음 단일 도구'를 제안하세요.
- 존재하지 않는 도구는 절대 만들지 마세요.
"""

def get_system_prompt(command: str = "") -> str:
    # 2) .format() 대신 정확히 이 토큰만 치환
    core = SYSTEM_PROMPT_CORE.replace("{DESCRIPTIONS}", DESCRIPTIONS)
    return f"{core}\n사용자 명령어: {command}\n"

def _merge_tool_result_into_context(context: Dict[str, Any], result_data: Dict[str, Any]) -> None:
    """
    제네릭 머지: 결과로 들어온 키를 컨텍스트에 안전하게 반영.
    - 타입을 변형하지 않음(문자열화 금지)
    - 파생 필드(month 등) 계산
    """
    # 원본 키들 그대로 반영
    for k, v in result_data.items():
        context[k] = v

    # 파생: today → month
    if "today" in result_data and isinstance(result_data["today"], str) and len(result_data["today"]) >= 7:
        context["month"] = result_data["today"][:7]

    # 파생: parse_pdf → summarize_text 입력 준비
    if "text" in result_data and isinstance(result_data["text"], str):
        context["text_to_summarize"] = result_data["text"]

    # 파생: summarize_text → generate_feedback 입력 준비
    if "summary" in result_data and isinstance(result_data["summary"], str):
        context["kpi_summary"] = result_data["summary"]

    # 파생: generate_feedback → export 계열 입력 준비
    if "content" in result_data and isinstance(result_data["content"], str):
        context["content"] = result_data["content"]

def _inject_args_from_context(tool: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    if tool in TOOL_CONTEXT_MAP:
        for name in TOOL_CONTEXT_MAP[tool]:
            if name in context and name not in args:
                args[name] = context[name]
    return args

def _as_user_feedback(tool: str, ok: bool, payload: Dict[str, Any]) -> str:
    if ok:
        # 요약 헤더 + 축약 JSON(길면 잘라서)
        short = json.dumps(payload, ensure_ascii=False)
        if len(short) > 2000:  # 토큰 절약
            short = short[:2000] + "…(truncated)"
        return f"Tool {tool} executed successfully.\nResult JSON:\n{short}"
    else:
        message = payload.get("message", "Unknown error")
        return f"Tool {tool} failed.\nReason: {message}\nHint: Provide missing args or call a preparatory tool."

def agent_step(messages: List[Dict[str, Any]], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str, bool, Dict[str, Any] | None]:
    """
    에이전트의 단일 스텝.
    """
    wip_content = None
    try:
        response = model.generate_content(messages)
        text = getattr(response, "text", "") or ""
    except Exception as e:
        ui_message = f"모델 호출 중 오류: {e}"
        return messages, context, ui_message, True, None

    # JSON 파싱
    try:
        llm_response = json.loads(text)
        print(f"💡 LLM says: {json.dumps(llm_response, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"❌ JSON decode error: {e}\nRaw: {text}")
        llm_response = {"final_answer": "죄송합니다. 응답 형식 오류가 발생했습니다."}

    # tool_code 경로
    if "tool_code" in llm_response:
        tool_call = llm_response["tool_code"]
        if isinstance(tool_call, str):
            tool_call = {"tool": tool_call, "args": {}}

        tool_name = tool_call.get("tool")
        tool_args = tool_call.get("args", {}) or {}

        # 컨텍스트에서 필요한 인자 주입
        tool_args = _inject_args_from_context(tool_name, tool_args, context)
        tool_call["args"] = tool_args

        # 히스토리에 '모델 의도' 기록
        messages.append({"role": "model", "parts": [{"text": json.dumps({"tool_code": tool_call}, ensure_ascii=False)}]})

        # 실제 도구 실행
        execution_result = execute_plan(tool_call)
        status_ok = (execution_result.get("status") == "200")
        result_payload = execution_result.get("result", {}) if isinstance(execution_result, dict) else {}

        # 컨텍스트 병합(성공 시)
        if status_ok and isinstance(result_payload, dict) and result_payload.get("status") != "error":
            _merge_tool_result_into_context(context, result_payload)
            feedback = _as_user_feedback(tool_name, True, result_payload)
            wip_content = result_payload
        else:
            # 실패 케이스
            err_payload = result_payload if isinstance(result_payload, dict) else {"message": execution_result}
            feedback = _as_user_feedback(tool_name, False, err_payload)

        # LLM에게 결과 전달
        messages.append({"role": "user", "parts": [{"text": feedback}]})
        return messages, context, f"🛠️ {tool_name} 실행", False, wip_content

    # final_answer 경로
    if "final_answer" in llm_response:
        return messages, context, llm_response["final_answer"], True, None

    # 결정 실패
    return messages, context, "에이전트가 다음 단계를 결정하지 못했습니다. 루프를 종료합니다.", True, None

def run_agent(command: str, *, max_steps: int = 20) -> None:
    """
    에이전트를 실행하여 최종 답변에 도달할 때까지 반복.
    """
    print(f"🚀 Starting agent with command: {command}")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "parts": [{"text": get_system_prompt(command)}]},
        {"role": "user", "parts": [{"text": command}]},
    ]
    context: Dict[str, Any] = {}

    last_tool: str | None = None
    same_tool_count = 0

    for step in range(1, max_steps + 1):
        print(f"\n🤔 Step {step}…")
        messages, context, ui_message, is_final, wip_content = agent_step(messages, context)
        print(f"✅ Agent step result: {ui_message}")
        if wip_content:
            print(f"  - Work In Progress: {json.dumps(wip_content, indent=2, ensure_ascii=False)}")


        # 단순한 무한 반복 방지: 같은 도구 연속 호출 감지 (선택)
        if len(messages) >= 2 and messages[-2]["role"] == "model":
            try:
                last_intent = json.loads(messages[-2]["parts"][0]["text"])
                cur_tool = last_intent.get("tool_code", {}).get("tool")
                if cur_tool and cur_tool == last_tool:
                    same_tool_count += 1
                else:
                    same_tool_count = 0
                last_tool = cur_tool
                if same_tool_count >= 3:
                    print("⚠️ 동일 도구를 반복 호출하여 루프를 종료합니다.")
                    break
            except Exception:
                pass

        if is_final:
            print(f"\n🏁 Final Answer: {ui_message}")
            return

    print("\n⏹️ 최대 스텝에 도달하여 종료했습니다.")
