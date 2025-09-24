import os
import re
from dotenv import load_dotenv
import notion_client

DESCRIPTION = "- export_to_notion(month: str, content: str): 생성된 보고서 내용을 Notion 페이지로 생성합니다."

# .env 파일 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_BLOCK_CHAR_LIMIT = 2000 # Notion API의 블록 당 글자 수 제한

def markdown_to_blocks(markdown_content: str):
    """마크다운 텍스트를 Notion 블록 리스트로 변환합니다. 긴 텍스트는 자동으로 나눕니다."""
    blocks = []
    lines = markdown_content.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 글자 수 제한 체크 및 분할 처리 (헤딩이나 리스트가 아닌 일반 텍스트에만 적용)
        if len(line) > NOTION_BLOCK_CHAR_LIMIT and not line.startswith(('#', '- ')):
            for i in range(0, len(line), NOTION_BLOCK_CHAR_LIMIT):
                chunk = line[i:i + NOTION_BLOCK_CHAR_LIMIT]
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
                })
            continue

        # 마크다운 요소에 따라 블록 타입 결정 (순서가 중요: ### -> ## -> #)
        if line.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}}
            )
        elif line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}}
            )
        elif line.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}}
            )
        elif line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}}
            )
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]}}
            )
    return blocks

def run(month: str = None, content: str = None):
    if not all([month, content]):
        return {"status": "error", "message": "month와 content 인자가 모두 필요합니다."}

    if not NOTION_API_KEY or not NOTION_PAGE_ID:
        return {"status": "error", "message": ".env 파일에 NOTION_API_KEY와 NOTION_PAGE_ID를 설정해야 합니다."}

    try:
        notion = notion_client.Client(auth=NOTION_API_KEY)
        
        page_title = f"{month} 월간 피드백 보고서"
        notion_blocks = markdown_to_blocks(content)

        new_page = notion.pages.create(
            parent={"page_id": NOTION_PAGE_ID},
            properties={
                "title": {
                    "title": [
                        {
                            "text": {"content": page_title}
                        }
                    ]
                }
            },
            children=notion_blocks
        )
        page_url = new_page.get("url")
        print(f"[export_to_notion] Notion 페이지 생성 완료: {page_url}")
        return {"status": "success", "url": page_url}

    except Exception as e:
        print(f"[export_to_notion] 오류 발생: {e}")
        return {"status": "error", "message": f"Notion 페이지 생성 중 오류 발생: {e}"}
