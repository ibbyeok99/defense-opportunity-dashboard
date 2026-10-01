"""검증된 로컬 카드 아이콘만 읽는다. PNG 원본과 데이터는 수정하지 않는다."""

import base64
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


def procurement_icon_path(procurement_type: str) -> Path | None:
    """유형별 고정 파일만 연결한다. 파일 누락 시 화면은 유형 글자를 유지한다."""
    name = PROCUREMENT_ICON_FILES.get(procurement_type)
    if not name:
        return None
    path = ICON_DIRECTORY / name
    return path if path.is_file() else None


def procurement_icon_html(procurement_type: str) -> str | None:
    """native image에는 alt/title 지정 API가 없어 이름·hover 설명만 작은 HTML로 제공한다."""
    path = procurement_icon_path(procurement_type)
    if path is None:
        return None
    label = escape(procurement_type, quote=True)
    encoded = _encoded_icon(path.name, path.stat().st_mtime_ns)
    return (f'<img src="data:image/png;base64,{encoded}" width="40" height="40" '
            f'alt="{label}" title="조달 유형: {label}" style="display:block" />')
