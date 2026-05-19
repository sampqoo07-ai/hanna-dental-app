"""新增／編輯申請表單。

從 URL query string 帶 ?id=<uuid> 進來就是編輯既有案件，否則是新建。
表單每次「儲存草稿」都會 upsert 到 Supabase。
"""
import streamlit as st
from core.auth import require_login
from core import storage, validators, pdf_builder

st.set_page_config(page_title="新增申請", page_icon="📝", layout="wide")
user = require_login()

# --- 載入既有案件（編輯模式）---
# URL ?id=... 優先；沒有就退回 session_state（rerun 後仍可保住）
app_id = st.query_params.get("id") or st.session_state.get("current_case_id")
if app_id:
    st.session_state["current_case_id"] = app_id  # 保留以防 URL 沒帶
    st.query_params["id"] = app_id                # 同步寫回 URL（方便 bookmark）

existing = storage.get_application(app_id) if app_id else None
payload = (existing or {}).get("payload", {}) if existing else {}
uploads = (existing or {}).get("uploads", []) if existing else []

st.title("📝 " + ("編輯申請" if existing else "新增申請"))
if existing:
    st.caption(f"案件編號：{app_id}　狀態：{storage.status_label(existing.get('status'))}")

# 主內容區的快速操作（手機桌機都看得到）
_action_cols = st.columns([2, 3, 1])
with _action_cols[0]:
    if st.button("✨ 新建空白案件", use_container_width=True):
        st.session_state.pop("current_case_id", None)
        st.session_state.pop("_last_pdf", None)
        st.query_params.clear()
        st.rerun()

if app_id and existing:
    with _action_cols[1]:
        _statuses = list(storage.STATUS_LABELS.keys())
        new_status = st.selectbox(
            "變更狀態",
            _statuses,
            index=_statuses.index(existing.get("status", "draft")),
            format_func=storage.status_label,
            key=f"status_select_{app_id}",
        )
    with _action_cols[2]:
        st.write("")  # 對齊用
        if new_status != existing.get("status") and st.button(
            "套用", use_container_width=True
        ):
            storage.upsert_application(
                app_id, existing["created_by"],
                existing.get("case_name") or "(未命名)",
                existing["payload"], status=new_status,
                uploads=existing.get("uploads", []),
            )
            st.session_state["_saved_msg"] = (
                f"狀態已改為 {storage.status_label(new_status)}"
            )
            st.rerun()

st.divider()

# 顯示上一次儲存／送出後的提示（rerun 之後仍能看到）
_msg = st.session_state.pop("_saved_msg", None)
if _msg:
    st.success(_msg)

