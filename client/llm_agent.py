import os
import re
import json
import google.generativeai as genai
from .executor import execute_plan
from mcp_server.tools import DESCRIPTIONS

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"},
)

# 각 도구가 컨텍스트에서 어떤 인자를 필요로 하는지 명시하는 맵
TOOL_CONTEXT_MAP = {
    "summarize_text": ["text_to_summarize"],
    "generate_feedback": ["month", "todos", "kpi_summary"],
    "export_to_notion": ["month", "content"],
    "export_report": ["month", "content"],
}

def run_agent(command: str):
    """
    Runs the agent loop to process a command, using tools until a final answer is reached.
    """
    print(f"🚀 Starting agent with command: {command}")

    messages = [
        {
            "role": "user",
            "parts": [
                {
                    "text": f"""당신은 도구를 호출하여 사용자를 돕는 AI 에이전트입니다. 당신의 목표는 사용자의 요청에 가장 적절한 단 하나의 도구를 호출하여 응답하는 것입니다.

사용 가능한 도구 목록:
{DESCRIPTIONS}

# 주요 작업 시나리오
- **월간 보고서 생성 및 Notion 내보내기**: 이 요청을 받으면, 반드시 아래 순서대로 도구를 호출해야 합니다.
  1. `get_today` (오늘 날짜 확인)
  2. `list_todos` (할 일 목록 가져오기)
  3. `list_pdf_files` (PDF 파일 목록 확인)
  4. `parse_pdf` (PDF 내용 추출)
  5. `summarize_text` (추출된 내용 요약)
  6. `generate_feedback` (모든 정보를 종합하여 보고서 내용 생성)
  7. `export_to_notion` (생성된 보고서 내용을 Notion으로 내보내기)

# 규칙
- 반드시 JSON 형식으로 응답해야 합니다.
- 응답은 단일 도구 호출을 위한 'tool_code' 필드 또는 최종 답변을 위한 'final_answer' 필드를 포함해야 합니다.
- **중요**: 여러 단계를 미리 계획하지 마세요. 시나리오나 사용자의 마지막 메시지를 해결하기 위한 다음 단계만 생각하고, 가장 직접적으로 도움이 되는 도구 하나만 선택하세요.
- **오류 처리**: 도구 호출이 실패했다는 메시지를 받으면, 그 원인을 해결하기 위한 다음 단계를 생각하세요. 예를 들어, 인자가 부족해서 실패했다면, 그 인자를 얻을 수 있는 다른 도구를 호출해야 합니다.
- 없는 도구를 만들지 말고, 주어진 도구만 사용해야 합니다.

사용자 명령어: {command}
"""
                }
            ],
        }
    ]
    
    context = {}

    while True:
        print("\n🤔 Thinking...")
        response = model.generate_content(messages)
        
        try:
            llm_response = json.loads(response.text)
            print(f"💡 LLM says: {json.dumps(llm_response, indent=2, ensure_ascii=False)}")
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"❌ Error decoding LLM response: {e}")
            print(f"Raw response: {response.text}")
            llm_response = {"final_answer": "죄송합니다, 응답을 처리하는 중 오류가 발생했습니다."}

        if "tool_code" in llm_response:
            tool_call = llm_response["tool_code"]
            
            if isinstance(tool_call, str):
                tool_call = {"tool": tool_call, "args": {}}

            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("args", {})

            # 🧠 도구에 필요한 인자만 컨텍스트에서 선별적으로 주입 (컨텍스트 값을 우선)
            if tool_name in TOOL_CONTEXT_MAP:
                for arg_name in TOOL_CONTEXT_MAP[tool_name]:
                    if arg_name in context:
                        tool_args[arg_name] = context[arg_name]
            tool_call["args"] = tool_args

            messages.append({"role": "model", "parts": [{"text": json.dumps({"tool_code": tool_call})}]})

            print(f"🛠️  Executing tool: {tool_name} with args: {tool_args}")
            execution_result = execute_plan(tool_call)
            print(f"✅ Tool result: {json.dumps(execution_result, indent=2, ensure_ascii=False)}")

            # 🧠 실행 결과 처리 및 LLM에게 전달할 메시지 생성
            user_feedback_message = f"Tool {tool_name} executed. Result is stored in context."
            if execution_result.get("status") == "200":
                result_data = execution_result.get("result", {})
                if result_data.get("status") != "error":
                    if "today" in result_data: 
                        context["month"] = result_data["today"][:7]
                        user_feedback_message = f"Tool {tool_name} executed. Result: {json.dumps(result_data)}"
                    if "todos" in result_data: context["todos"] = json.dumps(result_data["todos"], ensure_ascii=False)
                    if "text" in result_data: context["text_to_summarize"] = result_data["text"]
                    if "summary" in result_data: context["kpi_summary"] = result_data["summary"]
                    if "content" in result_data: context["content"] = result_data["content"]
                else:
                    user_feedback_message = f"Tool {tool_name} failed. Error: {result_data.get('message')}"

            messages.append({
                "role": "user",
                "parts": [{ "text": user_feedback_message }]
            })

        elif "final_answer" in llm_response:
            final_answer = llm_response["final_answer"]
            print(f"\n🏁 Final Answer: {final_answer}")
            break
        
        else:
            print("❌ LLM response did not contain 'tool_code' or 'final_answer'.")
            print("Ending agent loop.")
            break