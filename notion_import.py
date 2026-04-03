"""Notionデータ一括取込（全件版：本文ベクトル化 & 究極お掃除 & AI命名）"""

import os
import re
import json
import http.client
from dotenv import load_dotenv

# プロジェクト共通モジュールのインポート
import db
import search
import ai

load_dotenv()

def _basic_clean(text: str) -> str:
    """プログラムによる高速なゴミ掃除（テンプレート由来の定型文を除去）"""
    cleaned = text
    patterns = [
        r"(?:例）)?.*?[〇○]{2,}.*?取り組んでいる中で.*?共有します！",
        r"(?:例）)?.*?[〇○]{2,}.*?役に立ちそうな情報をまとめたので共有します！",
        r"追加もウェルカムです！",
        r"←参考になったと思ったら.*?お願いします",
        r"内容\s*Slackの情報は３ヶ月で消えてしまうため.*?お願いします！",
        r"関連ワード.*?使用しない場合は空白にする。",
        r"上に[「\(].*?[」\)]の入力を\s*お願いします！",
        r"[「\(]アイコン[」\)].*?自由です！",
        r"[「\(]要素[」\)].*?します！",
        r"[「\(]内容[」\)].*?自由です！\s*\)?",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.DOTALL)
    
    for kw in ["内容はここから", "記入方法", "要約", "内容", "要素"]:
        cleaned = cleaned.replace(kw, "")
        
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned) 
    return cleaned.strip()

def call_notion_api(method: str, path: str, body: dict = None):
    """Notion APIへの低レベルリクエスト"""
    token = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
    conn = http.client.HTTPSConnection("api.notion.com")
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28'
    }
    payload = json.dumps(body) if body else None
    conn.request(method, path, body=payload, headers=headers)
    res = conn.getresponse()
    return json.loads(res.read().decode("utf-8"))

def _get_all_content_recursive(block_id: str, depth=0) -> str:
    """再帰的にすべての子ブロックからテキストを抽出（深さ5まで）"""
    if depth > 5: return ""
    content = ""
    try:
        data = call_notion_api("GET", f"/v1/blocks/{block_id}/children")
        for block in data.get("results", []):
            b_type = block.get("type")
            if b_type in block:
                block_data = block[b_type]
                if isinstance(block_data, dict) and "rich_text" in block_data:
                    text = "".join([t.get("plain_text", "") for t in block_data["rich_text"]])
                    if text: content += text + "\n"
            if block.get("has_children"):
                content += _get_all_content_recursive(block["id"], depth + 1)
        return content
    except: return ""

def fetch_pages_from_notion(database_id: str) -> list[dict]:
    """データベースから全ページを取得し、初期お掃除まで行う"""
    qa_list = []
    start_cursor = None
    # 無効なタイトルを判定するパターン
    invalid_title_pattern = re.compile(r"^(タイトルを入力|無題|無題のページ|Untitled|記入方法|要約|内容|上に.*入力を.*)$", re.IGNORECASE)

    print("🔍 Fetching pages from Notion...")
    while True:
        body = {"page_size": 100}
        if start_cursor: body["start_cursor"] = start_cursor
        result = call_notion_api("POST", f"/v1/databases/{database_id}/query", body)
        pages = result.get("results", [])
        if not pages: break

        for page in pages:
            page_id = page["id"]
            title = ""
            props = page.get("properties", {})
            # タイトル項目の抽出
            for cand in ["タイトル", "Name", "件名", "名前"]:
                if cand in props and props[cand].get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in props[cand].get("title", [])).strip()
                    break
            
            # 本文の全取得と簡易お掃除
            full_text = _get_all_content_recursive(page_id)
            cleaned_text = _basic_clean(full_text)

            # 短すぎるものはスキップ
            if len(cleaned_text) < 20: continue

            # AIによるディープクリーニングが必要か判定
            is_invalid_title = not title or invalid_title_pattern.match(title)
            has_trash_remnants = any(w in cleaned_text[:100] for w in ["上に", "タグ", "作成者", "共有します"])

            # 共通AI関数を使用して整形
            # タイトルが空、またはゴミが残っている場合はAIに整形を依頼
            if is_invalid_title or has_trash_remnants:
                print(f"✨ Deep Cleaning with AI: {title or 'Untitled'}...")
                # 共通関数の clean_qa_text を使用
                # questionはtitleを補う形でAIに考えさせる
                cleaned_data = ai.clean_qa_text(title or "名称未設定", title or "内容の要約", cleaned_text)
                
                title = cleaned_data["title"]
                question = cleaned_data["question"]
                answer = cleaned_data["answer"]

                if title == "EMPTY" or len(answer) < 40:
                    print(f"   -> Skipped (Low quality).")
                    continue
            else:
                # すでに綺麗なデータはそのまま利用（質問項目はタイトルを流用）
                question = title
                answer = cleaned_text

            qa_list.append({
                "title": title,
                "question": question,
                "answer": answer,
                "source_id": page_id
            })
            print(f"Parsed: {title}")


        if not result.get("has_more"): break
        start_cursor = result.get("next_cursor")
    
    return qa_list

def run_import() -> dict:
    """インポート実行メインルーチン"""
    database_id = os.environ.get("NOTION_DATABASE_ID") or os.environ.get("DATABASE_ID")
    if not database_id: return {"error": "DATABASE_ID が未設定です。"}

    # 1. Notionから全件取得（内部でAIお掃除実行）
    qa_list = fetch_pages_from_notion(database_id)

    # 2. データベースへ保存
    upserted = 0
    total = len(qa_list)
    print(f"📦 Importing {total} items to DB with Body Embedding...")
    
    for i, qa in enumerate(qa_list):
        # 共通関数の get_qa_embedding を使用してベクトル化
        embedding = search.get_qa_embedding(qa["title"], qa["question"], qa["answer"])
        
        db.upsert_qa_by_source_id(
            source="notion",
            source_id=qa["source_id"],
            title=qa["title"],
            question=qa["question"],
            answer=qa["answer"],
            embedding=embedding
        )
        
        upserted += 1
        if (i+1) % 5 == 0 or (i+1) == total:
            print(f"Progress: {i+1}/{total} ({qa['title'][:20]}...)")

    return {"total": total, "upserted": upserted}

if __name__ == "__main__":
    res = run_import()
    print(res)