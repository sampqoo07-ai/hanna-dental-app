"""進入頁 = 登入閘 + 導覽。

實際表單在 pages/1_新增申請.py、案件在 pages/2_案件清單.py。
"""
import streamlit as st
from core.auth import require_login

st.set_page_config(page_title="居家牙醫申請優化系統", page_icon="🦷", layout="wide")

user = require_login()

st.title("🦷 居家牙醫申請優化系統")
st.markdown(f"歡迎，**{user}**。請從左側選單選擇功能：")

st.markdown(
    """
    - **新增申請** — 填寫個案資料、上傳口腔照片，生成可寄出的 PDF
    - **案件清單** — 查看／編輯／重印過往案件

    ---
    📌 PDF 生成後請手動寄到 `dental@cda.org.tw`（系統不會自動寄）。
    """
)

with st.sidebar:
    st.divider()
    if st.button("登出"):
        for k in ("authed", "user_name"):
            st.session_state.pop(k, None)
        st.rerun()
