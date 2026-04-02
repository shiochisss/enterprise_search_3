"""検索ページ — クエリ入力→類似検索→AI要約→満足度評価→回答募集"""

import streamlit as st
import search
import ai
import db
from sidebar import show_sidebar

# 認証チェック
if "user" not in st.session_state:
    st.switch_page("app.py")

show_sidebar()

st.title("🔍 質問する")
st.markdown("わからないことを入力して検索してください。")

# ── 検索入力 ──
query = st.text_input("検索クエリ", placeholder="例: 有給休暇の申請方法は？")

if st.button("検索", type="primary") and query:
    st.session_state.search_query = query
    st.session_state.search_results = None
    st.session_state.search_history_id = None
    st.session_state.ai_answer = None

# ── 検索実行 ──
if st.session_state.get("search_query") and st.session_state.get("search_results") is None:
    query = st.session_state.search_query
    with st.spinner("検索中..."):
        results = search.find_similar(query, top_k=10)
        st.session_state.search_results = results

        # 検索履歴を保存
        if results:
            search_id = db.insert_search_history(
                query, results, st.session_state.user["display_name"]
            )
            st.session_state.search_history_id = search_id
    st.rerun()

# ── 検索結果表示 ──
results = st.session_state.get("search_results")
if results is not None:
    query = st.session_state.search_query

    if not results:
        st.warning("該当するデータが見つかりませんでした。")
    else:
        # AI要約（上位3件を基に）
        st.subheader("💡 AIによる回答")
        top_3 = results[:3]
        answer_placeholder = st.empty()
        full_answer = ""
        for chunk in ai.generate_answer_stream(query, top_3):
            full_answer += chunk
            answer_placeholder.markdown(full_answer)
        st.session_state.ai_answer = full_answer

        # 検索結果一覧
        st.subheader("📋 検索結果")
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            source = r.get("source", "不明")
            with st.expander(
                f"#{i} {r.get('title', '無題')}（類似度: {score:.2f} / 出典: {source}）"
            ):
                st.markdown(f"**質問:** {r.get('question', '')}")
                st.markdown(f"**回答:** {r.get('answer', '')}")

        # 満足度評価
        st.subheader("📝 この検索結果は役に立ちましたか？")
        col1, col2 = st.columns([1, 2])
        with col1:
            rating = st.radio(
                "満足度",
                options=[5, 4, 3, 2, 1],
                format_func=lambda x: "⭐" * x,
                horizontal=True,
                key="search_rating",
            )
        with col2:
            if st.button("評価を送信"):
                search_id = st.session_state.get("search_history_id")
                if search_id:
                    db.rate_search(search_id, rating)
                    st.success("評価を送信しました。ありがとうございます！")

        # 回答募集ボタン
        st.divider()
        st.markdown("検索結果に満足できない場合は、他のユーザーに回答を募集できます。")
        if st.button("🙋 回答を募集する"):
            db.insert_pending_question(query, st.session_state.user["display_name"])
            st.success("回答募集を投稿しました。「回答募集中」ページで確認できます。")
