"""Notionデータ一括取込"""

import os
from notion_client import Client as NotionClient
from dotenv import load_dotenv
import db
import search

load_dotenv()


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


def fetch_pages_from_notion(
    client: NotionClient, database_id: str
) -> list[dict]:
    """
    Notionデータベースのページを取得し、QAペア形式に変換する。
    ルール: ページタイトル→タイトル, 最初のテキストブロック→質問, 残り→回答（結合）
    """
    qa_list = []
    start_cursor = None

    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = client.databases.query(**kwargs)

        for page in response.get("results", []):
            page_id = page["id"]
            title = _extract_page_title(page)

            # ページ内のブロック（子要素）を取得
            blocks_resp = client.blocks.children.list(block_id=page_id)
            blocks = blocks_resp.get("results", [])

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

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

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

    client = NotionClient(auth=token)
    qa_list = fetch_pages_from_notion(client, database_id)

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
