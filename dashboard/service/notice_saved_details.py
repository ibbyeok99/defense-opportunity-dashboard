"""Codex, 2026-10-03: 선택한 공고의 저장 필드만 상세 표시용으로 가공한다.

네트워크·파일·DB 읽기, 코드명 추정, 금액 계산 및 참가자격 판정을 하지 않는다.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

import pandas as pd

MISSING = "미제공"


def _text(value) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    if pd.isna(value):
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"", "nan", "nat", "none", "null", "<na>", "미확인", "–"} else value[:4096]


def _extra(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or len(value) > 1024 * 1024:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _date(value) -> str:
    # 숫자·코드를 시각으로 해석하지 않고, 저장되지 않은 시각도 보충하지 않는다.
    value = _text(value)
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]|$)", value):
        return MISSING
    stamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(stamp):
        return MISSING
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("Asia/Seoul")
    return stamp.strftime("%Y-%m-%d %H:%M" if len(value) > 10 else "%Y-%m-%d")


def _number(value) -> str:
    text = _text(value).replace(",", "")
    if len(text) > 50 or not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return ""
    try:
        number = Decimal(text)
        if not number.is_finite():
            return ""
        result = format(number, ",f")
        return result.rstrip("0").rstrip(".") if "." in result else result
    except InvalidOperation:
        return ""


def _attachment_url(url, number, order) -> str:
    """저장된 공식 링크도 다른 공고·차수이거나 인증정보가 포함됐으면 표시하지 않는다."""
    url = _text(url)
    if not re.fullmatch(r"[A-Za-z0-9]{8,20}", number) or not re.fullmatch(r"\d{3}", order):
        return ""
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        valid = (parsed.scheme == "https" and parsed.hostname in {"g2b.go.kr", "www.g2b.go.kr"}
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and query.get("bidPbancNo") == [number] and query.get("bidPbancOrd") == [order]
                 and not any(key.lower() in {"servicekey", "apikey", "token", "password"} for key in query))
        return url if valid else ""
    except ValueError:
        return ""


def saved_notice_details(notice) -> dict:
    """공고 한 건만 변환. JSON이 없거나 손상돼도 추가 조회하지 않는다."""
    extra = _extra(notice.get("extra_attributes"))

    def pick(*keys):
        for key in keys:
            for source in (notice, extra):
                if _text(source.get(key)):
                    return source[key]
        return None

    def text(*keys):
        return _text(pick(*keys)) or MISSING

    def flag(*keys):
        value = text(*keys)
        return {"Y": "허용", "N": "불허"}.get(value.upper(), value)

    def money(*keys):
        number = _number(pick(*keys))
        if not number:
            return MISSING
        # 국내 예산·추정가격 필드만 원화 단위로 표시한다. 외자 통화는 추정하지 않는다.
        unit = "원" if _text(notice.get("procurement_type")) in {"물품", "용역", "공사"} else "(통화 미제공)"
        return f"{number} {unit}"

    rate = _number(pick("sucsfbidLwltRate_num", "sucsfbidLwltRate"))
    number, order = _text(pick("bidNtceNo")), _text(pick("bidNtceOrd"))
    # notice_id도 유형|번호|차수의 정확한 원본 식별자일 때만 사용한다.
    parts = _text(notice.get("notice_id")).split("|")
    if len(parts) == 3:
        if (number and number != parts[1]) or (order and order != parts[2]):
            number, order = "", ""  # 원본 식별자가 충돌하면 첨부 링크를 제공하지 않는다.
        else:
            number, order = number or parts[1], order or parts[2]
    attachments, seen = [], set()
    for slot in range(1, 11):
        name = _text(pick(f"ntceSpecFileNm{slot}"))
        raw_url = _text(pick(f"ntceSpecDocUrl{slot}"))
        if not name and not raw_url:
            continue
        url = _attachment_url(raw_url, number, order)
        identity = (name, raw_url)
        if identity in seen:
            continue
        seen.add(identity)
        attachments.append({"name": name or f"첨부파일 {slot} (파일명 미제공)", "url": url,
                            "note": "" if url else "저장된 링크 없음 또는 공고번호·차수/주소 확인 필요"})

    contract_method = text("contract_method", "cntrctCnclsMthdNm")
    return {
        "contract_method": contract_method,
        "schedule": {
            "공고 게시": _date(pick("notice_date", "bidNtceDt_kst", "bidNtceDt")),
            "입찰참가자격 등록 마감": _date(pick("bidQlfctRgstDt_kst", "bidQlfctRgstDt")),
            "입찰보증서 접수 마감": _date(pick("bidWgrnteeRcptClseDt_kst", "bidWgrnteeRcptClseDt")),
            "입찰서 제출 시작": _date(pick("bidBeginDt_kst", "bidBeginDt")),
            "입찰서 제출 마감": _date(pick("bidClseDt_kst", "bidClseDt", "bid_close_date")),
            "개찰": _date(pick("opengDt_kst", "opengDt")),
        },
        "price": {
            "배정예산": money("asignBdgtAmt_num", "asignBdgtAmt"),
            "추정가격": money("presmptPrce_num", "presmptPrce"),
            "예정가격 결정 방식": text("prearngPrceDcsnMthdNm"),
            "낙찰 방법": text("sucsfbidMthdNm"),
            "낙찰 기준": text("sucsfbidMthdAppStd"),
            "낙찰하한율": f"{rate}%" if rate else MISSING,
        },
        "participation": {
            "공고 종류": text("ntceKindNm"),
            "계약 방법": contract_method,
            "공동수급 방식": text("cmmnSpldmdMethdNm"),
            "공동수급협정서 접수 방식": text("cmmnSpldmdAgrmntRcptdocMethd"),
            "공동수급협정서 마감": _date(pick("cmmnSpldmdAgrmntClseDt_kst", "cmmnSpldmdAgrmntClseDt")),
            "재입찰": flag("rbidPermsnYn"),
            "국제입찰": {"Y": "국제입찰", "N": "국내입찰"}.get(text("intrbidYn").upper(), text("intrbidYn")),
        },
        "related": {"참조번호": text("refNo"), "사전규격 등록번호": text("bfSpecRgstNo"),
                    "발주계획 번호": text("orderPlanUntyNo"),
                    "이전 공고번호": text("prev_bid_no", "befBidBbancNo_std", "befBidBbancNo")},
        "attachments": attachments,
        "extra_available": bool(extra),
    }
