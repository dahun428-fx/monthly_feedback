#계획(plan)을 읽고 MCP 서버 툴을 실제 실행
import requests
MCP_SERVER_URL = "http://localhost:8000"

def execute_plan(plan: dict):
    tool = plan.get("tool")
    args = plan.get("args", {})

    url = f"{MCP_SERVER_URL}/tools/{tool}"
    resp = requests.post(url, json={"args": args})

    if resp.status_code == 200:
        return {"status": "200", "result" : resp.json()}
    else:
        return {"status": "error", "message": resp.text}
