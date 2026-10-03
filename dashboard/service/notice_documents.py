"""나라장터 공고 원문 PDF에서 검토용 근거를 추출한다.

공식 PDF 한 건의 제한적 읽기와 필드 후보·페이지·원문 인용을 제공한다.
DB 쓰기는 수행하지 않는다.
자동 적격 판정은 하지 않으며, 추출 실패는 제한 없음으로 해석하지 않는다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests

MAX_PDF_BYTES = 30 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_REDIRECTS = 3
OFFICIAL_HOSTS = {"g2b.go.kr", "www.g2b.go.kr"}

_AMOUNT_PATTERN = re.compile(
    r"(?P<label>사업금액|추정가격|배정예산|기초금액|예정가격|낙찰금액|계약금액)"
    r"\s*[:：]?\s*(?:금\s*)?(?P<amount>[0-9][0-9,]*(?:\.\d+)?)\s*"
    r"(?P<unit>원|천원|만원|억원)?",
    re.MULTILINE,
)
_ELIGIBILITY_LABELS = (
    "입찰참가자격",
    "입찰 참가 자격",
    "참가자격",
    "참가 자격",
    "입찰참가 자격",
)
_HEADING_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVX]+[.)、]?|\d{1,2}[.)、])"
    r"\s*[^\n]{2,50}(?:\n|$)"
)


@dataclass(frozen=True)
class AmountEvidence:
    label: str
    raw_value: str
    amount_krw: str | None
    unit: str
    vat_basis: str
    page: int
    evidence: str


@dataclass(frozen=True)
class RequirementEvidence:
    label: str
    page: int
    excerpt: str


def _official_source_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or host not in OFFICIAL_HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError("출처 URL은 HTTPS 나라장터(g2b.go.kr) 주소여야 합니다.")
    return source_url


def download_official_pdf(source_url: str) -> bytes:
    """명시적으로 제공된 공식 G2B PDF URL 한 건만 제한적으로 다운로드한다.

    공고 페이지에서 첨부 링크를 찾지는 않는다. 해당 탐색은 별도 검증 대상이다.
    """
    current_url = _official_source_url(source_url)
    for redirect_count in range(MAX_REDIRECTS + 1):
        with requests.get(
            current_url,
            headers={"Accept": "application/pdf"},
            timeout=(3.05, 20),
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                if redirect_count == MAX_REDIRECTS:
                    raise ValueError("나라장터 PDF URL의 리다이렉트 횟수가 제한을 초과합니다.")
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("리다이렉트 응답에 Location 주소가 없습니다.")
                current_url = _official_source_url(urljoin(current_url, location))
                continue

            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_PDF_BYTES:
                raise ValueError("PDF가 최대 허용 크기(30 MiB)를 초과합니다.")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise ValueError("PDF가 최대 허용 크기(30 MiB)를 초과합니다.")
                chunks.append(chunk)
            pdf_bytes = b"".join(chunks)
            if not pdf_bytes.startswith(b"%PDF-"):
                raise ValueError("응답 내용이 PDF가 아닙니다.")
            return pdf_bytes
    raise ValueError("나라장터 PDF 다운로드에 실패했습니다.")


def _vat_basis(text: str) -> str:
    compact = re.sub(r"\s+", " ", text)
    has_included = bool(re.search(r"부가가치세\s*포함|부가세\s*포함|VAT\s*포함", compact, re.I))
    has_excluded = bool(re.search(r"부가가치세\s*제외|부가세\s*별도|VAT\s*제외", compact, re.I))
    if has_included and not has_excluded:
        return "포함"
    if has_excluded and not has_included:
        return "제외"
    return "미표기"


def _amount_krw(raw: str, unit: str) -> str | None:
    multiplier = {"원": Decimal(1), "천원": Decimal(1_000), "만원": Decimal(10_000), "억원": Decimal(100_000_000)}
    try:
        amount = Decimal(raw.replace(",", "")) * multiplier.get(unit, Decimal(1))
    except Exception:
        return None
    if amount != amount.to_integral_value():
        return None
    return str(int(amount))


def _extract_page(text: str, page: int) -> tuple[list[AmountEvidence], list[RequirementEvidence]]:
    amounts: list[AmountEvidence] = []
    matches = list(_AMOUNT_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        start, end = match.span()
        context = text[max(0, start - 40): min(len(text), end + 100)]
        evidence = re.sub(r"\s+", " ", context).strip()
        vat_end = matches[index + 1].start() if index + 1 < len(matches) else min(len(text), end + 100)
        vat_context = text[end:vat_end]
        unit = match.group("unit") or "원"
        amounts.append(AmountEvidence(
            label=match.group("label"),
            raw_value=f"{match.group('amount')} {match.group('unit') or ''}".strip(),
            amount_krw=_amount_krw(match.group("amount"), unit),
            unit=unit,
            vat_basis=_vat_basis(vat_context),
            page=page,
            evidence=evidence,
        ))

    requirements: list[RequirementEvidence] = []
    for label in _ELIGIBILITY_LABELS:
        match = re.search(re.escape(label), text)
        if not match:
            continue
        remainder = text[match.end():]
        next_heading = _HEADING_PATTERN.search(remainder)
        excerpt = remainder[:next_heading.start()] if next_heading else remainder[:1200]
        excerpt = re.sub(r"\s+", " ", excerpt).strip(" :：-\t")[:1200]
        if excerpt:
            requirements.append(RequirementEvidence(label=label, page=page, excerpt=excerpt))
        break
    return amounts, requirements


def extract_notice_pdf(pdf_bytes: bytes, source_url: str) -> dict:
    """공식 나라장터 PDF를 분석해 수치 후보·참가자격 발췌문·출처를 반환한다."""
    source_url = _official_source_url(source_url)
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("입력은 PDF 바이트여야 합니다.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF가 최대 허용 크기({MAX_PDF_BYTES // 1024 // 1024} MiB)를 초과합니다.")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF 추출에는 dashboard/requirements-db.txt의 pypdf 설치가 필요합니다.") from exc

    reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDF 페이지 수가 최대 허용치({MAX_PDF_PAGES})를 초과합니다.")

    all_amounts: list[AmountEvidence] = []
    all_requirements: list[RequirementEvidence] = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        amounts, requirements = _extract_page(text, page_no)
        all_amounts.extend(amounts)
        all_requirements.extend(requirements)

    return {
        "schema": "g2b-notice-document-evidence-v1",
        "source_url": source_url,
        "document_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "page_count": len(reader.pages),
        "extraction_status": "evidence_found" if all_amounts or all_requirements else "no_text_evidence",
        "eligibility_status": "source_excerpt_only" if all_requirements else "unknown",
        "amounts": [asdict(item) for item in all_amounts],
        "requirements": [asdict(item) for item in all_requirements],
        "warnings": [
            "추출 결과는 원문 검토용 후보이며 법적 자격 판정이 아닙니다.",
            "검색되지 않은 값은 0 또는 제한 없음으로 간주하지 않습니다.",
            "사업금액·추정가격·기초금액·예정가격·낙찰금액·계약금액은 서로 다른 의미의 필드입니다.",
        ],
    }
