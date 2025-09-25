from ..utils.gemini_helper import call_gemini

DESCRIPTION = "- generate_feedback(month: str, todos: str, kpi_summary: str, template: str = None): 제공된 정보를 바탕으로 월간 피드백 보고서 초안을 생성합니다. 템플릿이 제공되면 해당 구조를 우선적으로 따릅니다."

def run(month: str = None, todos: str = None, kpi_summary: str = None, template: str = None):
    if not all([month, todos, kpi_summary]):
        return {"status": "error", "message": "month, todos, kpi_summary 인자가 모두 필요합니다."}

    if template and template.strip():
        # Use the user-provided template
        prompt = f"""당신은 전문적인 보고서 작성자입니다.
아래의 [사용자 지정 템플릿]을 반드시 참고하여, 주어진 정보를 바탕으로 월간 피드백 보고서를 한국어로 작성해 주세요.
템플릿의 구조, 스타일, 어조를 최대한 유지해야 합니다.

[사용자 지정 템플릿]:
---
{template}
---

[보고서에 반영할 정보]:
- 월: {month}
- 완료한 할 일: {todos}
- KPI 요약: {kpi_summary}

위 정보를 바탕으로 [사용자 지정 템플릿]에 맞춰 보고서를 생성해 주세요.
"""
    else:
        # Use the default prompt if no template is provided
        prompt = f"""당신은 전문적인 보고서 작성자입니다.
아래의 {month}월 정보를 바탕으로 월간 피드백 보고서를 한국어로 작성해 주세요.
보고서는 반드시 마크다운 형식이어야 하며, 단순히 목록을 나열하는 것이 아니라 자연스러운 문장으로 서술해야 합니다.

**1. 완료한 할 일 목록:**
```json
{todos}
```

**2. KPI 요약:**
```text
{kpi_summary}
```

**보고서 구조:**
보고서에는 반드시 아래의 네 가지 항목이 포함되어야 합니다. 주어진 데이터를 바탕으로 각 항목을 상세히 서술해 주세요.

- ## 성과 (Highlights)
  - (완료된 할 일 목록과 KPI 요약의 긍정적인 내용을 분석하여 달성한 성과를 서술합니다.)

- ## 주요 활동 (Key Activities)
  - (할 일 목록을 바탕으로 해당 월에 수행한 주요 활동과 업무들을 서술합니다.)

- ## 개선점 (Areas for Improvement)
  - (완료하지 못한 할 일이나 KPI 요약에서 언급된 개선 필요 사항을 식별하여 서술합니다.)

- ## 다음 달 계획 (Next Month's Plan)
  - (개선점과 진행 중인 업무를 바탕으로 다음 달의 계획을 제안합니다.)
"""

    gemini_result = call_gemini(prompt)

    if gemini_result.get("status") == "ok":
        raw_text = gemini_result.get("result", {}).get("text", "").strip()
        if not raw_text:
            raw_text = "[생성 실패: 빈 응답]"
    else:
        raw_text = f"[생성 오류] {gemini_result.get('message', '')}"

    return {
        "status": "success",
        "month": month,
        "content": raw_text
    }