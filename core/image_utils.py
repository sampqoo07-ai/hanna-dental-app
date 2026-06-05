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


MAX_DIM = 1600         # 口腔照長邊像素上限
JPEG_QUALITY = 82      # 對口腔照足夠清楚，又比原圖小很多

# 證明文件（VPN／身障手冊／身分證）走另一組參數：保留文字細節
DOC_MAX_DIM = 2400     # 文件長邊像素上限：A4 300dpi ≈ 2480px，這裡走 2400 已很清楚
DOC_JPEG_QUALITY = 92  # 高品質保留文字邊緣


def _normalize(data: bytes, filename: str, max_dim: int, quality: int) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)

    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    return buf.getvalue(), f"{base}.jpg"


def normalize_photo(data: bytes, filename: str) -> tuple[bytes, str]:
    """口腔照片用：讀任意格式（含 HEIC）→ 轉正 → 縮到 1600px → JPEG bytes。"""
    return _normalize(data, filename, MAX_DIM, JPEG_QUALITY)


def normalize_document(data: bytes, filename: str) -> tuple[bytes, str]:
    """證明文件用（VPN／身障手冊／身分證）：縮到 2400px、quality 92，保留文字細節。"""
    return _normalize(data, filename, DOC_MAX_DIM, DOC_JPEG_QUALITY)
