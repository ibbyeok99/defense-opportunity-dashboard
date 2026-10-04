"""숫자 표기와 화면 공통 문구·색."""

from __future__ import annotations

import math
import pandas as pd
from view.copy import review_label

# 참여 판단 배지 색 — service.eligibility.STATUS_OPTIONS와 같은 순서(가능·원문 확인·불가·미입력)
STATUS_COLORS = ["green", "orange", "red", "gray"]


def dday_text(d) -> str:
    if d is None or pd.isna(d):
        return "–"
    return "마감됨" if d < 0 else ("D-day" if d == 0 else f"D-{int(d)}")


def deadline_tone(d) -> str:
    """마감 상태의 공통 표시색. 날짜·정렬·참여 판단은 변경하지 않는다."""
    if d is None or pd.isna(d) or d < 0:
        return 'gray'
    return 'red' if d <= 7 else 'blue'

CONTRACT_AMOUNT_MESSAGES = {
    "no_linked_contracts": "해당 공고와 연결된 계약정보가 없습니다.",
    "missing_amount": "연결된 계약정보에 계약금액이 없습니다.",
}


def notice_status_label(status: str) -> str:
    """화면·내보내기 표시 문구. 판정 값·필터·저장값은 그대로 유지한다."""
    return "▲ 원문 확인 필요" if status == "▲ 원문 확인" else status


def company_empty_hint(has_profile: bool) -> str:
    """회사 조건의 미입력과 입력 후 일치 공고 없음을 구분한다."""
    if has_profile:
        return "입력한 회사 조건을 충족하는 공고가 없습니다. 검색 범위를 넓히거나 ‘모든 공고’에서 참여 판단과 원문을 확인하세요."
    return "왼쪽 ‘내 회사 조건’을 펼쳐 소재지·보유 면허를 입력하세요. 최종 참가 자격은 공고 원문에서 확인하세요."


def compact_filter_values(values, *, limit: int = 3, separator: str = ", ", empty_label: str = "미입력") -> str:
    """검색 조건 요약에서 선택값은 최대 limit개만 표시하고 나머지는 개수로 줄인다."""
    if values is None:
        items = []
    elif isinstance(values, str):
        items = [values.strip()] if values.strip() else []
    else:
        items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        return empty_label

    summary = separator.join(items[:limit])
    if len(items) > limit:
        summary += f" 외 {len(items) - limit}개"
    return summary


def notice_requirement_summary(license_state, license_values, region_state, region_values, *, license_review="미조회", region_review="미조회") -> str:
    """공고 목록용 면허·지역 요건. '미확인'을 '제한 없음'으로 축약하지 않는다."""

    def dimension(label, state, value, review, *, is_region=False):
        if review in {"공식 업종 제한 없음", "문서상 업종 제한 없음"}:
            return f"{label}·업종: 업종 제한 없음 · 기타 자격 원문 검토"
        if state == "조건없음":
            return f"{label} {'문서상 ' if review == '문서상 제한 없음' else ''}제한 없음" + (" · 원문 검토" if review == "문서상 제한 없음" else "")
        if state != "제한있음":
            if review == "문서 요건 후보·원문 검토" and isinstance(value, str) and value.strip():
                candidates = [v.strip() for v in value.split("|") if v.strip()]
                return f"{label} 문서 후보: {' · '.join(candidates[:2])}" + (f" 외 {len(candidates)-2}개" if len(candidates) > 2 else "") + " · 원문 검토"
            return f"{label} {review_label(review) if review != '미조회' else '미확인'}"

        values = [part.strip() for part in value.split("|") if part.strip()] if isinstance(value, str) else []
        if not values:
            return f"{label} 제한 있음 · 상세 미확인"
        if is_region:
            values = [region_display(item) for item in values]
        visible = " · ".join(values[:2])
        if len(values) > 2:
            visible += f" 외 {len(values) - 2}개"
        return f"{label} 제한: {visible}" + (" · 문서 원문 검토" if review == "문서 지역 조건 확인·원문 검토" else "")

    parts = (dimension("면허", license_state, license_values, license_review),
             dimension("지역", region_state, region_values, region_review, is_region=True))
    # 두 표시가 같은 상세 확인일 때만 합친다. 확인된 값·다른 검토 상태는 보존한다.
    return "상세 확인" if parts == ("면허 상세 확인", "지역 상세 확인") else " | ".join(parts)


def registered_requirement_summary(license_state, license_values, region_state, region_values, *,
                                   license_requires_review=False, region_requires_review=False) -> str:
    """일반 목록의 등록 조건만 표시. 미확인/문서 검토 값은 공란이며 상세·즐겨찾기에는 적용하지 않는다."""
    parts = []
    missing = {'', '-', '–', '미확인', 'UNKNOWN', 'NAN', 'NONE', 'NULL', '<NA>', '공고서참조', '공고문참조', '정보없음'}
    for label, state, raw, manual in (("면허", license_state, license_values, license_requires_review),
                                      ("지역", region_state, region_values, region_requires_review)):
        if not isinstance(state, str) or manual is pd.NA or manual:
            continue
        if state == '조건없음':
            parts.append(f'{label} 제한 없음')
        elif state == '제한있음' and isinstance(raw, str):
            values = [v.strip() for v in raw.split('|') if ''.join(v.split()).upper() not in missing]
            if values:
                shown = [region_display(v) for v in values] if label == '지역' else values
                text = ' · '.join(shown[:2]) + (f' 외 {len(shown)-2}개' if len(shown) > 2 else '')
                parts.append(f'{label} 제한: {text}')
    return ' | '.join(parts)

