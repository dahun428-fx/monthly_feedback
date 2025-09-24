from ..utils.gemini_helper import call_gemini

DESCRIPTION = "- summarize_text(text_to_summarize: str): 주어진 텍스트를 요약합니다."

def run(text_to_summarize: str = None):
    if not text_to_summarize:
        return {"status": "error", "message": "요약할 텍스트가 필요합니다."}

    prompt = f"""다음 텍스트를 한국어로 요약해 주세요:

    --- 텍스트 ---
    {text_to_summarize}
    --- 텍스트 끝 ---

    요약:"
    """

    gemini_result = call_gemini(prompt)

    if gemini_result.get("status") == "ok":
        summary_text = gemini_result.get("result", {}).get("text", "").strip()
        if not summary_text:
            return {"status": "success", "summary": "[요약 실패: 빈 응답]"}
        else:
            return {"status": "success", "summary": summary_text}
    else:
        return {"status": "error", "message": f"[요약 오류] {gemini_result.get('message', '')}"}