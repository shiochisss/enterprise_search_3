"""回答募集中ページ — 未回答・回答評価待ち・過去のQAの3タブ構成"""

import streamlit as st
import db
import search
from sidebar import show_sidebar

# 認証チェック
if "user" not in st.session_state:
    st.switch_page("app.py")

show_sidebar()

st.title("🙋 回答募集中")

# 全質問を取得して振り分け
all_questions = db.fetch_all_pending_questions()

unanswered = [q for q in all_questions if not q.get("resolved")]
awaiting_rating = [
    q for q in all_questions
    if q.get("resolved") and not (q.get("satisfaction_rating") or 0)
]
past_qa = [
    q for q in all_questions
    if q.get("resolved") and (q.get("satisfaction_rating") or 0) > 0
]

tab1, tab2, tab3 = st.tabs([
    f"❓ 未回答（{len(unanswered)}）",
    f"⏳ 回答評価待ち（{len(awaiting_rating)}）",
    f"📚 過去のQA（{len(past_qa)}）",
])

# ──────────────────────────────────────
# タブ1: 未回答
# ──────────────────────────────────────
with tab1:
    if not unanswered:
        st.info("現在、未回答の質問はありません。")
    else:
        for q in unanswered:
            with st.expander(f"❓ {q['question']}（投稿者: {q.get('asked_by', '不明')}）"):
                st.caption(f"投稿日時: {q.get('created_at', '')}")

                answer_key = f"answer_{q['id']}"
                answer = st.text_area("回答を入力", key=answer_key)

                if st.button("回答を送信", key=f"submit_{q['id']}"):
                    if not answer:
                        st.error("回答を入力してください。")
                    else:
                        user_name = st.session_state.user["display_name"]
                        db.resolve_pending_question(q["id"], answer, user_name)
                        embedding = search.get_qa_embedding(q["question"][:50], q["question"], answer)
                        db.insert_qa(
                            title=q["question"][:50],
                            question=q["question"],
                            answer=answer,
                            source="user",
                            embedding=embedding,
                            created_by=user_name,
                        )
                        st.success("回答を送信し、ナレッジベースに登録しました！")
                        st.rerun()

# ──────────────────────────────────────
# タブ2: 回答評価待ち
# ──────────────────────────────────────
with tab2:
    if not awaiting_rating:
        st.info("現在、評価待ちの回答はありません。")
    else:
        for q in awaiting_rating:
            with st.expander(f"💬 {q['question']}（投稿者: {q.get('asked_by', '不明')}）"):
                st.markdown(f"**回答:** {q.get('answer', '')}")
                st.caption(f"回答者: {q.get('resolved_by', '')} / 投稿日時: {q.get('created_at', '')}")

                rating = st.radio(
                    "満足度を評価してください",
                    options=[5, 4, 3, 2, 1],
                    format_func=lambda x: "⭐" * x,
                    horizontal=True,
                    key=f"rating_{q['id']}",
                )

                if st.button("評価を送信", key=f"rate_{q['id']}"):
                    db.rate_pending_question(q["id"], rating)
                    st.success("評価を送信しました。ありがとうございます！")
                    st.rerun()

# ──────────────────────────────────────
# タブ3: 過去のQA
# ──────────────────────────────────────
with tab3:
    if not past_qa:
        st.info("過去のQAはまだありません。")
    else:
        for q in past_qa:
            with st.expander(f"✅ {q['question']}（投稿者: {q.get('asked_by', '不明')}）"):
                st.markdown(f"**回答:** {q.get('answer', '')}")
                st.caption(
                    f"回答者: {q.get('resolved_by', '')} / "
                    f"満足度: {'⭐' * q.get('satisfaction_rating', 0)} / "
                    f"投稿日時: {q.get('created_at', '')}"
                )
