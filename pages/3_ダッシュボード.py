"""管理者専用ダッシュボード — 統計情報の表示

このページは、アプリケーション全体の利用状況と効果を可視化する管理者向けダッシュボード。
以下の4つのセクションで、多角的な指標を表示：
1. 検索状況：検索利用の基本指標
2. 検索コスト削減状況：AI検索による業務効率化の効果
3. 知恵袋状況：ユーザー間質問応答の進捗状況
4. 回答ランキング：高貢献度ユーザーの可視化
"""

import streamlit as st
import pandas as pd
import altair as alt
import dashboard_stats
from sidebar import show_sidebar


# ========================================
# ユーティリティ関数
# ========================================

def format_minutes_as_hms(total_minutes: int) -> str:
    """
    总分数を「X時間Y分」形式に変換する。
    
    Parameters:
        total_minutes (int): 総分数
    
    Returns:
        str: フォーマット済みの時間表記。例："3時間10分" または "30分"
    """
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}時間{minutes}分" if hours > 0 else f"{minutes}分"


# ========================================
# ページ認証
# ========================================

if "user" not in st.session_state:
    st.switch_page("app.py")

if not st.session_state.user.get("is_admin"):
    st.error("このページは管理者専用です。")
    st.stop()

show_sidebar()

st.title("📊 ダッシュボード")

# 統計データ取得
search_cost = dashboard_stats.fetch_search_cost_stats()
question_cost = dashboard_stats.fetch_question_cost_stats()


# ========================================
# セクション1: 検索状況
# ========================================

st.header("🔍 検索状況")
col1, col2 = st.columns(2)
with col1:
    st.metric("総検索数", search_cost["total_searches"])
with col2:
    st.metric(
        "AI解決率",
        f"{search_cost['cost_reduction_rate']:.1f}%",
        help="AI検索で満足度4以上の割合。計算: (満足度4以上の検索数 / 総検索数) × 100%",
    )

st.caption("📈 検索トレンド（時系列）")
search_trends = dashboard_stats.fetch_search_trends()
if search_trends:
    df_trends = pd.DataFrame(search_trends)
    df_trends['date'] = pd.to_datetime(df_trends['date'])
    df_trends = df_trends.set_index('date')
    st.line_chart(df_trends['searches'])
else:
    st.info("まだ検索データがありません。")

st.divider()

# ========================================
# セクション2: 検索コスト削減状況
# ========================================

st.header("💰 検索コスト削減状況")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        "AI検索で解決（満足度4以上）",
        f"{search_cost['satisfied_searches']}件",
        help="検索後に満足度4以上の評価をしたケース（人に聞く必要がなかった）",
    )
with col2:
    time_display = format_minutes_as_hms(search_cost['total_saved_minutes'])
    st.metric(
        "削減した時間（累計）",
        time_display,
        help="解決数 × 16分（従来の探索時間19分-アプリ検索時間3分）",
    )
with col3:
    st.metric(
        "削減した金額（累計）",
        f"{search_cost['total_saved_cost']:,}円",
        help="解決数 × 800円（1件あたりの削減時間16分 × 時給3,000円=年収576万円 ※全社員平均想定）",
    )

st.divider()

# ========================================
# セクション3: 知恵袋状況
# ========================================

st.header("💬 知恵袋状況")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("回答募集数", question_cost["human_escalated"])
with col2:
    st.metric("回答待ち", f"{question_cost['awaiting_answer']}")
with col3:
    st.metric("評価待ち", f"{question_cost['answered_awaiting_rating']}")
with col4:
    st.metric("解決済み", f"{question_cost['evaluated']}")

st.divider()

# ========================================
# セクション4: 回答ランキング
# ========================================

st.header("🏆 回答ランキング")
st.subheader("回答数ランキング（人別）")
df_stacked = dashboard_stats.fetch_answer_ranking_stacked()
if not df_stacked.empty:
    chart = alt.Chart(df_stacked).mark_bar().encode(
        x=alt.X('name:N', title='回答者', sort=list(df_stacked['name'].unique())),
        y=alt.Y('count:Q', title='件数'),
        color=alt.Color('category:N', scale=alt.Scale(domain=['★4以上', '★3以下', '評価待ち'], range=['#9999ff', '#99ff99', '#ff9999']), title='評価'),
        order=alt.Order('category:N', sort='descending')  # 下から★4以上、★3以下、評価待ち
    ).properties(
        width=600,
        height=400
    )
    st.altair_chart(chart)
else:
    st.info("まだ回答データがありません。")

st.subheader("⭐ 回答満足度ランキング")
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
