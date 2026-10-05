"""원본 요건과 분리한 근거 보완. 후보 문장으로 회사 적격을 확정하지 않는다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import json

import pandas as pd
from service.requirement_documents import PATTERNS

SCHEMA = "requirement-overlay-v1"
MAX_AGE = timedelta(hours=24)
NONE_PATTERNS = {
    "license": re.compile(r"(?:면허|업종)\s*제한\s*(?:없음|없습니다|없다|을\s*두지\s*않)"),
    "region": re.compile(r"지역\s*제한\s*(?:없음|없습니다|없다|을\s*두지\s*않)"),
}
COMPLEX = re.compile(r"다만|예외|공동\s*수급|대표\s*사|분담|제외|한하여|한해|경우|변경|정정")
PROVINCES = ("서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
             "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "강원도", "충청북도", "충청남도",
             "전북특별자치도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도")
MAIN_OFFICE_REGION = re.compile(r"(?:법인등기부상\s*)?(?:본점\s*소재지|본사\s*소재지|주된\s*영업소(?:의\s*소재지)?)를?\s*(?:" +
    "(?P<region>" + "|".join(PROVINCES) + r"))\s*에\s*(?:두고\s*있는|둔|두어야\s*하는)\s*(?:업체|자|기업)")


def usable_values(value):
    """미확인 표시·원문 참조 문구는 실제 면허명/지역명이 아니다."""
    placeholders = {"", "-", "–", "미확인", "UNKNOWN", "NAN", "NONE", "NULL", "<NA>",
                    "공고서참조", "공고문참조", "정보없음"}
    return [v.strip() for v in str(value).split("|")
            if re.sub(r"\s+", "", v).upper() not in placeholders]


def identity(row) -> tuple[str, str, str]:
    pt = str(row.get("procurement_type", ""))
    no, order = row.get("bidNtceNo", row.get("notice_number")), row.get("bidNtceOrd", row.get("notice_order"))
    if not isinstance(no, str) or not isinstance(order, str):
        parts = str(row.get("notice_id", "")).split("|")
        no, order = parts[-2:] if len(parts) >= 3 else ("", "")
    order = order.zfill(3)
    if pt not in {"물품", "공사", "용역", "외자"} or not re.fullmatch(r"[A-Za-z0-9]{8,20}", no) or not re.fullmatch(r"\d{3}", order):
        raise ValueError("공고 유형·번호·차수 오류")
    return pt, no, order


def fresh(record, now=None) -> bool:
    try:
        checked = datetime.fromisoformat(record["checked_at"])
        now = now or datetime.now(timezone.utc)
        return record.get("overlay_schema") == SCHEMA and checked.tzinfo is not None and timedelta(0) <= now - checked < MAX_AGE
    except (KeyError, TypeError, ValueError):
        return False


def condition(result, kind):
    """API 구조화 값, 명시적 없음, 해석할 문장을 각각 구분한다."""
    if result.get('projection_schema'):
        from service.requirement_projection import validate
        return validate(result)['resolved'][kind]
    from service.notice_date_policy import cancelled
    if cancelled(result):
        return dict(state='미확인', values='', review='취소공고·참가 대상 아님', manual=True,
                    quote='취소 차수의 자료는 이력으로 보존합니다. 이전 차수 조건을 상속하거나 참가 가능으로 판단하지 않습니다.')
    if any(re.search(r'제목 불일치|식별자.*불일치|공고번호·차수 불일치', str(s.get('reason', '')))
           for s in result.get('sources', [])):
        return dict(state='미확인', values='', review='근거 충돌', manual=True,
                    quote='공개 원문과 저장 공고의 식별 정보가 다릅니다. 이전 버전의 조건을 적용하지 않습니다.')
    label = {"license": "면허", "region": "지역"}[kind]
    field = {"license": "lcnsLmtNm", "region": "prtcptPsblRgnNm"}[kind]
    rows = result.get(f"api_{kind}_rows", [])
    values = list(dict.fromkeys(v for r in rows for v in usable_values(r.get(field))))
    page = result.get('public_page', {})
    page_rows = page.get('limits', {}).get(kind, []) if isinstance(page, dict) else []
    page_values = list(dict.fromkeys((r['name'] + '/' + r['code'] if kind == 'license'
                                     and re.fullmatch(r'\d{4}', r.get('code', '')) else r['name'])
                                   for r in page_rows if usable_values(r.get('name', ''))))
    direct = [e for e in result.get("evidence", []) if e.get("scope") == "참가자격 구역"
              and e.get("method") != "ocr" and e.get("kind") in {label, "참가자격"}]
    # 저장된 과거 후보도 현재 추출 규칙으로 재검증한다. '본사업'의 '본사'는 지역 근거가 아니다.
    relevant = [e for e in direct if (e.get("kind") in {label, "참가자격"} and PATTERNS[label].search(e.get("excerpt", "")))
                or NONE_PATTERNS[kind].search(e.get("excerpt", ""))]
    quotes = list(dict.fromkeys(e["excerpt"] for e in relevant if e.get("excerpt")))
    text = "\n".join(quotes)
    absence = bool(NONE_PATTERNS[kind].search(text))
    industry_flag = str(result.get("notice_flags", {}).get("indstrytyLmtYn", "")).strip().upper() if kind == "license" else ""
    # 제한 없음과 구조화 조건이 충돌하면 어떤 값도 자동 선택하지 않는다.
    if (absence or industry_flag == "N") and (values or page_values):
        return dict(state="미확인", values="", review="근거 충돌", manual=True, quote=text[:2500])
    if values:
        api_codes = {m for v in values for m in re.findall(r'(?<!\d)\d{4}(?!\d)', v)}
        page_codes = {r['code'] for r in page_rows if re.fullmatch(r'\d{4}', r.get('code', ''))}
        if api_codes and page_codes and api_codes != page_codes:
            return dict(state='미확인', values='', review='근거 충돌', manual=True,
                        quote='API 업종과 공개 원문 제한 표의 업종 코드가 다릅니다.')
        return dict(state="제한있음", values=" | ".join(values), review="공식 조건 확인", manual=False, quote=text[:2500])
    if page_values:
        if absence:
            return dict(state='미확인', values='', review='근거 충돌', manual=True, quote=text[:2500])
        return dict(state='제한있음', values=' | '.join(page_values), review='문서 제한 조건·원문 검토',
                    manual=True, quote=text[:2500] or '공개 원문 제한 표: ' + ' | '.join(page_values))
    if industry_flag == "N" and not quotes:
        return dict(state="미확인", values="", review="공식 업종 제한 없음", manual=True,
                    quote="공식 공고 indstrytyLmtYn=N. 업종 제한 표시이며 다른 면허·참가자격의 제한 없음은 확정하지 않습니다.")
    if quotes:
        # 한 구역에서 상반되는 문장을 발견하거나 예외가 있으면 없음으로 확정하지 않는다.
        restricted = re.search(r"(?:지역|면허|업종)\s*제한\s*(?:있|적용)|(?:본점|본사|주된\s*영업소).{0,180}(?:두[고어]|둔|소재)|업종\s*코드\s*[0-9]", text)
        qualification = "\n".join(e.get("excerpt", "") for e in direct if e.get("kind") == "참가자격")
        negated = re.search(r"없(?:음|습니다|다).{0,15}(?:아니|아님|아닌|아닙|않)", text)
        if absence and not restricted and not negated and not COMPLEX.search(qualification or text):
            if kind == "license" and not re.search(r"면허\s*제한", text):
                return dict(state="미확인", values="", review="문서상 업종 제한 없음", manual=True, quote=text[:2500])
            return dict(state="조건없음", values="", review="문서상 제한 없음", manual=True, quote=text[:2500])
        if kind == "region" and not absence and not COMPLEX.search(qualification or text) and not re.search(r"예시|우대|가점|아닌|아니|않", qualification or text):
            places = list(dict.fromkeys(m.group("region") for m in MAIN_OFFICE_REGION.finditer(text)))
            # 시·도 한 곳을 본점 자격으로 명시한 단순 문장만. 납품 장소·복수 지역·예외는 보류한다.
            mentioned = set(re.findall("|".join(PROVINCES), qualification or text))
            if len(places) == 1 and mentioned == set(places):
                return dict(state="제한있음", values=places[0], review="문서 지역 조건 확인·원문 검토", manual=True, quote=text[:2500])
        from service.requirement_structure import structure_requirements
        clauses = structure_requirements(dict(result, evidence=direct))["clauses"]
        candidates = list(dict.fromkeys(
            f"{v['name']}/{v['code']}" if v['code'] else v['name']
            for c in clauses for v in c['licenses'])) if kind == "license" else list(dict.fromkeys(
                v for c in clauses for v in c['allowed_regions']))
        documented = (bool(candidates) and not absence and not negated
                      and not re.search(r"예시|우대|가점|아닌|아니|않", text))
        if kind == 'license' and not candidates and not absence:
            from service.requirement_structure import PARTICIPATION_REGISTRATION
            # 일반/외자 참가등록을 면허로 만들지 않는다. 공고 전체 면허 없음도 확정하지 않는다.
            if PARTICIPATION_REGISTRATION.search(qualification or text) and not re.search(r'면허|업종\s*(?:코드|번호|제한)', text):
                return dict(state='미확인', values='', review='면허 근거 미탐지·참가등록 별도 확인',
                            manual=True, quote=text[:2500])
        return dict(state="제한있음" if documented else "미확인", values=" | ".join(candidates),
                    review="문서 제한 조건·원문 검토" if documented else "문서 요건 후보·원문 검토" if candidates else "근거 확인·해석 필요",
                    manual=True, quote=text[:2500])
    attachments = [s for s in result.get("sources", []) if s.get("name") not in {"공식 API 면허", "공식 API 지역", "원문 페이지"}]
    statuses = " ".join(s.get("status", "") for s in attachments)
    incomplete = bool(re.search(r"실패|한도", statuses))
    readable = any(s.get('format') and not re.search(r"실패|한도", s.get('status', '')) for s in attachments)
    from service.requirement_coverage import coverage
    completeness = coverage(result)
    review = ("일부 첨부 미확인" if incomplete and readable else "추출 실패" if incomplete else "OCR 원문 대조 필요" if "OCR" in statuses
              else "자료 미제공" if not attachments else "자료 확인 미완료" if completeness["gaps"] else "확인 자료에서 근거 미탐지")
    if kind == "license" and industry_flag == "Y":
        review = "공식 제한 표시·상세 미제공"
    return dict(state="미확인", values="", review=review, manual=True, quote="")


def prepare(result, procurement_type):
    identity(dict(procurement_type=procurement_type, bidNtceNo=result["notice_number"], bidNtceOrd=result["notice_order"]))
    if result.get("error"):
        raise ValueError("실패한 조회는 보완값으로 저장하지 않습니다")
    from service.requirement_summary import clean_excerpt
    displayed = [dict(e, display_excerpt=clean_excerpt(e.get('excerpt', '')),
                     relevant=(e.get("kind") not in PATTERNS or e.get("scope") in {"공식 API", "공개 화면 구조화 조건"}
                                   or bool(PATTERNS[e["kind"]].search(e.get("excerpt", "")))))
                 for e in result.get("evidence", [])]
    from service.requirement_structure import structure_requirements
    from service.requirement_coverage import coverage
    prepared = dict(result, evidence=displayed, procurement_type=procurement_type, overlay_schema=SCHEMA,
                coverage=coverage(dict(result, evidence=displayed)),
                structured=structure_requirements(dict(result, evidence=displayed)),
                resolved={kind: condition(result, kind) for kind in ("license", "region")})
    from service.requirement_automation import classify_automation
    prepared['automation'] = classify_automation(prepared)
    return prepared


def overlay(frame, records, now=None):
    """복사본만 보완한다. 원본에서 이미 확인된 조건과 상충하면 원본을 유지한다."""
    out = frame.copy()
    for kind in ("license", "region"):
        out[f"{kind}_review_status"] = "미조회"
        out[f"{kind}_evidence_quote"] = ""
        out[f"{kind}_requires_review"] = False
    out["requirement_search_text"] = ""
    out["requirement_checked_at"] = ""
    out["requirement_other_summary"] = ""
    out["requirement_evidence"] = pd.Series([None] * len(out), index=out.index, dtype=object)
    valid = {}
    for r in records:
        if fresh(r, now):
            valid[(r["procurement_type"], r["notice_number"], r["notice_order"])] = r
    if not valid or "procurement_type" not in out:
        return out
    numbers = {key[1] for key in valid}
    if "bidNtceNo" in out:
        candidates = out[out.bidNtceNo.isin(numbers)]
    elif "notice_id" in out:
        candidates = out[out.notice_id.isin({"|".join(key) for key in valid})]
    else:
        return out
    patches = {}
    for index, row in candidates.iterrows():
        try:
            result = valid.get(identity(row))
        except ValueError:
            continue
        if result is None:
            continue
        facts = result.get("notice_facts", {})
        # 공식 API 제목의 끝 공백만 다른 실제 사례. 내부 문자·차수·마감 비교는 엄격히 유지한다.
        if facts.get("bidNtceNm") and str(facts["bidNtceNm"]).strip() != str(row.get("notice_name", "")).strip():
            continue
        if facts.get("bidClseDt") and pd.to_datetime(facts["bidClseDt"], errors="coerce") != row.get("bid_close_date"):
            continue
        changes = {"requirement_evidence": result, "requirement_checked_at": result["checked_at"]}
        other = list(dict.fromkeys(v['category'] for c in result.get('structured', {}).get('clauses', [])
                                  for v in c.get('other_requirements', [])))
        changes["requirement_other_summary"] = " · ".join(other)
        search = []
        for kind in ("license", "region"):
            resolved = condition(result, kind)  # 저장 판정 대신 현재 규칙으로 재검증한다.
            state_col, values_col = f"{kind}_state", f"{kind}_values"
            old_state = row.get(state_col)
            review = resolved["review"]
            # 제한 플래그만 있고 값이 미확인인 원본은 실제 조건이 확인된 상태가 아니다.
            missing_original = old_state == "제한있음" and not usable_values(row.get(values_col))
            if old_state == "미확인" or missing_original or review == '취소공고·참가 대상 아님':
                changes[state_col] = resolved["state"]
                changes[values_col] = resolved["values"]
                changes[f"{kind}_requires_review"] = resolved["manual"]
            elif resolved["state"] != "미확인" and (old_state != resolved["state"] or (old_state == "제한있음" and {v.strip() for v in str(row.get(values_col, "")).split("|") if v.strip()} != {v.strip() for v in resolved["values"].split("|") if v.strip()})):
                review = "근거 충돌"
                changes[f"{kind}_requires_review"] = True
            changes[f"{kind}_review_status"] = review
            if review == '근거 충돌':
                changes[f"{kind}_requires_review"] = True
            changes[f"{kind}_evidence_quote"] = resolved["quote"]
            search.extend([resolved["values"], resolved["quote"]])
        changes["requirement_search_text"] = " ".join(search)
        patches[index] = changes
    # Arrow 열은 한 셀마다 바꾸면 열 전체를 반복 복사한다. 같은 판단 결과를 열별로 한 번에 반영한다.
    for column in {column for changes in patches.values() for column in changes}:
        updates = pd.Series({index: changes[column] for index, changes in patches.items() if column in changes}, dtype=object)
        out.loc[updates.index, column] = updates
    return out


def pending(frame, now):
    """실제 공고일·마감이 유효한 마감 전 공고만. 과거의 잘못된 마감일은 제외한다."""
    dates, closes = pd.to_datetime(frame.notice_date, errors="coerce"), pd.to_datetime(frame.bid_close_date, errors="coerce")
    mask = dates.notna() & closes.notna() & (dates <= now) & (closes >= now) & (closes >= dates)
    # 수년 전 공고의 비정상 미래 마감값을 현재 작업으로 가져오지 않는다.
    mask &= dates >= now - pd.Timedelta(days=365)
    mask &= frame.license_state.eq("미확인") | frame.region_state.eq("미확인")
    result = frame.loc[mask].copy()
    def priority(row):
        try:
            flags = json.loads(row.get("extra_attributes") or "{}")
        except (ValueError, TypeError):
            flags = {}
        value = flags.get("indstrytyLmtYn")
        return 0 if row.license_state == "미확인" and value == "Y" else 1 if row.license_state == "미확인" and value == "N" else 2
    result["_requirement_priority"] = result.apply(priority, axis=1) if len(result) else pd.Series(dtype=int)
    return result.sort_values(["_requirement_priority", "bid_close_date", "notice_date"]).drop_duplicates("notice_id").drop(columns="_requirement_priority")
