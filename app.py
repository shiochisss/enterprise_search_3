"""社内検索＆知恵袋アプリ — エントリポイント（ログイン画面）"""

import streamlit as st
import auth

st.set_page_config(page_title="社内検索＆知恵袋", page_icon="🔍", layout="wide")

# 管理者アカウントの初期作成（初回のみ）
auth.create_user("admin", "admin", "管理者", is_admin=True)

# ログイン済みならリダイレクト
if "user" in st.session_state:
    st.switch_page("pages/1_質問する.py")

st.title("社内検索＆知恵袋")
st.subheader("ログイン")

with st.form("login_form"):
    user_id = st.text_input("ユーザーID")
    password = st.text_input("パスワード", type="password")
    submitted = st.form_submit_button("ログイン")

if submitted:
    if not user_id or not password:
        st.error("ユーザーIDとパスワードを入力してください。")
    else:
        user = auth.authenticate(user_id, password)
        if user:
            st.session_state.user = user
            st.switch_page("pages/1_質問する.py")
        else:
            st.error("ユーザーIDまたはパスワードが正しくありません。")
