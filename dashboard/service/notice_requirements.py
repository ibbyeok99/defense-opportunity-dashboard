"""공고·차수의 공식 API → 원문 → 첨부 순서로 요건 근거를 읽는다. DB·판정값은 변경하지 않는다."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
import streamlit as st

from service.notice_documents import _official_source_url
from service.requirement_documents import MAX_BYTES, evidence_from_text, extract_bounded

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/"
OPERATIONS = {"물품": "getBidPblancListInfoThng", "용역": "getBidPblancListInfoServc",
              "공사": "getBidPblancListInfoCnstwk", "외자": "getBidPblancListInfoFrgcpt"}
SCHEMA = "g2b-requirement-evidence-v10"


class EvidenceError(ValueError):
    pass


def validate_identity(number: str, order: str):
    if not re.fullmatch(r"[A-Za-z0-9]{8,20}", number) or not re.fullmatch(r"\d{3}", order):
        raise EvidenceError("원본 공고번호·3자리 차수를 확인할 수 없습니다.")


def same_notice_url(url: str, number: str, order: str) -> str:
    _official_source_url(url)
    query = parse_qs(urlparse(url).query)
    if query.get("bidPbancNo") != [number] or query.get("bidPbancOrd") != [order]:
        raise EvidenceError("첨부·원문 주소의 공고번호/차수가 다릅니다. 다른 공고 자료는 사용하지 않습니다.")
    return url


def _api(operation, number, order, key, deadline) -> list[dict]:
    rows, total, received = [], None, 0
    for page in range(1, 4):
        if time.monotonic() >= deadline:
            raise EvidenceError("확인 시간 제한을 초과했습니다.")
        try:
            # 오류 문자열에 serviceKey가 포함될 수 있어 requests 예외를 전달하지 않는다.
            with requests.get(BASE + operation, params={"serviceKey": unquote(key), "type": "json",
                              "inqryDiv": 2, "bidNtceNo": number, "bidNtceOrd": order,
                              "numOfRows": 100, "pageNo": page}, timeout=(4, 12),
                              allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise EvidenceError(f"공식 API 응답 오류(HTTP {response.status_code}). 자동 재시도하지 않습니다.")
                parts, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise EvidenceError("공식 API 응답 크기 한도를 초과했습니다.")
                    parts.append(chunk)
                obj = json.loads(b"".join(parts)).get("response", {})
        except EvidenceError:
            raise
        except requests.exceptions.Timeout:
            raise EvidenceError("공식 API 응답 시간 초과. 자동 재시도하지 않습니다.") from None
        except (json.JSONDecodeError, AttributeError, TypeError):
            raise EvidenceError("공식 API JSON 응답 형식 오류. 자동 재시도하지 않습니다.") from None
        except Exception:
            raise EvidenceError("공식 API 연결·응답 해석 실패. 자동 재시도하지 않습니다.") from None
        header, body = obj.get("header", {}), obj.get("body", {})
        code = str(header.get("resultCode", ""))
        if code != "00":
            raise EvidenceError(f"공식 API 조회 거부/오류(코드 {code[:5] if code.isalnum() else '미확인'}). 반복 호출하지 않습니다.")
        total = int(body.get("totalCount", 0))
        items = body.get("items", []) or []
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        for row in items:
            if row.get("bidNtceNo") != number or not re.fullmatch(r"\d{3}", str(row.get("bidNtceOrd", ""))):
                raise EvidenceError("API 응답의 공고번호·차수 불일치. 결과를 사용하지 않습니다.")
        # 번호 조회는 차수 파라미터를 받아도 모든 차수를 반환한다. 전체 페이지를
        # 읽은 후 요청한 차수만 선택한다. 다른 차수의 조건을 상속하지 않는다.
        received += len(items)
        rows.extend(row for row in items if str(row["bidNtceOrd"]) == order)
        if received >= total:
            if total > 0 and not rows:
                raise EvidenceError("API 응답의 공고번호·차수 불일치. 요청 차수의 결과가 없습니다.")
            return rows
        if not items:
            raise EvidenceError("API 페이지가 누락되어 전체 조건을 확인할 수 없습니다.")
    raise EvidenceError("조건이 300개를 초과하여 전체 조회하지 못했습니다. 수동 확인이 필요합니다.")


def download(url: str, limit: int, deadline: float) -> tuple[bytes, str]:
    current = _official_source_url(url)
    for attempt in range(4):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise EvidenceError("확인 시간 제한을 초과했습니다.")
        try:
            with requests.get(current, timeout=(4, min(12, remaining)), allow_redirects=False,
                              stream=True, headers={"User-Agent": "FrontlineData-NoticeEvidence/1.0"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if attempt == 3 or not response.headers.get("Location"):
                        raise EvidenceError("공식 주소 이동 한도를 초과했습니다.")
                    current = _official_source_url(urljoin(current, response.headers["Location"]))
                    continue
                if response.status_code != 200:
                    raise EvidenceError(f"공식 파일 접근 실패(HTTP {response.status_code}).")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > limit or time.monotonic() > deadline:
                        raise EvidenceError("다운로드 크기·시간 한도를 초과했습니다.")
                    chunks.append(chunk)
                return b"".join(chunks), current
        except (EvidenceError, ValueError):
            raise
        except Exception:
            raise EvidenceError("공식 원문·첨부 연결 실패. 수동 확인이 필요합니다.") from None
    raise EvidenceError("원문 다운로드에 실패했습니다.")


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self.hidden = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append(href)
        if tag in {"p", "br", "div", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def check_requirements(number: str, order: str, procurement_type: str, key: str, *, include_page=True, time_budget=90, on_progress=None) -> dict:
    validate_identity(number, order)
    if procurement_type not in OPERATIONS or not key.strip():
        raise EvidenceError("공식 API 키 또는 조달 유형 설정이 없습니다.")
    if not 5 <= time_budget <= 90:
        raise EvidenceError('확인 시간 한도는 5~90초입니다.')
    deadline = time.monotonic() + time_budget
    progress = on_progress or (lambda message: None)
    progress('공식 공고·면허·지역 조건 찾는 중…')
    result = {"schema": SCHEMA, "notice_number": number, "notice_order": order,
              "checked_at": datetime.now(timezone.utc).isoformat(), "evidence": [], "sources": [],
              "warnings": [], "api_license_rows": [], "api_region_rows": [], "attachment_inventory_complete": True}
    records = _api(OPERATIONS[procurement_type], number, order, key, deadline)
    if len(records) != 1:
        raise EvidenceError("공식 API에서 해당 공고·차수 한 건을 확인하지 못했습니다. 변경공고를 수동 확인하세요.")
    notice = records[0]
    # 업종 제한과 지역·다른 참가자격 제한을 혼동하지 않도록 원문 필드명을 보존한다.
    result["notice_flags"] = {"indstrytyLmtYn": notice.get("indstrytyLmtYn", "")}
    result["notice_facts"] = {k: notice.get(k, "") for k in ("bidNtceNm", "bidNtceDt", "bidClseDt", "chgDt")}
    for op, field, kind, value_field in [
        ("getBidPblancListInfoLicenseLimit", "api_license_rows", "면허", "lcnsLmtNm"),
        ("getBidPblancListInfoPrtcptPsblRgn", "api_region_rows", "지역", "prtcptPsblRgnNm"),
    ]:
        rows = _api(op, number, order, key, deadline)
        # 원본 그룹·순번을 보존한다. 그룹의 AND/OR 의미를 추정하지 않는다.
        allowed = {"bidNtceNo", "bidNtceOrd", "lmtGrpNo", "lmtSno", value_field,
                   "permsnIndstrytyList", "indstrytyMfrcFldList", "rgstDt"}
        result[field] = [{k: v for k, v in row.items() if k in allowed} for row in rows]
        result["sources"].append({"name": f"공식 API {kind}", "url": BASE + op,
                                  "status": f"{len(rows)}개 행 확인"})
        for row in rows:
            if row.get(value_field):
                result["evidence"].append({"kind": kind, "location": "공식 API",
                    "excerpt": str(row[value_field]), "status": "공식 구조화 조건", "scope": "공식 API",
                    "group": row.get("lmtGrpNo", ""), "sequence": row.get("lmtSno", ""), "source": f"공식 API {kind}"})
    urls = []
    for index in range(1, 11):
        url = str(notice.get(f"ntceSpecDocUrl{index}", "") or "")
        if url:
            urls.append((str(notice.get(f"ntceSpecFileNm{index}", "") or f"첨부 {index}"), url))
    page_url = str(notice.get("bidNtceDtlUrl", "") or "")
    if page_url and not include_page:
        result["sources"].append({"name": "원문 페이지", "url": page_url, "status": "미열람·API/첨부 우선 회차"})
    if page_url and include_page:
        progress('공고 원문에서 제한 조건 찾는 중…')
        try:
            same_notice_url(page_url, number, order)
            blob, final = download(page_url, 2 * 1024 * 1024, deadline)
            same_notice_url(final, number, order)
            parser = PageText()
            parser.feed(blob.decode("utf-8", errors="replace"))
            text = "".join(parser.parts)
            if number not in text:
                result["sources"].append({"name": "원문 페이지", "url": page_url, "status": "공고 본문 미확인·동적/안내 화면"})
            else:
                found = evidence_from_text(text, "원문 본문")
                result["evidence"].extend(dict(e, source="원문 페이지") for e in found)
                result["sources"].append({"name": "원문 페이지", "url": page_url, "status": "본문 근거 후보 발견" if found else "본문 근거 미발견"})
                for href in parser.links:
                    url = urljoin(page_url, href)
                    try:
                        same_notice_url(url, number, order)
                    except ValueError:
                        continue
                    if "downloadFile.do" in url:
                        urls.append(("원문 링크 첨부", url))
        except ValueError:
            result["sources"].append({"name": "원문 페이지", "url": page_url, "status": "원문 접근·동일 공고 확인 실패"})
    # 근거 후보 발견은 확인 완료가 아니다. API 미확인 항목이 있으면 모든 제공 첨부를 한도 내 대조한다.
    seen, consumed = set(), 0
    for name, url in urls:
        if url in seen:
            continue
        if len(seen) >= 5 or consumed >= 60 * 1024 * 1024 or time.monotonic() >= deadline:
            result["warnings"].append("첨부 확인 한도(5개·전체60 MiB·90초)에 도달했습니다. 남은 첨부를 수동 확인하세요.")
            result["sources"].append({"name": name, "url": url, "status": "미열람·첨부 확인 한도", "read_stage": "미열람"})
            seen.add(url)
            continue
        seen.add(url)
        source = {"name": name, "url": url, "status": "미확인"}
        progress('첨부 공고문·파일에서 제한 조건 찾는 중…')
        try:
            same_notice_url(url, number, order)
            blob, final = download(url, min(MAX_BYTES, 60 * 1024 * 1024 - consumed), deadline)
            same_notice_url(final, number, order)
            consumed += len(blob)
            source['read_stage'] = '다운로드 완료'
            parsed = extract_bounded(blob, timeout=max(.1, min(20, deadline - time.monotonic())))
            source.update({k: parsed[k] for k in ("format", "sha256", "status")})
            source["evidence_truncated"] = parsed.get("evidence_truncated", False)
            source["document_gaps"] = parsed.get("document_gaps", [])
            source['read_stage'] = '본문 읽기 완료'
            if parsed.get("ocr_pages"):
                source["ocr_pages"] = parsed["ocr_pages"]
                source["status"] += " · OCR 수동 대조 필요"
            if parsed["format"] == "ZIP":
                source["archive_inventory"] = parsed.get("archive_inventory", [])
                source["archive_complete"] = parsed.get("archive_complete", False)
                if not source["archive_complete"]:
                    result["warnings"].append("ZIP의 미지원·읽기 실패·이미지/OCR 대조 파일이 남았습니다. 내부 파일 목록에서 확인하세요.")
            result["evidence"].extend(dict(e, source=name) for e in parsed["evidence"])
            if not parsed["text_available"]:
                source["status"] = "본문 텍스트 없음·스캔/OCR 수동 확인 필요"
        except Exception:
            source["status"] = ("문서 읽기 실패·암호/손상/미지원 또는 처리 한도·수동 확인 필요"
                                if source.get('read_stage') == '다운로드 완료' else
                                "다운로드·동일 공고 확인 실패·수동 확인 필요")
        result["sources"].append(source)
    result["warnings"].append("빈 API 응답·검색 미발견·첨부 실패는 ‘제한 없음’이 아닙니다. 후보 문장과 다른 첨부·정정공고를 함께 확인하세요.")
    return result


@st.cache_data(ttl=3600, max_entries=128, show_spinner=False)
def _cached_check(number: str, order: str, procurement_type: str, schema: str, _service_key: str):
    return check_requirements(number, order, procurement_type, _service_key)


def fetch_evidence(number: str, order: str, procurement_type: str) -> dict:
    """페이지에서 요청할 때만 호출. 키는 캐시 hash·공개 결과에 넣지 않는다."""
    from service.source import requirement_service_key, save_requirement_evidence
    key = requirement_service_key()
    if not key:
        return {"error": "자동 확인을 이용할 수 없습니다. 나라장터 원문에서 직접 확인해 주세요."}
    try:
        result = _cached_check(number, order, procurement_type, SCHEMA, key)
        return save_requirement_evidence(result, procurement_type)
    except EvidenceError as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "요건 확인 실패. 제한 없음으로 판단하지 말고 원문을 직접 확인하세요."}


@st.cache_resource(max_entries=1, show_spinner=False)
def _detail_jobs():
    from service.requirement_jobs import RequirementJobs
    return RequirementJobs()


def detail_fingerprint(notice):
    from service.requirement_queue import source_fingerprint
    # 표시용 보완값이 바뀌었다고 같은 원문을 다시 호출하지 않는다.
    row = dict(notice)
    for kind in ('license', 'region'):
        row[kind + '_state'] = row[kind + '_values'] = ''
    return source_fingerprint(row)


def poll_detail_evidence(notice, force=False):
    """빠른 상태 읽기/작업 제출만 한다. 완료를 기다리거나 전체 공고를 다시 읽지 않는다."""
    from service import source
    from service.requirement_overlay import identity, fresh
    pt, number, order = identity(notice)
    fingerprint = detail_fingerprint(notice)
    job_id = (pt, number, order, fingerprint)
    jobs = _detail_jobs()
    existing = jobs.peek(job_id)
    if existing and (existing['phase'] == 'running' or not force):
        return existing
    saved = notice.get('requirement_evidence')
    if not isinstance(saved, dict) or saved.get('api_only'):
        # 공고 목록에서는 사본을 읽지 않는다. 상세/즐겨찾기 요청 시에만 읽는다.
        saved = next((record for record in source.read_requirement_evidence()
                      if identity(record) == (pt, number, order)), None)
    if not force and isinstance(saved, dict) and fresh(saved) and saved.get('detail_fingerprint') == fingerprint:
        return {'phase': 'done', 'result': saved, 'message': '저장된 확인 결과'}
    key = source.requirement_service_key()  # 세션 밖 worker에서 Secrets를 읽지 않는다.
    if not key:
        return {'phase': 'unavailable', 'message': '자동 확인을 이용할 수 없습니다. 나라장터 원문에서 직접 확인해 주세요.'}
    expected_title = str(notice.get('notice_name', '')).strip()
    expected_close = notice.get('bid_close_date')

    def work(progress):
        import pandas as pd
        result = check_requirements(number, order, pt, key, on_progress=progress)
        if identity(dict(result, procurement_type=pt)) != (pt, number, order):
            raise ValueError('공고 식별자 불일치')
        facts = result.get('notice_facts', {})
        if facts.get('bidNtceNm') and str(facts['bidNtceNm']).strip() != expected_title:
            raise ValueError('공고 제목 불일치')
        if facts.get('bidClseDt') and pd.to_datetime(facts['bidClseDt'], errors='coerce') != expected_close:
            raise ValueError('공고 마감 불일치')
        result['detail_fingerprint'] = fingerprint
        return source.save_requirement_evidence(result, pt)

    return jobs.start(job_id, work, force=force)
