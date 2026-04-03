"""管理者専用ページ — QA一覧CRUD＋ユーザー管理＋データインポート"""

import streamlit as st
import db
import auth
import search
import slack_import
import notion_import
from sidebar import show_sidebar

# 認証チェック
if "user" not in st.session_state:
    st.switch_page("app.py")

if not st.session_state.user.get("is_admin"):
    st.error("このページは管理者専用です。")
    st.stop()

show_sidebar()

st.title("⚙️ 管理")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📚 全データ一覧", "👥 ユーザー管理", "📥 データインポート", "❓ 質問管理"]
)

# ──────────────────────────────────────
# タブ1: 全データ一覧
# ──────────────────────────────────────
with tab1:
    st.subheader("全QAデータ一覧")

    qa_list = db.fetch_all_qa()

    if not qa_list:
        st.info("データがありません。")
    else:
        for qa in qa_list:
            with st.expander(
                f"[{qa.get('source', '')}] {qa.get('title', '無題')} (ID: {qa['id']})"
            ):
                st.markdown(f"**質問:** {qa.get('question', '')}")
                st.markdown(f"**回答:** {qa.get('answer', '')}")
                st.caption(
                    f"作成者: {qa.get('created_by', '')} / "
                    f"更新者: {qa.get('updated_by', '')} / "
                    f"作成日時: {qa.get('created_at', '')}"
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("削除", key=f"del_qa_{qa['id']}"):
                        db.delete_qa(qa["id"])
                        st.success("削除しました。")
                        st.rerun()

    # 手動QA追加
    st.divider()
    st.subheader("QAデータを手動追加")
    with st.form("add_qa_form"):
        new_title = st.text_input("タイトル")
        new_question = st.text_area("質問")
        new_answer = st.text_area("回答")
        add_submitted = st.form_submit_button("追加")

    if add_submitted and new_question and new_answer:
        embedding = search.get_qa_embedding(new_title or new_question[:50], new_question, new_answer)
        db.insert_qa(
            title=new_title or new_question[:50],
            question=new_question,
            answer=new_answer,
            source="user",
            embedding=embedding,
            created_by=st.session_state.user["display_name"],
        )
        st.success("QAデータを追加しました。")
        st.rerun()

# ──────────────────────────────────────
# タブ2: ユーザー管理
# ──────────────────────────────────────
with tab2:
    st.subheader("ユーザー一覧")
    users = auth.fetch_all_users()

    if users:
        for u in users:
            role = "管理者" if u.get("is_admin") else "一般"
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{u['display_name']}** ({u['user_id']}) — {role}")
            with col2:
                st.caption(f"{u.get('created_at', '')[:10]}")
            with col3:
                if u["user_id"] != "admin":
                    if st.button("削除", key=f"del_user_{u['user_id']}"):
                        auth.delete_user(u["user_id"])
                        st.success(f"{u['display_name']} を削除しました。")
                        st.rerun()

    st.divider()
    st.subheader("ユーザーを追加")
    with st.form("add_user_form"):
        new_user_id = st.text_input("ユーザーID")
        new_password = st.text_input("パスワード", type="password")
        new_display_name = st.text_input("表示名")
        new_is_admin = st.checkbox("管理者権限")
        user_submitted = st.form_submit_button("追加")

    if user_submitted:
        if not new_user_id or not new_password or not new_display_name:
            st.error("全項目を入力してください。")
        else:
            ok = auth.create_user(new_user_id, new_password, new_display_name, new_is_admin)
            if ok:
                st.success(f"{new_display_name} を追加しました。")
                st.rerun()
            else:
                st.error("このユーザーIDは既に使用されています。")

# ──────────────────────────────────────
# タブ3: データインポート
# ──────────────────────────────────────
with tab3:
    st.subheader("外部データのインポート")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Slack")
        st.markdown("Slackチャンネルからスレッドを取得し、QAデータとして登録します。")
        if st.button("Slackインポート実行", type="primary"):
            with st.spinner("Slackからデータを取得中..."):
                result = slack_import.run_import()
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(
                    f"完了: {result['total']}件取得、{result['upserted']}件登録/更新"
                )

    with col2:
        st.markdown("### Notion")
        st.markdown("Notionデータベースからページを取得し、QAデータとして登録します。")
        if st.button("Notionインポート実行", type="primary"):
            with st.spinner("Notionからデータを取得中..."):
                result = notion_import.run_import()
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(
                    f"完了: {result['total']}件取得、{result['upserted']}件登録/更新"
                )

# ──────────────────────────────────────
# タブ4: 質問管理
# ──────────────────────────────────────
with tab4:
    st.subheader("全質問一覧（解決済み含む）")
    all_questions = db.fetch_all_pending_questions()

    if not all_questions:
        st.info("質問がありません。")
    else:
        for q in all_questions:
            status = "✅ 解決済み" if q.get("resolved") else "❓ 未解決"
            with st.expander(f"{status} {q['question']}"):
                st.caption(f"投稿者: {q.get('asked_by', '')} / 投稿日時: {q.get('created_at', '')}")
                if q.get("resolved"):
                    st.markdown(f"**回答:** {q.get('answer', '')}")
                    st.caption(f"回答者: {q.get('resolved_by', '')}")
                    if q.get("satisfaction_rating"):
                        st.caption(f"満足度: {'⭐' * q['satisfaction_rating']}")

                if st.button("削除", key=f"del_pq_{q['id']}"):
                    db.delete_pending_question(q["id"])
                    st.success("削除しました。")
                    st.rerun()
