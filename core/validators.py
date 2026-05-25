"""欄位驗證。每個函式回傳 (ok, 錯誤訊息)。"""
from __future__ import annotations
import re
from datetime import date

_ID_RE = re.compile(r"^[A-Z][12]\d{8}$")
_PHONE_RE = re.compile(r"^(0\d{1,3}-?\d{6,8}|09\d{2}-?\d{3}-?\d{3})$")
_ROC_DATE_RE = re.compile(r"^\d{7}$")  # 民國 YYYMMDD，如 0650101


def validate_id_number(s: str) -> tuple[bool, str]:
    s = (s or "").strip().upper()
    if not s:
        return False, "身分證字號必填"
    if not _ID_RE.match(s):
        return False, "身分證字號格式錯誤（例：A123456789）"
    # 檢查碼驗證
    letter_map = "ABCDEFGHJKLMNPQRSTUVXYWZIO"
    n = letter_map.index(s[0]) + 10
    nums = [n // 10, n % 10] + [int(c) for c in s[1:]]
    weights = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
    if sum(a * b for a, b in zip(nums, weights)) % 10 != 0:
        return False, "身分證字號檢查碼不符"
    return True, ""


def validate_phone(s: str) -> tuple[bool, str]:
    s = (s or "").strip()
    if not s:
        return False, "電話必填"
    if not _PHONE_RE.match(s):
        return False, "電話格式錯誤（例：02-12345678 或 0912-345-678）"
    return True, ""


def validate_roc_date(s: str) -> tuple[bool, str]:
    s = (s or "").strip()
    if not s:
        return False, "出生日期必填"
    if not _ROC_DATE_RE.match(s):
        return False, "民國日期格式錯誤（例：0650101）"
    year, month, day = int(s[:3]), int(s[3:5]), int(s[5:])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return False, "民國日期月日不合理"
    return True, ""


def validate_required(value, label: str) -> tuple[bool, str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return False, f"{label}必填"
    return True, ""


def parse_roc_date(s: str) -> date | None:
    """民國 YYYMMDD 7 碼字串 → datetime.date；格式錯回 None。"""
    s = (s or "").strip()
    if not _ROC_DATE_RE.match(s):
        return None
    try:
        return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    except ValueError:
        return None


def calc_age(birth: date, today: date | None = None) -> int:
    """西元生日 → 年齡（足歲）。"""
    today = today or date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
