from fastapi import FastAPI
from .schemas import ToolRequest
from .tools import TOOLS

app = FastAPI()

@app.post("/tools/{tool_name}")
def run_tool(tool_name: str, req: ToolRequest):
    if tool_name not in TOOLS:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    # args 딕셔너리를 툴 run 함수에 언팩 전달
    try:
        result = TOOLS[tool_name](**req.args)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
