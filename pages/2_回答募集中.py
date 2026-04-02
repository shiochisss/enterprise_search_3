"""回答募集中ページ — 未解決質問の一覧表示＋回答入力"""

import streamlit as st
import db
import search
from sidebar import show_sidebar

# 認証チェック
if "user" not in st.session_state:
    st.switch_page("app.py")

show_sidebar()

st.title("🙋 回答募集中")
st.markdown("まだ解決していない質問の一覧です。回答できるものがあれば入力してください。")

questions = db.fetch_pending_questions()

if not questions:
    st.info("現在、回答募集中の質問はありません。")
else:
    for q in questions:
        with st.expander(f"❓ {q['question']}（投稿者: {q.get('asked_by', '不明')}）"):
            st.caption(f"投稿日時: {q.get('created_at', '')}")

            answer_key = f"answer_{q['id']}"
            answer = st.text_area("回答を入力", key=answer_key)

            if st.button("回答を送信", key=f"submit_{q['id']}"):
                if not answer:
                    st.error("回答を入力してください。")
                else:
                    user_name = st.session_state.user["display_name"]
                    # 質問を解決済みにする
                    db.resolve_pending_question(q["id"], answer, user_name)
                    # 回答をQAペアとしてナレッジベースに登録
                    embedding = search.get_embedding(q["question"])
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
