"""SMTP 寄信：把生成好的 PDF 寄到公會信箱。

需要 st.secrets 設定 [smtp] sender / app_password。Gmail 用 app password
（Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼）。
"""
from __future__ import annotations
import smtplib
import socket
from email.message import EmailMessage

import streamlit as st


RECIPIENT = "dental@cda.org.tw"
SUBJECT = "好所宅診所居家牙醫申請"


class EmailSendError(Exception):
    """寄信失敗時包裝成人類看得懂的訊息。

    .user_message：直接顯示給使用者的中文說明
    .hint：建議下一步動作
    .raw：原始錯誤（traceback 用），給工程除錯
    """

    def __init__(self, user_message: str, hint: str, raw: Exception | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.hint = hint
        self.raw = raw


def active_recipient() -> str:
    """實際會寄到的地址：secrets [smtp].test_recipient 有設就用那個，否則寄公會。"""
    try:
        override = st.secrets["smtp"].get("test_recipient")
    except Exception:
        override = None
    return (override or "").strip() or RECIPIENT


def send_application_pdf(case_name: str, pdf_bytes: bytes) -> None:
    """寄一封 PDF 附件信給公會（或 test_recipient）。失敗會 raise EmailSendError。"""
    cfg = st.secrets["smtp"]
    sender = cfg["sender"]
    app_password = cfg["app_password"]
    to_addr = active_recipient()

    msg = EmailMessage()
    msg["Subject"] = SUBJECT + (" [TEST]" if to_addr != RECIPIENT else "")
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(
        f"您好，\n\n附件為居家牙醫醫療需求服務申請，個案：{case_name}。\n"
        "煩請審閱，感謝。\n\n好所宅診所 敬上"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"居家牙醫申請_{case_name}.pdf",
    )

    size_mb = len(pdf_bytes) / 1024 / 1024
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(sender, app_password)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise EmailSendError(
            f"Gmail 拒絕登入（{sender}）。",
            "通常是應用程式密碼被改過或撤銷。請到 "
            "Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼 "
            "重新產生一組 16 碼密碼，貼到 Streamlit Cloud Secrets 的 "
            "[smtp].app_password。",
            raw=e,
        ) from e
    except smtplib.SMTPRecipientsRefused as e:
        raise EmailSendError(
            f"收件人 {to_addr} 被 Gmail 拒收。",
            "通常是地址打錯或對方信箱關閉。確認 [smtp] 設定的收件人正確。",
            raw=e,
        ) from e
    except smtplib.SMTPSenderRefused as e:
        raise EmailSendError(
            f"寄件人 {sender} 被 Gmail 拒絕。",
            "可能是帳戶被暫時鎖定（例如異常活動）。先到 Gmail 網頁登入"
            "一次確認沒有警告，再試一次。",
            raw=e,
        ) from e
    except smtplib.SMTPDataError as e:
        # 552 = 信件太大；其他 5xx 多半是內容被擋
        code = getattr(e, "smtp_code", "?")
        if code == 552 or "size" in str(e).lower():
            raise EmailSendError(
                f"附件超過 Gmail 25 MB 上限（這封大約 {size_mb:.1f} MB）。",
                "通常是上傳的口腔照片或 VPN 文件原圖太大。回上一頁刪掉"
                "幾張、用較小的照片，再重新產 PDF。",
                raw=e,
            ) from e
        raise EmailSendError(
            f"Gmail 回報內容錯誤（SMTP {code}）。",
            "內容可能被當作可疑信件。換個說法或縮減附件後再試。",
            raw=e,
        ) from e
    except (socket.gaierror, smtplib.SMTPConnectError) as e:
        raise EmailSendError(
            "連不上 Gmail 伺服器。",
            "通常是網路問題：換個 wifi、關掉 VPN、或稍等一分鐘重試。"
            "公司／醫院網路有時會擋 SMTP（port 465）。",
            raw=e,
        ) from e
    except TimeoutError as e:
        raise EmailSendError(
            "寄信逾時。",
            "網路太慢或附件太大（30 秒內傳不完）。換個網路或縮小附件再試。",
            raw=e,
        ) from e
    except smtplib.SMTPException as e:
        raise EmailSendError(
            f"SMTP 異常：{e}",
            "如果反覆失敗，截圖訊息給 Hanna。",
            raw=e,
        ) from e


def is_test_mode() -> bool:
    return active_recipient() != RECIPIENT
