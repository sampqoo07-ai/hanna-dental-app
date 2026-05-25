"""Supabase 資料層：申請案件 CRUD + 檔案上傳。

Supabase 端要先建好（用 SQL editor 跑一次）：

    create table applications (
      id uuid primary key default gen_random_uuid(),
      created_by text not null,
      created_at timestamptz default now(),
      updated_at timestamptz default now(),
      status text default 'draft',           -- draft / submitted / followup / approved / rejected
      case_name text,
      payload jsonb not null,                -- 表單全部欄位
      uploads jsonb default '[]'::jsonb      -- [{kind, path, filename}]
    );

    -- Storage：建一個 private bucket 叫 dental-uploads
"""
from __future__ import annotations
from typing import Any
import uuid
import streamlit as st
from supabase import create_client, Client


# 狀態對照表（顯示用）
STATUS_LABELS = {
    "draft":     "📝 草稿",
    "submitted": "📤 已送出",
    "followup":  "🔄 補件中",
    "approved":  "✅ 已通過",
    "rejected":  "❌ 已退回",
}


def status_label(s: str | None) -> str:
    return STATUS_LABELS.get(s or "", s or "")


@st.cache_resource
def _client() -> Client:
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])


def _bucket() -> str:
    return st.secrets["supabase"]["bucket"]


def list_applications(user: str, mine_only: bool = True) -> list[dict[str, Any]]:
    q = _client().table("applications").select("*").order("updated_at", desc=True)
    if mine_only:
        q = q.eq("created_by", user)
    return q.execute().data or []


def get_application(app_id: str) -> dict[str, Any] | None:
    res = _client().table("applications").select("*").eq("id", app_id).execute()
    return (res.data or [None])[0]


def upsert_application(
    app_id: str | None,
    user: str,
    case_name: str,
    payload: dict,
    status: str = "draft",
    uploads: list[dict] | None = None,
) -> str:
    row = {
        "case_name": case_name,
        "payload": payload,
        "status": status,
    }
    if uploads is not None:
        row["uploads"] = uploads

    table = _client().table("applications")
    if app_id:
        # 更新既有案件時不動 created_by，保留原始建立者
        table.update(row).eq("id", app_id).execute()
        return app_id
    # 新建才寫 created_by
    row["created_by"] = user
    new_id = str(uuid.uuid4())
    row["id"] = new_id
    table.insert(row).execute()
    return new_id


_MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "pdf": "application/pdf",
    "heic": "image/heic",
}


def upload_file(app_id: str, kind: str, filename: str, data: bytes) -> dict:
    """kind: mouth_photo / id_doc / vpn_doc. 回傳 {kind, path, filename}。

    失敗會把 Supabase 回的 message/statusCode 包進 RuntimeError raise 出來，
    讓上層能顯示給使用者看（Streamlit Cloud 預設會把未處理錯誤 redact 掉）。
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    path = f"{app_id}/{kind}/{uuid.uuid4().hex}_{filename}"
    try:
        _client().storage.from_(_bucket()).upload(
            path, data, {"content-type": mime, "upsert": "true"}
        )
    except Exception as e:
        msg = getattr(e, "message", None) or str(e)
        status = getattr(e, "code", None) or getattr(e, "status_code", None) or "?"
        size_mb = len(data) / 1024 / 1024
        raise RuntimeError(
            f"上傳「{filename}」失敗（{size_mb:.1f} MB, {mime}, status={status}）：{msg}"
        ) from e
    return {"kind": kind, "path": path, "filename": filename}


def download_file(path: str) -> bytes:
    return _client().storage.from_(_bucket()).download(path)


def delete_application(app_id: str) -> None:
    _client().table("applications").delete().eq("id", app_id).execute()
