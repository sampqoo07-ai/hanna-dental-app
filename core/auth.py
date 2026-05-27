"""共用密碼登入閘 + 操作者署名。

登入成功會把名字＋簽章寫進瀏覽器 cookie（7 天有效），這樣
手機按上一頁／重新開分頁不用反覆登入。
"""
from __future__ import annotations
import hmac
import hashlib
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx


COOKIE_NAME = "dental_app_auth"
COOKIE_TTL_DAYS = 7


def _sign(name: str, secret: str) -> str:
    return hmac.new(secret.encode(), name.encode(), hashlib.sha256).hexdigest()


def _verify(token: str, name: str, secret: str) -> bool:
    if not token or not name:
        return False
    return hmac.compare_digest(token, _sign(name, secret))


def _cookie_mgr() -> stx.CookieManager:
    # 用 cache_resource 確保整個 session 用同一個 manager 實例
    if "_cookie_mgr" not in st.session_state:
        st.session_state["_cookie_mgr"] = stx.CookieManager(key="dental_cookie_mgr")
    return st.session_state["_cookie_mgr"]


def require_login() -> str:
    """擋在所有頁面前面。回傳使用者填的暱稱（會記在每筆案件的 created_by）。"""
    secret = st.secrets.get("app_password", "")

    # 1) session_state 有就直接用
    if st.session_state.get("authed"):
        return st.session_state["user_name"]

    # 2) 沒有就看 cookie（手機回上一頁、重開分頁時走這條）
    cm = _cookie_mgr()
    cookie_val = cm.get(COOKIE_NAME)
    if cookie_val and isinstance(cookie_val, dict):
        name = cookie_val.get("name", "")
        token = cookie_val.get("token", "")
        if _verify(token, name, secret):
            st.session_state["authed"] = True
            st.session_state["user_name"] = name
            return name

    # 3) 都沒有，顯示登入表單
    st.title("🦷 居家牙醫申請優化系統")
    with st.form("login"):
        name = st.text_input("你的姓名／暱稱", help="會記在你建立的每筆案件上，方便清單篩選")
        pw = st.text_input("共用密碼", type="password")
        ok = st.form_submit_button("登入", type="primary", use_container_width=True)

    if ok:
        if not name.strip():
            st.error("請填姓名／暱稱")
        elif pw != secret:
            st.error("密碼錯誤")
        else:
            name = name.strip()
            st.session_state["authed"] = True
            st.session_state["user_name"] = name
            cm.set(
                COOKIE_NAME,
                {"name": name, "token": _sign(name, secret)},
                expires_at=datetime.now() + timedelta(days=COOKIE_TTL_DAYS),
                key=f"cookie_set_{name}",
            )
            st.rerun()
    st.stop()


def logout() -> None:
    """清空 session_state + 刪 cookie。給 app.py 登出按鈕用。"""
    cm = _cookie_mgr()
    try:
        cm.delete(COOKIE_NAME, key="cookie_del")
    except Exception:
        pass
    for k in ("authed", "user_name"):
        st.session_state.pop(k, None)
