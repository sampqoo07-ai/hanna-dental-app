"""案件清單：預設只看自己的，可切看全部。"""
import pandas as pd
import streamlit as st
from core.auth import require_login
from core import storage

st.set_page_config(page_title="案件清單", page_icon="📋", layout="wide")
user = require_login()

st.title("📋 案件清單")

c1, c2 = st.columns([1, 4])
with c1:
    mine_only = st.toggle("只看我的", value=True)
with c2:
    status_filter = st.multiselect(
        "狀態篩選",
        list(storage.STATUS_LABELS.keys()),
        default=[],
        format_func=storage.status_label,
    )

try:
    rows = storage.list_applications(user, mine_only=mine_only)
except Exception as e:
    st.error(f"讀取案件清單失敗：{type(e).__name__}")
    # 把 PostgREST 結構化錯誤拆出來顯示
    for attr in ("message", "code", "details", "hint"):
        v = getattr(e, attr, None)
        if v:
            st.code(f"{attr}: {v}")
    st.caption("如果看到 invalid API key／JWT 之類訊息，多半是 Streamlit Cloud Secrets 沒同步成最新的 service_key。")
    st.stop()
if status_filter:
    rows = [r for r in rows if r.get("status") in status_filter]

if not rows:
    st.info("目前沒有案件。到「新增申請」開一份吧。")
    st.stop()

df = pd.DataFrame([
    {
        "案件編號": r["id"][:8],
        "個案姓名": r.get("case_name") or "(未命名)",
        "狀態": storage.status_label(r.get("status")),
        "建立者": r.get("created_by"),
        "更新時間": r.get("updated_at", "")[:16].replace("T", " "),
        "_id": r["id"],
    }
    for r in rows
])

st.dataframe(
    df.drop(columns=["_id"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("選一筆來編輯／重印")
choice = st.selectbox(
    "案件",
    options=df["_id"].tolist(),
    format_func=lambda i: f"{df[df._id==i]['個案姓名'].iloc[0]}（{i[:8]}）",
)
if st.button("開啟", type="primary"):
    # st.switch_page 不會帶 query_params，用 session 旗標傳遞，新增申請頁讀完即丟
    st.session_state["_open_case_id"] = choice
    st.switch_page("pages/1_新增申請.py")
