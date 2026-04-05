"""ダッシュボード集計ロジック

このモジュールは、ダッシュボード表示に必要な統計データの集計を行う。
検索状況、コスト削減状況、知恵袋状況などの各種指標を計算し、
UI層に提供するデータを準備する責務を持つ。
"""

from collections import defaultdict
import db
import pandas as pd

# ========================================
# コスト削減計算用定数
# ========================================
MINUTES_SAVED_PER_SEARCH = 16        # 1件あたり削減分数：従来の探索時間19分 - アプリ検索時間3分
HOURLY_WAGE = 3000                   # 時給（円）全社員平均想定。年収576万円ベース（576万円 / 240営業日 / 8時間）
COST_SAVED_PER_SEARCH = 800          # 1件あたり削減コスト（円）：16分 / 60分 × 3000円

# ========================================
# 回答関連の統計
# ========================================

def fetch_answer_stats() -> list[dict]:
    """
    人別の回答数を集計。
    返り値: [{"name": str, "count": int}, ...]
    """
    questions = db.fetch_all_pending_questions()
    counter: dict[str, int] = defaultdict(int)
    for q in questions:
        if q.get("resolved") and q.get("resolved_by"):
            counter[q["resolved_by"]] += 1  # 回答者ごとに解決した質問数をカウント

    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda x: -x[1])  # 回答数降順でソート
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
            ratings[q["resolved_by"]].append(rating)  # 回答者ごとに満足度をリスト化

    return [
        {
            "name": name,
            "avg_rating": sum(vals) / len(vals),  # 平均満足度 = 満足度の合計 / 件数
            "count": len(vals),  # 評価件数
        }
        for name, vals in sorted(ratings.items(), key=lambda x: -sum(x[1]) / len(x[1]))  # 平均満足度降順でソート
    ]


# ========================================
# コスト削減関連の統計
# ========================================

def fetch_search_cost_stats() -> dict:
    """
    探索コスト削減の集計。
    AI検索で満足（rating >= 4）した場合、人に聞く必要がなかったとみなす。
    """
    history = db.fetch_search_history(limit=10000)
    total = len(history)  # 総検索数
    satisfied = sum(1 for h in history if (h.get("satisfaction_rating") or 0) >= 4)  # 満足度4以上の検索数

    # TODO: 将来対応 - 検索開始〜満足度回答までの実測セッション時間を計測し、削減時間をより正確に算出
    total_saved_minutes = satisfied * MINUTES_SAVED_PER_SEARCH  # 削減時間 = 満足検索数 × 16分
    total_saved_cost = satisfied * COST_SAVED_PER_SEARCH  # 削減コスト = 満足検索数 × 800円

    return {
        "total_searches": total,
        "satisfied_searches": satisfied,
        "cost_reduction_rate": (satisfied / total * 100) if total > 0 else 0,  # AI解決率 = 満足検索数 / 総検索数 × 100
        "total_saved_minutes": total_saved_minutes,
        "total_saved_cost": total_saved_cost,
    }


def fetch_question_cost_stats() -> dict:
    """
    質問対応工数削減の集計。
    AI検索で解決した数（満足度4以上）vs 回答募集に至った数を比較。
    """
    history = db.fetch_search_history(limit=10000)
    questions = db.fetch_all_pending_questions()

    total_searches = len(history)  # 総検索数
    ai_resolved = sum(1 for h in history if (h.get("satisfaction_rating") or 0) >= 4)  # 満足度4以上の検索数
    human_escalated = len(questions)  # 回答募集数（質問総数）
    human_resolved = sum(1 for q in questions if q.get("resolved"))  # 回答済（解決フラグがついた質問数）
    evaluated = sum(1 for q in questions if q.get("satisfaction_rating") is not None)  # 評価済（満足度が入力された質問数）
    highly_satisfied = sum(1 for q in questions if (q.get("satisfaction_rating") or 0) >= 4)  # 解決済（満足度4以上の質問数）

    # 知恵袋関連の計算
    awaiting_answer = human_escalated - human_resolved  # 回答待ち = 回答募集数 - 回答済み
    answered_awaiting_rating = human_resolved - evaluated  # 回答済み（評価待ち） = 回答済み - 評価済み

    return {
        "total_searches": total_searches,
        "ai_resolved": ai_resolved,
        "human_escalated": human_escalated,  # 回答募集数
        "awaiting_answer": awaiting_answer,  # 回答待ち
        "answered_awaiting_rating": answered_awaiting_rating,  # 回答済み（評価待ち含む）
        "human_resolved": human_resolved,
        "evaluated": evaluated,  # 解決済み（評価完了）
        "highly_satisfied": highly_satisfied,
    }


# ========================================
# トレンド分析
# ========================================

def fetch_search_trends() -> list[dict]:
    """
    検索トレンドの集計（日別検索数）。
    返り値: [{"date": "YYYY-MM-DD", "searches": int}, ...]
    """
    history = db.fetch_search_history(limit=10000)
    if not history:
        return []

    # pandas DataFrame に変換
    df = pd.DataFrame(history)
    df['searched_at'] = pd.to_datetime(df['searched_at'])
    df['date'] = df['searched_at'].dt.date  # 日付列を作成

    # 日別集計
    daily_counts = df.groupby('date').size().reset_index(name='searches')  # 日付ごとに検索数をカウント
    daily_counts['date'] = daily_counts['date'].astype(str)  # JSONシリアライズ用

    return daily_counts.to_dict('records')


def fetch_answer_ranking_stacked() -> pd.DataFrame:
    """
    回答ランキングの積み上げデータを作成。
    返り値: DataFrame with columns ['name', 'category', 'count']
    category: '★4以上', '★3以下', '評価待ち'（下から上の順）
    """
    questions = db.fetch_all_pending_questions()
    stats = defaultdict(lambda: {'waiting': 0, '3below': 0, '4plus': 0})

    for q in questions:
        if not q.get("resolved") or not q.get("resolved_by"):
            continue
        name = q["resolved_by"]
        rating = q.get("satisfaction_rating")
        if rating is None:
            stats[name]['waiting'] += 1  # 評価待ち
        elif rating >= 4:
            stats[name]['4plus'] += 1  # ★4以上
        else:  # 1 <= rating < 4
            stats[name]['3below'] += 1  # ★3以下

    # DataFrame作成
    rows = []
    for name, counts in stats.items():
        rows.append({'name': name, 'category': '★4以上', 'count': counts['4plus']})
        rows.append({'name': name, 'category': '★3以下', 'count': counts['3below']})
        rows.append({'name': name, 'category': '評価待ち', 'count': counts['waiting']})

    df = pd.DataFrame(rows)
    # 総回答数でソート（降順）
    total_by_name = df.groupby('name')['count'].sum().sort_values(ascending=False)
    name_order = total_by_name.index.tolist()
    
    # nameをカテゴリカル型に設定して、指定の順序を保つ
    df['name'] = pd.Categorical(df['name'], categories=name_order, ordered=True)
    df = df.sort_values('name')
    
    return df
