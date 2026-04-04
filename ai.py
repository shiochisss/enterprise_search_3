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


def clean_qa_text(title: str, question: str, answer: str) -> dict:
    """
    取込データのテキストをAIで整形する。
    口語・略語・ノイズを除去し、検索しやすい明確な文章に変換。
    返り値: {"title": str, "question": str, "answer": str}
    """
    # 文字数制限（トークン爆発防止のため8,000文字程度で制限）
    safe_answer = answer[:8000] if answer else ""
    
    prompt = (
        "以下のQ&Aデータを、検索エンジンで見つけやすいように整形してください。\n"
        "・口語表現を丁寧語に変換\n"
        "・略語があれば正式名称を補足\n"
        "・不要なノイズ（挨拶、絵文字、相槌など）を除去\n"
        "・内容や意味は変えない\n"
        "・以下のフォーマットで出力（各セクションの内容のみ、ラベル不要）\n\n"
        "---タイトル---\n（簡潔なタイトル）\n"
        "---質問---\n（整形された質問）\n"
        "---回答---\n（整形された回答）\n\n"
        f"元データ:\nタイトル: {title}\n質問: {question}\n回答: {safe_answer}"
    )
    response = _get_client().chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content

    parts = {"title": title, "question": question, "answer": answer}
    try:
        if "---タイトル---" in text and "---質問---" in text and "---回答---" in text:
            parts["title"] = text.split("---タイトル---")[1].split("---質問---")[0].strip()
            parts["question"] = text.split("---質問---")[1].split("---回答---")[0].strip()
            parts["answer"] = text.split("---回答---")[1].strip()
    except (IndexError, ValueError):
        pass
    return parts


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
