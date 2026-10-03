"""화면 내용을 A4 PDF로 내보내기 — matplotlib만 사용(추가 설치 없음).

한글 글꼴은 시스템에서 찾는다(맑은 고딕 → 나눔고딕 → Noto Sans CJK). 서버에 한글 글꼴이 없으면
글자가 네모로 나오므로 배포 서버에는 나눔고딕 등을 설치해야 한다.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
PAGE_W, PAGE_H = 8.27, 11.69  # A4, 인치
MARGIN = 0.6
BODY_W = PAGE_W - 2 * MARGIN
FONT_CANDIDATES = ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic"]
ACCENT = "#52647A"
MUTED = "#667085"


def korean_font() -> str | None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in FONT_CANDIDATES if n in names), None)


def _text_width(s: str, size: float) -> float:
    """대략적인 글자 폭(인치). 한글·전각은 글자 크기만큼, 영숫자는 절반 정도."""
    units = sum(1.0 if ord(ch) > 0x2E80 else 0.55 for ch in s)
    return units * size / 72


def _wrap(s: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for para in str(s).split("\n"):
        line = ""
        for ch in para:
            if _text_width(line + ch, size) > width and line:
                lines.append(line)
                line = ch.lstrip()
            else:
                line += ch
        lines.append(line)
    return lines


def _cell(v) -> str:
    """표 칸 글자: 빈 값은 빈칸, 정수로 떨어지는 실수는 천 단위 쉼표 정수."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{int(v):,}" if v.is_integer() else f"{v:,.1f}"
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}"
    return str(v)


def _fit(s, size: float, width: float) -> str:
    s = _cell(s)
    if _text_width(s, size) <= width:
        return s
    while s and _text_width(s + "…", size) > width:
        s = s[:-1]
    return s + "…"


