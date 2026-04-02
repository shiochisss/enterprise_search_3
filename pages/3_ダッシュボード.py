"""管理者専用ダッシュボード — 統計情報の表示"""

import streamlit as st
import pandas as pd
import dashboard_stats
from sidebar import show_sidebar

# 認証チェック
if "user" not in st.session_state:
    st.switch_page("app.py")

if not st.session_state.user.get("is_admin"):
    st.error("このページは管理者専用です。")
    st.stop()

show_sidebar()

st.title("📊 ダッシュボード")

# ── KPI指標 ──
col1, col2, col3, col4 = st.columns(4)

search_cost = dashboard_stats.fetch_search_cost_stats()
question_cost = dashboard_stats.fetch_question_cost_stats()

with col1:
    st.metric("総検索数", search_cost["total_searches"])
with col2:
    st.metric("AI解決率", f"{search_cost['cost_reduction_rate']:.1f}%")
with col3:
    st.metric("回答募集数", question_cost["human_escalated"])
with col4:
    st.metric("人的解決数", question_cost["human_resolved"])

st.divider()

# ── 探索コスト削減 ──
st.subheader("🔍 探索コスト削減")
col1, col2 = st.columns(2)
with col1:
    st.metric(
        "AI検索で解決（満足度4以上）",
        f"{search_cost['satisfied_searches']}件",
        help="検索後に満足度4以上の評価をしたケース＝人に聞く必要がなかった",
    )
with col2:
    st.metric(
        "コスト削減率",
        f"{search_cost['cost_reduction_rate']:.1f}%",
        help="AI検索で解決した割合",
    )

st.divider()

# ── 質問対応工数削減 ──
st.subheader("💬 質問対応工数削減")
col1, col2 = st.columns(2)
with col1:
    st.metric("AI解決数", question_cost["ai_resolved"])
with col2:
    st.metric("人的対応数", question_cost["human_resolved"])

if question_cost["total_searches"] > 0:
    ai_rate = question_cost["ai_resolved"] / question_cost["total_searches"] * 100
    st.progress(ai_rate / 100, text=f"AI解決率: {ai_rate:.1f}%")

st.divider()

# ── 回答数（人別） ──
st.subheader("🏆 回答数ランキング（人別）")
answer_stats = dashboard_stats.fetch_answer_stats()
if answer_stats:
    df_answers = pd.DataFrame(answer_stats)
    st.bar_chart(df_answers.set_index("name")["count"])
else:
    st.info("まだ回答データがありません。")

st.divider()

# ── 回答満足度（人別） ──
st.subheader("⭐ 回答満足度（人別）")
satisfaction_stats = dashboard_stats.fetch_satisfaction_stats()
if satisfaction_stats:
    df_satisfaction = pd.DataFrame(satisfaction_stats)
    for _, row in df_satisfaction.iterrows():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"**{row['name']}**")
        with col2:
            st.write(f"{'⭐' * round(row['avg_rating'])} ({row['avg_rating']:.1f})")
        with col3:
            st.write(f"{row['count']}件")
else:
    st.info("まだ満足度データがありません。")
