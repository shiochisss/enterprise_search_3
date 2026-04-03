"""Slackデータ一括取込"""

import os
from slack_sdk import WebClient
from dotenv import load_dotenv
import db
import search
import ai

load_dotenv()


def fetch_qa_from_slack(
    client: WebClient, channel_id: str
) -> list[dict]:
    """
    Slackチャンネルのスレッドを取得し、QAペア形式に変換する。
    ルール: 親メッセージ→タイトル, 1番目のリプライ→質問, 2番目以降→回答（結合）
    reply_count >= 2 のスレッドのみ対象。
    """
    qa_list = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "limit": 100}
        if cursor:
            kwargs["cursor"] = cursor

        response = client.conversations_history(**kwargs)
        messages = response.get("messages", [])

        for msg in messages:
            if msg.get("reply_count", 0) < 2:
                continue

            thread_ts = msg["ts"]
            replies_resp = client.conversations_replies(
                channel=channel_id, ts=thread_ts, limit=200
            )
            replies = replies_resp.get("messages", [])
            if len(replies) < 3:  # 親 + 2リプライ以上
                continue

            title = replies[0].get("text", "")[:100]
            question = replies[1].get("text", "")
            answer = "\n".join(r.get("text", "") for r in replies[2:])

            qa_list.append(
                {
                    "title": title,
                    "question": question,
                    "answer": answer,
                    "source_id": thread_ts,
                }
            )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return qa_list


def run_import() -> dict:
    """
    Slackからデータを取得し、embedding生成後にSupabaseへupsert。
    返り値: {"total": 取得件数, "upserted": 登録件数}
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel_id = os.environ.get("SLACK_CHANNEL_ID", "")
    if not token or not channel_id:
        return {"error": "SLACK_BOT_TOKEN または SLACK_CHANNEL_ID が未設定です。"}

    client = WebClient(token=token)
    qa_list = fetch_qa_from_slack(client, channel_id)

    upserted = 0
    for qa in qa_list:
        cleaned = ai.clean_qa_text(qa["title"], qa["question"], qa["answer"])
        embedding = search.get_qa_embedding(cleaned["title"], cleaned["question"], cleaned["answer"])
        db.upsert_qa_by_source_id(
            source="slack",
            source_id=qa["source_id"],
            title=cleaned["title"],
            question=cleaned["question"],
            answer=cleaned["answer"],
            embedding=embedding,
        )
        upserted += 1

    return {"total": len(qa_list), "upserted": upserted}