class Report:
    """위에서 아래로 쌓는 간단한 보고서. 넘치면 새 쪽으로 넘어간다."""

    def __init__(self, title: str, subtitle: str = "", footer: str = ""):
        self.title, self.subtitle, self.footer = title, subtitle, footer
        self.blocks: list[tuple] = []

    def heading(self, text: str):
        self.blocks.append(("heading", text))
        return self

    def para(self, text: str, size: float = 9, color: str = "#1F2418"):
        self.blocks.append(("para", text, size, color))
        return self

    def kv(self, pairs: list[tuple[str, str]]):
        self.blocks.append(("kv", pairs))
        return self

    def table(self, df: pd.DataFrame, max_rows: int = 40, note: str = ""):
        self.blocks.append(("table", df.head(max_rows), note, len(df)))
        return self

    def chart(self, draw: Callable[[plt.Axes], None], height: float = 2.6):
        self.blocks.append(("chart", draw, height))
        return self

    # ---- 그리기 ----
    def build(self) -> bytes:
        font = korean_font()
        rc = {"font.family": font} if font else {}
        buf = io.BytesIO()
        with plt.rc_context({**rc, "axes.unicode_minus": False}), PdfPages(buf) as pdf:
            self._pdf, self._page_no, self._fig = pdf, 0, None
            self._new_page(first=True)
            for block in self.blocks:
                getattr(self, "_draw_" + block[0])(*block[1:])
            self._finish_page()
        return buf.getvalue()

    def _new_page(self, first: bool = False):
        if self._fig is not None:
            self._finish_page()
        self._page_no += 1
        self._fig = plt.figure(figsize=(PAGE_W, PAGE_H))
        self._y = PAGE_H - MARGIN
        if first:
            self._put(self.title, 17, weight="bold", color=ACCENT)
            self._y -= 0.34
            if self.subtitle:
                for line in _wrap(self.subtitle, 8.5, BODY_W):
                    self._put(line, 8.5, color=MUTED)
                    self._y -= 0.17
            self._y -= 0.1
            self._fig.add_artist(plt.Line2D([MARGIN / PAGE_W, 1 - MARGIN / PAGE_W], [self._y / PAGE_H] * 2,
                                            color=ACCENT, linewidth=1.2))
            self._y -= 0.25

    def _finish_page(self):
        stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
        self._fig.text(MARGIN / PAGE_W, 0.35 / PAGE_H, f"{self.footer}  ·  생성 {stamp}", fontsize=6.5, color=MUTED)
        self._fig.text(1 - MARGIN / PAGE_W, 0.35 / PAGE_H, f"{self._page_no}", fontsize=7, color=MUTED, ha="right")
        self._pdf.savefig(self._fig)
        plt.close(self._fig)
        self._fig = None

    def _need(self, h: float):
        if self._y - h < MARGIN + 0.3:
            self._new_page()

    def _put(self, text: str, size: float, x: float = MARGIN, **kw):
        self._fig.text(x / PAGE_W, self._y / PAGE_H, text, fontsize=size, va="top", **kw)

    def _draw_heading(self, text: str):
        self._need(0.6)
        self._y -= 0.08
        self._put(text, 12, weight="bold")
        self._y -= 0.3

    def _draw_para(self, text: str, size: float, color: str):
        for line in _wrap(text, size, BODY_W):
            self._need(size / 72 * 1.5)
            self._put(line, size, color=color)
            self._y -= size / 72 * 1.5
        self._y -= 0.08

    def _draw_kv(self, pairs):
        cols, cell_w = 3, BODY_W / 3
        for i in range(0, len(pairs), cols):
            self._need(0.5)
            for j, (k, v) in enumerate(pairs[i:i + cols]):
                x = MARGIN + j * cell_w
                self._put(_fit(k, 7.5, cell_w - 0.1), 7.5, x=x, color=MUTED)
                self._fig.text(x / PAGE_W, (self._y - 0.16) / PAGE_H, _fit(v, 11, cell_w - 0.1), fontsize=11,
                               va="top", weight="bold")
            self._y -= 0.5
        self._y -= 0.05

    def _draw_table(self, df: pd.DataFrame, note: str, total: int):
        size, row_h = 7, 0.2
        cols = list(df.columns)
        if not cols:
            return
        lengths = [max([_text_width(str(c), size)] + [_text_width(_cell(v), size) for v in df[c].head(40)])
                   for c in cols]
        lengths = [min(max(w, 0.45), 3.2) for w in lengths]
        scale = BODY_W / sum(lengths)
        widths = [w * scale for w in lengths]

        def header():
            self._need(row_h * 2)
            x = MARGIN
            for c, w in zip(cols, widths):
                self._put(_fit(c, size, w - 0.06), size, x=x, weight="bold", color=ACCENT)
                x += w
            self._y -= row_h
            self._fig.add_artist(plt.Line2D([MARGIN / PAGE_W, 1 - MARGIN / PAGE_W], [(self._y + 0.04) / PAGE_H] * 2,
                                            color="#D4DAE2", linewidth=0.6))

        header()
        for _, row in df.iterrows():
            if self._y - row_h < MARGIN + 0.3:
                self._new_page()
                header()
            x = MARGIN
            for c, w in zip(cols, widths):
                self._put(_fit(row[c], size, w - 0.06), size, x=x)
                x += w
            self._y -= row_h
        tail = f"상위 {len(df):,}행 표시 (전체 {total:,}행)" if total > len(df) else ""
        memo = "  ".join(t for t in (note, tail) if t)
        if memo:
            self._draw_para(memo, 7, MUTED)
        self._y -= 0.1

    def _draw_chart(self, draw, height: float):
        self._need(height + 0.6)
        bottom = self._y - height
        ax = self._fig.add_axes([(MARGIN + 0.45) / PAGE_W, bottom / PAGE_H, (BODY_W - 0.55) / PAGE_W,
                                 (height - 0.25) / PAGE_H])
        draw(ax)
        ax.tick_params(labelsize=7)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if ax.get_legend():
            ax.legend(fontsize=7, frameon=False)
        # 축 이름·눈금은 axes 밖으로 나온다. 실제 글자 끝 아래에 다음 표를 배치한다.
        self._fig.canvas.draw()
        bounds = ax.get_tightbbox(self._fig.canvas.get_renderer()).transformed(self._fig.dpi_scale_trans.inverted())
        self._y = min(bottom - 0.3, bounds.y0 - 0.16)
