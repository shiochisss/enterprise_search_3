"""Notionデータ一括取込"""

import os
import requests
from dotenv import load_dotenv
import db
import search

load_dotenv()

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _extract_text_from_block(block: dict) -> str:
    """Notionブロックからテキストを抽出"""
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    rich_texts = block_data.get("rich_text", [])
    return "".join(rt.get("plain_text", "") for rt in rich_texts)


def _extract_page_title(page: dict) -> str:
    """ページのタイトルプロパティを抽出"""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(t.get("plain_text", "") for t in title_parts)
    return "無題"


def fetch_pages_from_notion(token: str, database_id: str) -> list[dict]:
    """
    Notionデータベースのページを取得し、QAペア形式に変換する。
    ルール: ページタイトル→タイトル, 最初のテキストブロック→質問, 残り→回答（結合）
    """
    qa_list = []
    start_cursor = None
    hdrs = _headers(token)

    while True:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=hdrs,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        for page in data.get("results", []):
            page_id = page["id"]
            title = _extract_page_title(page)

            # ページ内のブロック（子要素）を取得
            blocks_resp = requests.get(
                f"{NOTION_API_BASE}/blocks/{page_id}/children?page_size=100",
                headers=hdrs,
            )
            blocks_resp.raise_for_status()
            blocks = blocks_resp.json().get("results", [])

            texts = [
                _extract_text_from_block(b)
                for b in blocks
                if _extract_text_from_block(b).strip()
            ]

            if not texts:
                continue

            question = texts[0]
            answer = "\n".join(texts[1:]) if len(texts) > 1 else texts[0]

            qa_list.append(
                {
                    "title": title,
                    "question": question,
                    "answer": answer,
                    "source_id": page_id,
                }
            )

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return qa_list


def run_import() -> dict:
    """
    Notionからデータを取得し、embedding生成後にSupabaseへupsert。
    返り値: {"total": 取得件数, "upserted": 登録件数}
    """
    token = os.environ.get("NOTION_API_KEY", "")
    database_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not token or not database_id:
        return {"error": "NOTION_API_KEY または NOTION_DATABASE_ID が未設定です。"}

    try:
        qa_list = fetch_pages_from_notion(token, database_id)
    except Exception as e:
        return {"error": f"Notion APIエラー: {e}"}

    upserted = 0
    for qa in qa_list:
        embedding = search.get_embedding(qa["question"])
        db.upsert_qa_by_source_id(
            source="notion",
            source_id=qa["source_id"],
            title=qa["title"],
            question=qa["question"],
            answer=qa["answer"],
            embedding=embedding,
        )
        upserted += 1

    return {"total": len(qa_list), "upserted": upserted}
