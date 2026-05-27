"""照片預處理：HEIC → JPEG、自動轉正、縮到上限尺寸。

iPhone 預設拍 HEIC，pdf_builder + PIL 開不了；同時原圖 5-10MB 上傳很慢
也讓 PDF 變大。所有口腔／文件照片上傳前先過這層。
"""
from __future__ import annotations
import io

from PIL import Image, ImageOps

# 註冊 HEIF 解碼器，PIL 之後就能 open .heic
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


MAX_DIM = 1600         # 長邊像素上限
JPEG_QUALITY = 82      # 對掃描／口腔照足夠清楚，又比原圖小很多


def normalize_photo(data: bytes, filename: str) -> tuple[bytes, str]:
    """讀任意格式（含 HEIC）→ 轉正 → 縮圖 → JPEG bytes。

    回傳 (新 bytes, 新檔名)，副檔名統一成 .jpg。
    """
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)

    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    return buf.getvalue(), f"{base}.jpg"
