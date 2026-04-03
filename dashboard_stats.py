"""ダッシュボード集計ロジック"""

from collections import defaultdict
import db


def fetch_answer_stats() -> list[dict]:
    """
    人別の回答数を集計。
    返り値: [{"name": str, "count": int}, ...]
    """
    questions = db.fetch_all_pending_questions()
    counter: dict[str, int] = defaultdict(int)
    for q in questions:
        if q.get("resolved") and q.get("resolved_by"):
            counter[q["resolved_by"]] += 1

    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda x: -x[1])
    ]


def fetch_satisfaction_stats() -> list[dict]:
    """
    人別の回答満足度を集計。
    返り値: [{"name": str, "avg_rating": float, "count": int}, ...]
    """
    questions = db.fetch_all_pending_questions()
    ratings: dict[str, list[int]] = defaultdict(list)
    for q in questions:
        rating = q.get("satisfaction_rating") or 0
        if q.get("resolved") and q.get("resolved_by") and rating > 0:
            ratings[q["resolved_by"]].append(rating)

    return [
        {
            "name": name,
            "avg_rating": sum(vals) / len(vals),
            "count": len(vals),
        }
        for name, vals in sorted(ratings.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    ]


def fetch_search_cost_stats() -> dict:
    """
    探索コスト削減の集計。
    AI検索で満足（rating >= 4）した場合、人に聞く必要がなかったとみなす。
    """
    history = db.fetch_search_history(limit=10000)
    total = len(history)
    satisfied = sum(1 for h in history if (h.get("satisfaction_rating") or 0) >= 4)

    return {
        "total_searches": total,
        "satisfied_searches": satisfied,
        "cost_reduction_rate": (satisfied / total * 100) if total > 0 else 0,
    }


def fetch_question_cost_stats() -> dict:
    """
    質問対応工数削減の集計。
    AI検索で解決した数（満足度4以上）vs 回答募集に至った数を比較。
    """
    history = db.fetch_search_history(limit=10000)
    questions = db.fetch_all_pending_questions()

    total_searches = len(history)
    ai_resolved = sum(1 for h in history if (h.get("satisfaction_rating") or 0) >= 4)
    human_escalated = len(questions)
    human_resolved = sum(1 for q in questions if q.get("resolved"))

    return {
        "total_searches": total_searches,
        "ai_resolved": ai_resolved,
        "human_escalated": human_escalated,
        "human_resolved": human_resolved,
    }
