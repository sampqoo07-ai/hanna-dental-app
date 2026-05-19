"""共用密碼登入閘 + 操作者署名。"""
import streamlit as st


def require_login() -> str:
    """擋在所有頁面前面。回傳使用者填的暱稱（會記在每筆案件的 created_by）。"""
    if st.session_state.get("authed"):
        return st.session_state["user_name"]

    st.title("🦷 居家牙醫申請優化系統")
    with st.form("login"):
        name = st.text_input("你的姓名／暱稱", help="會記在你建立的每筆案件上，方便清單篩選")
        pw = st.text_input("共用密碼", type="password")
        ok = st.form_submit_button("登入", type="primary", use_container_width=True)

    if ok:
        if not name.strip():
            st.error("請填姓名／暱稱")
        elif pw != st.secrets.get("app_password"):
            st.error("密碼錯誤")
        else:
            st.session_state["authed"] = True
            st.session_state["user_name"] = name.strip()
            st.rerun()
    st.stop()
