"""검증된 로컬 카드 아이콘만 읽는다. PNG 원본과 데이터는 수정하지 않는다."""

import base64
from PIL import Image
from html import escape
from functools import lru_cache
from pathlib import Path

ICON_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "icons"
CARD_ICON_FILES = {
    "찾은 공고": "notice_found.png",
    "마감 7일 안": "notice_deadline.png",
    "회사 조건 충족": "notice_company_match.png",
    "▲ 원문 확인 필요": "notice_review.png",
    "원문 확인 필요": "notice_review.png",
    "참가업체 수 (중앙값)": "participants.png",
    "단독입찰 비율": "single_bid.png",
    "상위 3개 업체 점유": "supplier_share.png",
    "계약 건수": "contracts.png",
}
PROCUREMENT_ICON_FILES = {
    "물품": "goods.png",
    "용역": "services.png",
    "공사": "construction.png",
    "외자": "foreign.png",
}
MARKET_ICON_FILES = {
    "공고 수": "market_notices.png",
    "개찰 수": "market_openings.png",
    "계약 건수": "market_contracts.png",
    "단독입찰 비율": "market_single_bid.png",
}
CARD_SYMBOLS = {
    "찾은 공고": "campaign",
    "공고 수": "campaign",
    "개찰 수": "gavel",
    "마감 7일 안": "schedule",
    "회사 조건 충족": "business",
    "▲ 원문 확인 필요": "description",
    "원문 확인 필요": "description",
}


@lru_cache(maxsize=32)
def _encoded_icon(name: str, modified_ns: int) -> str:
    # name은 위의 고정 파일 목록에서만 전달한다. 수정 시각은 캐시 갱신 키다.
    return base64.b64encode((ICON_DIRECTORY / name).read_bytes()).decode("ascii")


def card_icon_html(label: str, *, prefix: str | None = None) -> str | None:
    name = (MARKET_ICON_FILES if prefix == "ov" else CARD_ICON_FILES).get(label)
    if not name:
        return None
    path = ICON_DIRECTORY / name
    if not path.is_file():
        return None
    encoded = _encoded_icon(name, path.stat().st_mtime_ns)
    # 원본의 투명 여백을 CSS 확대만으로 줄인다. 이미지 바이트는 변경하지 않는다.
    return ("<div class='dashboard-kpi-icon' aria-hidden='true'>"
            f"<img src='data:image/png;base64,{encoded}' alt='' /></div>")


def header_background_url() -> str | None:
    """장식용 상단 이미지. 고정 파일만 읽고 누락 시 기존 단색 헤더를 유지한다."""
    path = ICON_DIRECTORY / "background.png"
    if not path.is_file():
        return None
    encoded = _encoded_icon(path.name, path.stat().st_mtime_ns)
    return f"data:image/png;base64,{encoded}"


def sidebar_brand():
    """원본 흰색 로고를 native 이미지로 표시하고 투명 여백만 화면에서 숨긴다."""
    import streamlit as st
    path = ICON_DIRECTORY / "logo_white_sb.png"
    if not path.is_file():
        return
    with Image.open(path) as image:
        # 낮은 알파의 고립 픽셀은 로고 바깥 여백 계산에 포함하지 않는다.
        bbox = (image.getchannel("A").point(lambda alpha: 255 if alpha >= 200 else 0).getbbox()
                if "A" in image.getbands() else None)
        left, top, right, bottom = bbox or (0, 0, *image.size)
        width, height = right - left, bottom - top
        crop_style = ("<style>.st-key-sidebar_brand {"
                      f"--sidebar-logo-aspect:{width}/{height};--sidebar-logo-width:{image.width / width * 100:.6f}%;"
                      f"--sidebar-logo-left:{-left / width * 100:.6f}%;--sidebar-logo-top:{-top / height * 100:.6f}%;"
                      "}</style>")
    st.html(crop_style)
    with st.sidebar.container(key="sidebar_brand", width=224):
        st.image(str(path), width="stretch")


def procurement_icon_path(procurement_type: str) -> Path | None:
    """유형별 고정 파일만 연결한다. 파일 누락 시 화면은 유형 글자를 유지한다."""
    name = PROCUREMENT_ICON_FILES.get(procurement_type)
    if not name:
        return None
    path = ICON_DIRECTORY / name
    return path if path.is_file() else None


def procurement_icon_html(procurement_type: str, *, with_tooltip: bool = False) -> str | None:
    """유형 이름·hover 설명만 HTML로 제공한다. with_tooltip은 즉시 표시·키보드 포커스를 지원한다."""
    path = procurement_icon_path(procurement_type)
    if path is None:
        return None
    label = escape(procurement_type, quote=True)
    encoded = _encoded_icon(path.name, path.stat().st_mtime_ns)
    if with_tooltip:
        tip_id = f"procurement-type-{path.stem}"
        return (f'<span class="procurement-type-hover" tabindex="0" role="img" '
                f'aria-label="조달 유형: {label}" aria-describedby="{tip_id}">'
                f'<img src="data:image/png;base64,{encoded}" width="40" height="40" '
                'alt="" style="display:block" />'
                f'<span class="procurement-type-tooltip" id="{tip_id}" role="tooltip">{label}</span></span>')
    return (f'<img src="data:image/png;base64,{encoded}" width="40" height="40" '
            f'alt="{label}" title="조달 유형: {label}" style="display:block" />')
