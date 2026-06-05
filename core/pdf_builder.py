"""把個案資料 overlay 到公會空白 PDF 上，再 append 一頁口腔照片。

策略：
  1. reportlab 在記憶體生成一個 overlay PDF（透明背景，只有文字）
  2. pypdf 把 overlay 蓋到 `official form.pdf` 第 1 頁上
  3. 把照片塞到第 2 頁（公會原本是「個案口腔狀況」附頁）
  4. 回傳 PDF bytes

中文字體：用 reportlab 內建的 CID font `STSong-Light`，零依賴。
A4 = 595 x 842 pt。pdfplumber 量出來的 top → reportlab 用的 y = 842 - top。

⚠️ FIELD_MAP 的座標是首次估算值。請第一次跑出 PDF 比對位置，再回來調這張表。
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# --- 字體：標楷體優先 ---
# 1. 部署到 Streamlit Cloud 時要把字體放到 assets/fonts/kaiti.ttf
# 2. 本機可用 Microsoft Word 內附的 Kaiti.ttf
# 3. 都找不到才退回 reportlab 內建的 STSong-Light（宋體）
def _register_font() -> str:
    bundled = Path(__file__).parent.parent / "assets" / "fonts" / "kaiti.ttf"
    word_kaiti = Path("/Applications/Microsoft Word.app/Contents/Resources/Fonts/Kaiti.ttf")
    for candidate in (bundled, word_kaiti):
        if candidate.exists():
            try:
                pdfmetrics.registerFont(TTFont("Kaiti", str(candidate)))
                return "Kaiti"
            except Exception:
                continue
    # 後備：reportlab 內建 CJK CID 字體
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


FONT = _register_font()

# --- 範本路徑 ---
TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "templates" / "official_form.pdf"

# --- 欄位座標表（reportlab 座標：y 從下往上算）---
# A4 高 842，pdfplumber 量到的 top 換成 reportlab y = 842 - top - 字體高度微調
# 第一次跑完比對成品，再來這裡微調 x/y
H = 842
PAD = 12  # 字體垂直微調

FIELD_MAP = {
    # 聯絡人區 (新範本 y_top=150)
    "contact_name":   (105, H - 190, 12),
    "contact_phone":  (355, H - 190, 12),
    # 個案表格 row1 (新 y_top=253)
    "name":           (60,  H - 304, 12),
    "disability":     (185, H - 304, 12),
    "age":            (250, H - 304, 12),
    "address":        (320, H - 304, 12),
    # 個案表格 row2 (新 y_top=339)
    "id_number":      (135, H - 351, 12),
    "birth_date":     (370, H - 351, 12),
    # 健康狀況大區塊（框 top=618.3 / bottom=716.8 / width=408.1）
    # 起點 y 對齊框內頂端（first baseline ≈ top+14）；字多時走 _fit_text 自動縮字級
    "health_status":  (147, H - 632, 12),
}

# 健康狀況框內可用區域（避免寫到框外被裁掉）
HEALTH_STATUS_MAX_WIDTH = 400   # 框寬 408，保留兩側 padding
HEALTH_STATUS_MAX_HEIGHT = 80   # 框高 98.5，保留上下 padding 不壓到框邊

# 身份別勾選：新範本 □_y_top=374，5 個□ x0 實測
IDENTITY_CHECKBOX_X = {
    "一般":       133,
    "低收入戶":   175,
    "中低收入戶": 240,
    "身障手冊":   318,
    "其他":       384,
}
IDENTITY_Y = H - 384

# 個案申請資格（新範本 □ 都在 x=40.0）
QUALIFICATION_X = 42
QUALIFICATION_Y = {
    1: H - 460,  # 特定身心障礙者，新 y_top=450
    2: H - 484,  # 失能老人，新 y_top=474
}

# 口腔需求勾選（新 □ 都在 x=148.3，y_top 分別 542.7 / 560.7 / 584.7）
NEEDS_CHECKBOX_Y = {
    "疑似牙齦出血紅腫等異常情況": H - 553,
    "疑有口腔衛生狀況不佳情況":   H - 571,
    "其他":                       H - 595,
}
NEEDS_CHECKBOX_X = 150

# 外出能力 (新 y_top=406，□否=213.6、□是=245.6)
OUTING_Y = H - 416
OUTING_X = {"否": 216, "是": 248}


def _checkmark(c: canvas.Canvas, x: float, y: float, size: int = 10):
    """在 (x, y) 畫一個 V 形勾選，不依賴字體。

    size ≈ □ 的邊長。三點折線：左上往右下到底點，再往右上勾起。
    """
    c.saveState()
    c.setLineWidth(2.0)
    c.setLineCap(1)   # 圓頭，看起來比較像手寫
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(x,             y + size * 0.45)
    p.lineTo(x + size * 0.4, y + size * 0.05)
    p.lineTo(x + size * 1.0, y + size * 0.85)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def _wrap_lines(text: str, max_width: float, size: int, font: str = FONT) -> list[str]:
    """把文字按字寬切成多行。"""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    lines: list[str] = []
    line = ""
    for ch in text:
        if ch == "\n":
            lines.append(line)
            line = ""
            continue
        if stringWidth(line + ch, font, size) > max_width:
            lines.append(line)
            line = ch
        else:
            line += ch
    lines.append(line)
    return lines


def _wrap_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, size: int):
    """簡易自動換行（按字寬切）。"""
    line_h = size * 1.3
    c.setFont(FONT, size)
    cur_y = y
    for line in _wrap_lines(text, max_width, size):
        c.drawString(x, cur_y, line)
        cur_y -= line_h


def _fit_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    max_width: float,
    max_height: float,
    base_size: int = 12,
    min_size: int = 8,
    line_ratio: float = 1.15,
):
    """在固定方框內自動縮字級，把文字塞進 max_width × max_height。

    y_top 是第一行 baseline 的 y 座標（reportlab 由下往上算）。
    從 base_size 往下試到 min_size；若 min_size 還是塞不下，最後一行尾部加 …。
    """
    for size in range(base_size, min_size - 1, -1):
        lines = _wrap_lines(text, max_width, size)
        line_h = size * line_ratio
        if len(lines) * line_h <= max_height:
            break
    else:
        # 連最小字級都塞不下：截斷並加省略號
        size = min_size
        line_h = size * line_ratio
        max_lines = max(1, int(max_height // line_h))
        lines = _wrap_lines(text, max_width, size)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            tail = lines[-1]
            from reportlab.pdfbase.pdfmetrics import stringWidth
            while tail and stringWidth(tail + "…", FONT, size) > max_width:
                tail = tail[:-1]
            lines[-1] = tail + "…"

    c.setFont(FONT, size)
    cur_y = y_top
    for line in lines:
        c.drawString(x, cur_y, line)
        cur_y -= line_h


def _build_overlay(payload: dict) -> bytes:
    """生成一個 1 頁的透明 PDF，把所有欄位文字放在指定座標。"""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # 純文字欄位
    for key, (x, y, size) in FIELD_MAP.items():
        val = payload.get(key, "")
        if not val:
            continue
        if key == "health_status":
            _fit_text(
                c, str(val), x, y,
                max_width=HEALTH_STATUS_MAX_WIDTH,
                max_height=HEALTH_STATUS_MAX_HEIGHT,
                base_size=size,
            )
        elif key == "address":
            _wrap_text(c, str(val), x, y, max_width=200, size=size)
        else:
            c.setFont(FONT, size)
            c.drawString(x, y, str(val))

    # 身份別勾選
    for ident in payload.get("identity", []) or []:
        if ident in IDENTITY_CHECKBOX_X:
            _checkmark(c, IDENTITY_CHECKBOX_X[ident], IDENTITY_Y)

    # 申請資格
    qual = payload.get("qualification")  # 1 or 2
    if qual in QUALIFICATION_Y:
        _checkmark(c, QUALIFICATION_X, QUALIFICATION_Y[qual])

    # 外出能力
    outing = payload.get("can_go_out")  # "是" / "否"
    if outing in OUTING_X:
        _checkmark(c, OUTING_X[outing], OUTING_Y)

    # 口腔需求
    for need in payload.get("needs", []) or []:
        if need in NEEDS_CHECKBOX_Y:
            _checkmark(c, NEEDS_CHECKBOX_X, NEEDS_CHECKBOX_Y[need])

    c.save()
    return buf.getvalue()


def _build_photo_overlay(photos: list[bytes]) -> bytes:
    """生成「照片 overlay」蓋在範本第 2 頁上：頂部標題列 + 下方 2x2 照片格。

    版面數字（單位 pt）：
      頁面寬 W=595，邊距 MARGIN=50，可用寬 495
      兩欄、欄間距 GUTTER=15 → 每格寬 240
      兩列、列間距 GUTTER=15 → 每格高 240（用方格，照片在格內置中）
    所有元素左邊都對齊 x=50，右邊都對齊 x=545。
    """
    from reportlab.lib.utils import ImageReader

    W = 595
    MARGIN = 50
    GUTTER = 15
    # 整體位移（標題＋分隔線＋網格一起平移）
    X_OFFSET = 5
    Y_OFFSET = 15
    GRID_LEFT = MARGIN + X_OFFSET
    GRID_RIGHT = W - MARGIN + X_OFFSET
    CELL_W = (GRID_RIGHT - GRID_LEFT - GUTTER) / 2   # 240
    CELL_H = 240

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # 頂部標題列
    title_y = H - 60 + Y_OFFSET
    c.setFont(FONT, 18)
    c.drawCentredString(W / 2 + X_OFFSET, title_y, "個案口腔照片")
    # 分隔線（左右對齊到網格邊界）
    c.setLineWidth(0.8)
    c.line(GRID_LEFT, title_y - 12, GRID_RIGHT, title_y - 12)

    if not photos:
        c.save()
        return buf.getvalue()

    # 2x2 網格起點：標題分隔線下方 20pt
    grid_top = title_y - 32
    cells = [
        (GRID_LEFT,                    grid_top - CELL_H),
        (GRID_LEFT + CELL_W + GUTTER,  grid_top - CELL_H),
        (GRID_LEFT,                    grid_top - 2 * CELL_H - GUTTER),
        (GRID_LEFT + CELL_W + GUTTER,  grid_top - 2 * CELL_H - GUTTER),
    ]

    side = int(min(CELL_W, CELL_H))  # 統一裁切成正方形
    for i, pb in enumerate(photos[:4]):
        cx, cy = cells[i]
        try:
            img = Image.open(BytesIO(pb))
            img = ImageOps.exif_transpose(img).convert("RGB")  # 依 EXIF 自動轉正
            # 置中裁切成正方形，再縮放到 side x side
            img = ImageOps.fit(img, (side, side), method=Image.LANCZOS, centering=(0.5, 0.5))
            ibuf = BytesIO()
            img.save(ibuf, format="JPEG", quality=85)
            ibuf.seek(0)
            # 格子內置中
            dx = cx + (CELL_W - side) / 2
            dy = cy + (CELL_H - side) / 2
            c.drawImage(ImageReader(ibuf), dx, dy, width=side, height=side, mask="auto")
        except Exception as e:
            c.setFont(FONT, 9)
            c.drawString(cx + 5, cy + CELL_H / 2, f"[載入失敗: {e}]")

    c.save()
    return buf.getvalue()


def _build_doc_page(filename: str, data: bytes, title: str) -> bytes | None:
    """把證明文件單張影像（JPG/PNG）做成一頁 PDF。回傳 PDF bytes，或 None（若不是影像）。

    不在這層砍像素──直接把原圖高解析度嵌進 PDF，只調整顯示尺寸（pt），
    這樣 VPN／身障手冊的文字在公會那邊放大看才會清楚。
    """
    from reportlab.lib.utils import ImageReader
    W = 595
    try:
        img = Image.open(BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return None
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(FONT, 16)
    c.drawCentredString(W / 2, H - 60, title)
    c.setLineWidth(0.8)
    c.line(50, H - 72, W - 50, H - 72)

    # 顯示框（pt）：A4 扣掉上方標題與下方註腳的空間
    max_w_pt, max_h_pt = W - 100, H - 130
    # 等比例縮到框內
    ratio = min(max_w_pt / img.width, max_h_pt / img.height)
    disp_w = img.width * ratio
    disp_h = img.height * ratio
    x = (W - disp_w) / 2
    y = (H - 100 - disp_h) / 2

    # 保留原始像素，只用 reportlab 的 width/height 控制顯示尺寸
    ibuf = BytesIO()
    img.save(ibuf, format="JPEG", quality=92)
    ibuf.seek(0)
    c.drawImage(ImageReader(ibuf), x, y, width=disp_w, height=disp_h)
    # 檔名小字註腳
    c.setFont(FONT, 8)
    c.drawCentredString(W / 2, 30, filename)
    c.save()
    return buf.getvalue()


def build_pdf(
    payload: dict,
    photo_bytes_list: list[bytes],
    doc_files: list[tuple[str, bytes, str]] | None = None,
) -> bytes:
    """主入口。回傳完整 PDF bytes。

    doc_files: [(filename, bytes, kind)]，kind 為 'id_doc' 或 'vpn_doc'。
      - 影像（JPG/PNG）：縮放後置中放在新一頁
      - PDF：直接 append 所有頁面
    """
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"找不到範本 PDF：{TEMPLATE_PATH}")

    overlay_bytes = _build_overlay(payload)
    overlay_reader = PdfReader(BytesIO(overlay_bytes))
    template_reader = PdfReader(str(TEMPLATE_PATH))

    writer = PdfWriter()
    # 第 1 頁：範本 p1 + 個案資料 overlay
    page1 = template_reader.pages[0]
    page1.merge_page(overlay_reader.pages[0])
    writer.add_page(page1)

    # 第 2 頁：口腔照片頁
    photo_pdf = PdfReader(BytesIO(_build_photo_overlay(photo_bytes_list)))
    writer.add_page(photo_pdf.pages[0])

    # 第 3 頁起：證明文件
    KIND_TITLE = {
        "id_doc":  "居家收案VPN／身障證明",
        "vpn_doc": "居家收案VPN／身障證明",
    }
    for filename, data, kind in (doc_files or []):
        title = KIND_TITLE.get(kind, "證明文件")
        if filename.lower().endswith(".pdf"):
            try:
                src = PdfReader(BytesIO(data))
                for p in src.pages:
                    writer.add_page(p)
            except Exception:
                continue
        else:
            page_bytes = _build_doc_page(filename, data, title)
            if page_bytes:
                writer.add_page(PdfReader(BytesIO(page_bytes)).pages[0])

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