# 如果剛剛產生 PDF（屬於這個案件），顯示下載按鈕
_pdf = st.session_state.get("_last_pdf")
if _pdf and _pdf.get("case_id") == app_id:
    st.download_button(
        "⬇️ 下載 PDF",
        _pdf["bytes"],
        file_name=f"居家牙醫申請_{_pdf['name']}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

# --- 表單 ---
with st.expander("一、申請單位資訊", expanded=True):
    CITIES = [
        "基隆市", "台北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
        "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
        "台南市", "高雄市", "屏東縣",
        "宜蘭縣", "花蓮縣", "台東縣",
        "澎湖縣", "金門縣", "連江縣",
    ]
    c1, c2 = st.columns(2)
    with c1:
        city = st.selectbox(
            "縣市別",
            CITIES,
            index=CITIES.index(payload["city"]) if payload.get("city") in CITIES else CITIES.index("雲林縣"),
            key="city",
        )
        applicant = st.text_input("申請人", value=payload.get("applicant", ""))
    with c2:
        unit = st.text_input("單位", value=payload.get("unit", "好所宅診所"))
        app_phone = st.text_input(
            "單位聯絡電話", value=payload.get("app_phone", "05-5880990")
        )

with st.expander("二、聯絡人資訊（家屬資訊）"):
    c1, c2 = st.columns(2)
    with c1:
        contact_name = st.text_input("聯絡人姓名", value=payload.get("contact_name", ""))
    with c2:
        contact_phone = st.text_input("聯絡人電話", value=payload.get("contact_phone", ""))

with st.expander("三、個案基本資料", expanded=True):
    name = st.text_input("個案姓名", value=payload.get("name", ""))
    id_number = st.text_input("身分證字號", value=payload.get("id_number", ""))
    birth_date = st.text_input(
        "出生年月日（例：0650101）",
        value=payload.get("birth_date", ""),
        help="請輸入民國 7 碼格式",
    )
    age = st.number_input("年齡", min_value=0, max_value=120, value=int(payload.get("age", 0)))
    address = st.text_area("住所地址", value=payload.get("address", ""))
    disability = st.text_input(
        "障別／等級（請寫等級，如「中度」）",
        value=payload.get("disability", payload.get("disability_type", "")),
    )
    identity = st.multiselect(
        "身份別",
        ["一般", "低收入戶", "中低收入戶", "身障手冊", "其他"],
        default=payload.get("identity", []),
    )
    other_identity = st.text_input("身份別（其他說明）", value=payload.get("other_identity", ""))
    can_go_out = st.radio(
        "3 個月內是否有自行外出的能力",
        ["否", "是"],
        index=["否", "是"].index(payload.get("can_go_out", "否")),
        horizontal=True,
    )
    qualification = st.radio(
        "個案申請資格",
        [1, 2],
        format_func=lambda i: {
            1: "1. 特定身心障礙者（清醒時 50% 以上活動限制在床／椅上）",
            2: "2. 失能老人（長照中心個案，因疾病傷病長期臥床）",
        }[i],
        index=[1, 2].index(payload.get("qualification", 2)),
    )

with st.expander("四、個案口腔需求"):
    needs = st.multiselect(
        "口腔異常狀況勾選",
        ["疑似牙齦出血紅腫等異常情況", "疑有口腔衛生狀況不佳情況", "其他"],
        default=payload.get("needs", []),
    )
    other_needs = st.text_input("需求（其他說明）", value=payload.get("other_needs", ""))

with st.expander("五、個案身心健康狀況"):
    health_status = st.text_area(
        "個案狀況說明",
        value=payload.get("health_status", ""),
        placeholder="過去病史、口腔清潔狀態、目前牙齒狀況、抗凝血藥物、醫療決策者、主要照顧者、由口進食、嗆咳…",
        height=320,
    )

with st.expander("六、附件上傳", expanded=True):
    st.subheader("口腔照片（建議 2-4 張）")
    new_mouth = st.file_uploader(
        "上傳口腔照片", accept_multiple_files=True, type=["jpg", "png", "jpeg"], key="mouth"
    )
    # 申請資格決定要附什麼證明
    doc_label = (
        "身心障礙證明正反面" if qualification == 1
        else "居家醫療收案 VPN 或身心障礙手冊"
    )
    st.subheader(doc_label)
    new_docs = st.file_uploader(
        f"上傳{doc_label}", accept_multiple_files=True, type=["jpg", "png", "jpeg", "pdf"], key="docs"
    )
    if uploads:
        st.caption(f"已上傳 {len(uploads)} 個附件（編輯模式下會保留，新檔會追加）")

# --- 收集 payload（key 直接對齊 pdf_builder.FIELD_MAP）---
payload_out = {
    "city": city,
    "applicant": applicant,
    "unit": unit,
    "app_phone": app_phone,
    "contact_name": contact_name,
    "contact_phone": contact_phone,
    "name": name,
    "id_number": id_number,
    "birth_date": birth_date,
    "age": age,
    "address": address,
    "disability": disability,
    "identity": identity,
    "other_identity": other_identity,
    "can_go_out": can_go_out,
    "qualification": qualification,
    "needs": needs,
    "other_needs": other_needs,
    "health_status": health_status,
}


def _save_uploads(case_id: str) -> list[dict]:
    new_records = []
    for f in new_mouth or []:
        new_records.append(storage.upload_file(case_id, "mouth_photo", f.name, f.getvalue()))
    for f in new_docs or []:
        kind = "vpn_doc" if qualification == 2 else "id_doc"
        new_records.append(storage.upload_file(case_id, kind, f.name, f.getvalue()))
    return new_records


# --- 動作按鈕 ---
st.divider()
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("💾 儲存草稿", use_container_width=True):
        case_id = storage.upsert_application(
            app_id, user, name or "(未命名)", payload_out, status="draft"
        )
        new_uploads = _save_uploads(case_id)
        if new_uploads:
            storage.upsert_application(
                case_id, user, name or "(未命名)", payload_out,
                status="draft", uploads=uploads + new_uploads,
            )
        st.session_state["current_case_id"] = case_id
        st.session_state["_saved_msg"] = f"草稿已儲存（{case_id[:8]}…）"
        st.query_params["id"] = case_id
        st.rerun()

with c2:
    if st.button("📄 產生 PDF 並標記為已送出", type="primary", use_container_width=True):
        # 驗證
        errors = []
        for ok, msg in [
            validators.validate_required(applicant, "申請人／單位"),
            validators.validate_required(name, "個案姓名"),
            validators.validate_id_number(id_number),
            validators.validate_roc_date(birth_date),
            validators.validate_phone(contact_phone),
        ]:
            if not ok:
                errors.append(msg)
        if not (new_mouth or any(u.get("kind") == "mouth_photo" for u in uploads)):
            errors.append("至少要上傳一張口腔照片")

        if errors:
            for e in errors:
                st.error(e)
        else:
            case_id = storage.upsert_application(
                app_id, user, name, payload_out, status="submitted"
            )
            new_uploads = _save_uploads(case_id)
            all_uploads = uploads + new_uploads
            storage.upsert_application(
                case_id, user, name, payload_out,
                status="submitted", uploads=all_uploads,
            )
            try:
                photos = [storage.download_file(u["path"]) for u in all_uploads
                          if u["kind"] == "mouth_photo"]
                doc_files = [
                    (u["filename"], storage.download_file(u["path"]), u["kind"])
                    for u in all_uploads if u["kind"] in ("id_doc", "vpn_doc")
                ]
                pdf_bytes = pdf_builder.build_pdf(payload_out, photos, doc_files)
                # 存到 session_state 讓 rerun 後下載按鈕還在
                st.session_state["_last_pdf"] = {
                    "bytes": pdf_bytes,
                    "name": name,
                    "case_id": case_id,
                }
                st.session_state["current_case_id"] = case_id
                st.session_state["_saved_msg"] = "已標記為「已送出」。請手動寄到 dental@cda.org.tw"
                st.query_params["id"] = case_id
                st.rerun()
            except NotImplementedError as e:
                st.warning(f"⚠️ {e}")
                st.info("案件已存到資料庫（狀態：已送出），等 PDF 範本就位後即可重印。")

with c3:
    if existing and st.button("🗑️ 刪除此案件", use_container_width=True):
        storage.delete_application(app_id)
        st.session_state.pop("current_case_id", None)
        st.session_state.pop("_last_pdf", None)
        st.session_state["_saved_msg"] = "案件已刪除"
        st.query_params.clear()
        st.rerun()