# EDA 인계 명세 4절: 화면 문구의 핵심(바꾸지 말 것)
CAVEATS = {
    "competition": "해당 조달유형·분류에서 관측된 과거 입찰·낙찰 결과입니다. 낙찰 가능성 예측이 아닙니다.",
    "contract_amount": "수집 시점에 확인되고 분석 규칙을 통과한 계약의 이번 반영 금액 합계입니다. 전체 시장규모가 아닙니다.",
    "new_supplier": "이 데이터에서 처음 확인된 업체라는 뜻입니다. 새로 창업했거나 처음 입찰한 기업이라는 뜻이 아닙니다.",
    "followup": "처음 개찰보다 나중에 확인된 재입찰·재공고 비율입니다. 유찰 확률이나 미래 위험 확률이 아닙니다.",
    "unknown_condition": "면허·지역 ‘미확인’은 조건이 없다는 뜻이 아닙니다. 공고 원문에서 확인해야 합니다.",
    "partial_year": "일부 기간만 수집된 연도는 전체 연도와 직접 비교할 수 없습니다. 연도 비교에는 같은 날짜 범위의 값을 사용해야 합니다.",
    "no_score": "이 화면은 판단에 필요한 사실만 모아 보여 줍니다. 진입 가능성을 점수로 매기지 않습니다.",
}

ASSUMPTION_NOTICE = (
    "통계는 2026-09-15 기준 분석 스냅샷입니다. 실시간 수집 공고와 통계 DB의 자동 연동은 아직 완료되지 않았습니다."
)


def notice_identifier(row) -> str:
    """원본 공고번호·차수 표시. 내부 복합 ID는 그대로 보존한다."""
    number, order = row.get("bidNtceNo"), row.get("bidNtceOrd")
    if isinstance(number, str) and number.strip():
        return number + ("-" + str(order).zfill(3) if pd.notna(order) else "")
    value = str(row.get("notice_id", ""))
    parts = value.split("|")
    return "-".join(parts[-2:]) if len(parts) >= 3 else value


def region_display(value) -> str:
    """2026-09-30 표시용 명칭. 원본 값·지역 범위·건수를 합치지 않는다.

    광주·전남 통합은 이름 변경만으로 옛 참가 허용 범위가 같아지지 않으므로
    원본 시·도 단위 값에는 옛 지역을 함께 표시한다.
    """
    if not isinstance(value, str):
        return "–"
    aliases = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도", "제주도": "제주특별자치도",
               "광주광역시": "전남광주통합특별시", "전라남도": "전남광주통합특별시"}
    parts = []
    for part in value.split("|"):
        part = part.strip()
        base = part.split(" ", 1)[0]
        if base in aliases:
            updated = aliases[base] + part[len(base):]
            if part == base:
                updated += f" (구 {base})"
            parts.append(updated)
        else:
            parts.append(part)
    return " · ".join(parts)


def is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def won(v) -> str:
    """원 → 억원/조원 표기."""
    if is_missing(v):
        return "–"
    # 요약 타일에서 잘리지 않게 짧게: 100억 이상은 소수점 없이(예: 2,955억원)
    if abs(v) >= 1e12:
        return f"{v / 1e12:,.2f}조원"
    if abs(v) >= 1e10:
        return f"{v / 1e8:,.0f}억원"
    if abs(v) >= 1e8:
        return f"{v / 1e8:,.1f}억원"
    return f"{v / 1e4:,.0f}만원"


def pct(v, digits: int = 1) -> str:
    return "–" if is_missing(v) else f"{v * 100:.{digits}f}%"


def num(v, digits: int = 0) -> str:
    """정수로 떨어지면 소수점 없이, 아니면 digits 자리까지."""
    if is_missing(v):
        return "–"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.{digits}f}"


def delta_pct(v) -> str | None:
    return None if is_missing(v) else f"{v * 100:+.1f}%"


def kpi_sample_context(current, previous, *, year: int, basis: str) -> dict:
    """계약 건수의 표시만 정한다. 5건 이하/30건 미만은 운영상 표시 기준이다."""
    def count(value):
        if value is None or pd.isna(value):
            return None
        try:
            number = float(value)
            return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
        except (TypeError, ValueError, OverflowError):
            return None

    current, previous = count(current), count(previous)
    if current is None:
        badge, color = None, 'gray'
        caption = f'{year}년 · 기준 건수 확인 불가'
    else:
        badge = '집계 대상 없음' if current == 0 else '표본 매우 적음' if current <= 5 else '표본 제한적' if current < 30 else None
        color = 'orange' if current and current <= 5 else 'gray'
        caption = f'{year}년 · {basis} {current:,}건 기준'
    show_delta = current is not None and previous is not None and min(current, previous) > 5
    return {'sample_badge': badge, 'sample_badge_color': color, 'sample_caption': caption,
            'show_delta': show_delta}


def year_delta(current, previous, unit: str) -> str:
    """비율은 %p, 건수는 증감률(전년 0은 실수 차이), 참가 수는 실수 차이."""
    if is_missing(current) or is_missing(previous):
        return "–"
    diff = current - previous
    if unit == "%p":
        value, digits, suffix = diff * 100, 1, "%p"
    elif unit == "곳":
        value, digits, suffix = diff, 1, "곳"
    elif previous == 0:
        value, digits, suffix = diff, 0, unit
    else:
        value, digits, suffix = diff / previous * 100, 1, "%"
    # 표시 자릿수에서 0인 변화에 방향 화살표를 붙이지 않는다.
    return "−" if round(value, digits) == 0 else f"{value:+,.{digits}f}{suffix}"
