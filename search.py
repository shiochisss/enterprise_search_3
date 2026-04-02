"""ベクトル検索ロジック（OpenAI embedding + pgvector）"""

import os
from openai import OpenAI
from dotenv import load_dotenv
import db

load_dotenv()

_openai_client: OpenAI | None = None

EMBEDDING_MODEL = "text-embedding-3-small"


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai_client


def get_embedding(text: str) -> list[float]:
    """テキストをembeddingベクトル（1536次元）に変換"""
    response = _get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def find_similar(question: str, top_k: int = 10) -> list[dict]:
    """
    クエリに類似するQAペアをpgvectorで検索し、類似度順に返す。
    各要素: {id, title, question, answer, source, score}
    """
    embedding = get_embedding(question)
    result = db.get_client().rpc(
        "match_qa",
        {"query_embedding": embedding, "match_count": top_k},
    ).execute()
    return result.data
