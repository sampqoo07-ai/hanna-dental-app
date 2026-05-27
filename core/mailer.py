"""SMTP 寄信：把生成好的 PDF 寄到公會信箱。

需要 st.secrets 設定 [smtp] sender / app_password。Gmail 用 app password
（Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼）。
"""
from __future__ import annotations
import smtplib
from email.message import EmailMessage

import streamlit as st


RECIPIENT = "dental@cda.org.tw"
SUBJECT = "好所宅診所居家牙醫申請"


def send_application_pdf(case_name: str, pdf_bytes: bytes) -> None:
    """寄一封 PDF 附件信給公會。失敗會 raise。"""
    cfg = st.secrets["smtp"]
    sender = cfg["sender"]
    app_password = cfg["app_password"]

    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = sender
    msg["To"] = RECIPIENT
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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(sender, app_password)
        s.send_message(msg)
