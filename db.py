"""Supabaseクライアント＋全CRUD操作"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Supabaseクライアントのシングルトンを返す"""
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"],
        )
    return _client


# ──────────────────────────────────────
# QA ペア CRUD
# ──────────────────────────────────────

def insert_qa(
    title: str,
    question: str,
    answer: str,
    source: str,
    embedding: list[float],
    created_by: str,
    source_id: str = "",
) -> dict:
    """QAペアを新規登録"""
    data = {
        "title": title,
        "question": question,
        "answer": answer,
        "source": source,
        "source_id": source_id,
        "embedding": embedding,
        "created_by": created_by,
        "updated_by": created_by,
    }
    return get_client().table("qa_pairs").insert(data).execute().data


def fetch_all_qa() -> list[dict]:
    """全QAペアを取得（新しい順）"""
    return (
        get_client()
        .table("qa_pairs")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def update_qa(
    qa_id: int,
    title: str,
    question: str,
    answer: str,
    embedding: list[float],
    updated_by: str,
) -> None:
    """QAペアを更新"""
    get_client().table("qa_pairs").update(
        {
            "title": title,
            "question": question,
            "answer": answer,
            "embedding": embedding,
            "updated_by": updated_by,
        }
    ).eq("id", qa_id).execute()


def delete_qa(qa_id: int) -> None:
    """QAペアを削除"""
    get_client().table("qa_pairs").delete().eq("id", qa_id).execute()


def upsert_qa_by_source_id(
    source: str,
    source_id: str,
    title: str,
    question: str,
    answer: str,
    embedding: list[float],
) -> None:
    """source + source_id で重複チェックし upsert"""
    existing = (
        get_client()
        .table("qa_pairs")
        .select("id")
        .eq("source", source)
        .eq("source_id", source_id)
        .execute()
        .data
    )
    if existing:
        get_client().table("qa_pairs").update(
            {
                "title": title,
                "question": question,
                "answer": answer,
                "embedding": embedding,
                "updated_by": source,
            }
        ).eq("id", existing[0]["id"]).execute()
    else:
        insert_qa(title, question, answer, source, embedding, source)


# ──────────────────────────────────────
# 回答募集中の質問
# ──────────────────────────────────────

def insert_pending_question(question: str, asked_by: str) -> None:
    """回答募集中の質問を登録"""
    get_client().table("pending_questions").insert(
        {"question": question, "asked_by": asked_by}
    ).execute()


def fetch_pending_questions() -> list[dict]:
    """未解決の質問一覧を取得"""
    return (
        get_client()
        .table("pending_questions")
        .select("*")
        .eq("resolved", False)
        .order("created_at", desc=True)
        .execute()
        .data
    )


def fetch_all_pending_questions() -> list[dict]:
    """全質問一覧を取得（解決済み含む）"""
    return (
        get_client()
        .table("pending_questions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def resolve_pending_question(
    pending_id: int, answer: str, resolved_by: str
) -> None:
    """質問を解決済みにする"""
    get_client().table("pending_questions").update(
        {"answer": answer, "resolved": True, "resolved_by": resolved_by}
    ).eq("id", pending_id).execute()


def rate_pending_question(pending_id: int, rating: int) -> None:
    """回答募集質問の満足度を評価"""
    get_client().table("pending_questions").update(
        {"satisfaction_rating": rating}
    ).eq("id", pending_id).execute()


def delete_pending_question(pending_id: int) -> None:
    """質問を削除"""
    get_client().table("pending_questions").delete().eq("id", pending_id).execute()


# ──────────────────────────────────────
# 検索履歴
# ──────────────────────────────────────

def insert_search_history(
    query: str, results: list[dict], searched_by: str
) -> int:
    """検索履歴を保存し、IDを返す"""
    row: dict = {
        "query": query,
        "searched_by": searched_by,
    }
    for i, r in enumerate(results[:3], 1):
        row[f"result{i}_qa_id"] = r.get("id")
        row[f"result{i}_title"] = r.get("title", "")
        row[f"result{i}_score"] = r.get("score", 0)

    data = get_client().table("search_history").insert(row).execute().data
    return data[0]["id"]


def rate_search(search_id: int, rating: int) -> None:
    """検索結果の満足度を評価"""
    get_client().table("search_history").update(
        {"satisfaction_rating": rating}
    ).eq("id", search_id).execute()


def fetch_search_history(limit: int = 100) -> list[dict]:
    """検索履歴を取得"""
    return (
        get_client()
        .table("search_history")
        .select("*")
        .order("searched_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
