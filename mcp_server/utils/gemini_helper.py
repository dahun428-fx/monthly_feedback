import re
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일로부터 환경 변수 로드
load_dotenv()

# API 키 설정
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set in the environment.")
genai.configure(api_key=API_KEY)

# 모델 초기화
model = genai.GenerativeModel("gemini-2.0-flash")
def call_gemini(prompt: str):
    try:
        response = model.generate_content(prompt)
        raw = (response.text or "").strip()
        return {"status": "ok", "result": {"text": raw}}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "result": {"text": ""}
        }
