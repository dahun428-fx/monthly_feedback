from pydantic import BaseModel

class ToolRequest(BaseModel):
    args: dict
