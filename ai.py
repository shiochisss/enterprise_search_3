"""RAG回答生成（OpenAI gpt-4o-mini / gpt-5-nano）"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

ALLOWED_MODELS = ["gpt-4o-mini", "gpt-5-nano"]
DEFAULT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "あなたは社内ナレッジベースのアシスタントです。"
    "以下の参考情報をもとに、ユーザーの質問に丁寧に回答してください。"
    "参考情報に該当するものがない場合は、正直にその旨を伝えてください。"
    "回答はできるだけ具体的に、データの出典も含めて説明してください。"
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _build_messages(question: str, similar_qas: list[dict]) -> list[dict]:
    """システムプロンプト＋参考QA＋ユーザー質問のメッセージを組み立てる"""
    context_parts = []
    for i, qa in enumerate(similar_qas[:3], 1):
        source = qa.get("source", "不明")
        score = qa.get("score", 0)
        context_parts.append(
            f"【参考{i}】(出典: {source}, 類似度: {score:.2f})\n"
            f"タイトル: {qa.get('title', '')}\n"
            f"質問: {qa.get('question', '')}\n"
            f"回答: {qa.get('answer', '')}"
        )

    context_text = "\n\n".join(context_parts) if context_parts else "参考情報はありません。"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"参考情報:\n{context_text}\n\n質問: {question}"},
    ]


def generate_answer(
    question: str, similar_qas: list[dict], model: str = DEFAULT_MODEL
) -> str:
    """非ストリーミングでRAG回答を生成"""
    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL

    messages = _build_messages(question, similar_qas)
    response = _get_client().chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content


def generate_answer_stream(
    question: str, similar_qas: list[dict], model: str = DEFAULT_MODEL
):
    """ストリーミングでRAG回答を生成（ジェネレータ）"""
    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL

    messages = _build_messages(question, similar_qas)
    stream = _get_client().chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
