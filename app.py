"""進入頁 = 登入閘 + 導覽。

實際表單在 pages/1_新增申請.py、案件在 pages/2_案件清單.py。
"""
import streamlit as st
from core.auth import require_login, logout

st.set_page_config(page_title="居家牙醫申請優化系統", page_icon="🦷", layout="wide")

user = require_login()

st.title("🦷 居家牙醫申請優化系統")
st.markdown(f"歡迎，**{user}** 👋")

st.subheader("📋 開始使用")
st.markdown(
    """
    1. 左側點 **新增申請** → 填表 → 上傳口腔照片
    2. 點「📄 產生 PDF 並標記為已送出」→ 系統自動跳寄信視窗
    3. 確認後一鍵寄到 `dental@cda.org.tw`（也可以先下載 PDF 檢查再寄）
    4. 之後回 app 把案件狀態改成對應的（補件中／已通過等）
    """
)

st.divider()
st.warning(
    "🔒 **資料隱私提醒**：本系統存身分證／健康狀況等敏感資料。"
    "用完請**登出**、共用電腦請**關閉分頁**、不要在公共電腦使用。"
)
st.caption("🆘 卡住請聯絡 Hanna")

with st.sidebar:
    st.divider()
    if st.button("登出"):
        logout()
        st.rerun()
