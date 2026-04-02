"""共通サイドバーコンポーネント"""

import streamlit as st


def show_sidebar():
    """ログインユーザー情報とログアウトボタンを表示"""
    user = st.session_state.get("user")
    if not user:
        return

    with st.sidebar:
        st.markdown(f"**{user['display_name']}** でログイン中")
        if user.get("is_admin"):
            st.caption("管理者")

        if st.button("ログアウト"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.switch_page("app.py")
