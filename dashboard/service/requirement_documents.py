"""공개 첨부의 텍스트 근거만 추출한다. 프로그램·매크로 실행과 적격 판정은 하지 않는다."""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import struct
import subprocess
import sys
import time
import zlib
from io import BytesIO
from pathlib import Path
from html.parser import HTMLParser
from zipfile import ZipFile
from xml.etree import ElementTree as ET

MAX_BYTES = 30 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_TEXT = 2_000_000
MAX_QUALIFICATION_QUOTE = 30_000
MAX_ARCHIVE_DOCUMENTS = 20
MAX_PDF_PAGES = 1000
FAST_PDF_THRESHOLD = 300
READ_FAILURES = {
    'unsupported_format': '지원하지 않는 문서 형식',
    'protected_document': '암호·배포용 문서',
    'damaged_document': '손상된 문서·압축',
    'processing_limit': '크기·페이지·처리 시간 한도',
    'text_encoding': '본문 문자 인코딩 오류',
    'access_response': '문서 대신 접근 제한 안내 응답',
    'unsafe_document': '매크로·엔티티 등 안전 제한',
    'empty_text': '읽을 수 있는 본문 없음',
    'read_failure': '문서 해석 실패·원인 추가 확인 필요',
}


class DocumentReadError(ValueError):
    def __init__(self, code):
        self.code = code if code in READ_FAILURES else 'read_failure'
        super().__init__('첨부 해석 실패: ' + READ_FAILURES[self.code] + '·수동 확인 필요')


def document_error_code(error):
    # 원시 예외/파일 경로/접속 주소를 저장하거나 사용자에게 전달하지 않는다.
    if isinstance(error, UnicodeError):
        return 'text_encoding'
    message = str(error)
    for code, pattern in (
        ('access_response', '접근 제한 안내'),
        ('protected_document', '암호|배포용'),
        ('unsafe_document', '매크로|DTD|엔티티'),
        ('processing_limit', '한도|제한을 초과|페이지를 초과'),
        ('unsupported_format', '지원하지 않는|HWP 5 형식이 아닙니다'),
        ('text_encoding', '문자 인코딩'),
        ('damaged_document', '손상'),
        ('empty_text', '읽을 수 있는 본문이 없습니다|본문을 읽지 못했습니다'),
    ):
        if re.search(pattern, message):
            return code
    return 'read_failure'
PATTERNS = {
    "면허": re.compile(r"면허|업종\s*(?:코드|등록|제한)|(?:업체|업종)로?\s*등록|(?:건설업|공사업|용역업)\s*(?:등록|신고)|제조업.{0,30}허가"),
    "지역": re.compile(r"지역\s*(?:제한|조건)|참가\s*가능\s*지역|본점|본사(?!업)|주된\s*영업소|법인등기부상"),
}
QUALIFICATION = re.compile(
    r"(?:^|\n)[ \t]*(?:[□■●○]\s*)?(?:(?P<number>\d{1,2})[.)]\s*)?"
    r"(?:(?:입\s*찰(?:\s*[（(]\s*견\s*적\s*(?:서\s*)?제\s*출\s*[）)])?|견\s*적\s*(?:서\s*)?제\s*출|다수\s*공급자\s*계약\s*구매)\s*)?(?:참\s*가\s*자\s*격|참\s*가\s*요\s*건|참\s*여\s*조\s*건)"
    r"(?:\s*(?:및|과)\s*(?:등록\s*사항|조건|요건|제한\s*사항))?"
    r"[ \t]*(?:[（(]\s*적격성\s*평가\s*신청일\s*기준\s*[）)])?"
    r"[ \t]*(?:(?P<trailing>\d{1,2})\s*\.)?[ \t]*(?:[:：][ \t]*|\n|$)")
NEXT_HEADING = re.compile(r"\n\s*(?P<number>\d{1,2})[.)]\s*[^\n]{2,80}(?:\n|$)")
NEXT_CAUTION_HEADING = re.compile(r"\n[ \t]*[□■●○][ \t]*유\s*의\s*사\s*항[^\n]{0,80}(?:\n|$)")
QUALIFICATION_EN = re.compile(
    r"(?:^|\n)[ \t]*(?:(?P<number>\d{1,2})[.)][ \t]*)?"
    r"QUALIFICATIONS?\s+(?:OF|FOR)\s+BIDDERS?[ \t]*[:：]?[ \t]*(?:\n|$)", re.I)
# 영문 DOCX는 자동 번호가 평문에 나오지 않는다. 대문자 구역 제목에서 끝낸다.
NEXT_HEADING_EN = re.compile(r"\n[ \t]*(?:\d{1,2}[.)][ \t]*)?[A-Z][A-Z /&()\-]{4,100}[ \t]*(?:\n|$)")
OTHER_REQUIREMENT = re.compile(r"중소\s*기업|소\s*기업|소상공인|직접\s*생산|제조\s*등록|제조물품|제조업|생산\s*능력|납품\s*실적|수행\s*실적|인증|확인서|지명\s*경쟁|지명한|공동\s*수급|공동\s*도급|공동\s*이행|분담\s*이행|보안|보증|참가\s*제한|제재|등록\s*마감|공고일\s*전일")


def _quote(text):
    # 문단/항목 경계를 보존해야 '및/또는'이 서로 다른 요건에 섞이지 않는다.
    return re.sub(r"[^\S\n]+", " ", text).strip()


def evidence_from_text(text: str, location: str) -> list[dict]:
    """단정 대신 키워드 주변 문장을 보존한다. 연락처·이행 장소만으로 지역을 추정하지 않는다."""
    if len(text) > MAX_TEXT:
        raise ValueError("본문 텍스트 한도를 초과했습니다.")
    evidence = []
    qualifications = []
    for heading in QUALIFICATION.finditer(text):
        number = heading.group("number") or heading.group("trailing")
        parent_number = int(number) if number else None
        next_heading = next((m for m in NEXT_HEADING.finditer(text, heading.end())
                             if parent_number is None or int(m.group("number")) > parent_number), None)
        end = next_heading.start() if next_heading else len(text)
        # 실제 무번호 참가자격 뒤의 유의사항 구역을 자격 요건에 섞지 않는다.
        if parent_number is None:
            caution = NEXT_CAUTION_HEADING.search(text, heading.end())
            if caution:
                end = min(end, caution.start())
        qualifications.append((heading.start(), end))
        evidence.append({"kind": "참가자격", "location": location,
                         "excerpt": _quote(text[heading.start():end])[:MAX_QUALIFICATION_QUOTE],
                         "scope": "참가자격 구역", "status": "검토용 근거 후보",
                         "excerpt_truncated": len(_quote(text[heading.start():end])) > MAX_QUALIFICATION_QUOTE,
                         "start": heading.start(), "end": end})
    for heading in QUALIFICATION_EN.finditer(text):
        number = heading.group('number')
        candidates = [m.start() for m in NEXT_HEADING_EN.finditer(text, heading.end())]
        if number:
            candidates.extend(m.start() for m in NEXT_HEADING.finditer(text, heading.end())
                              if int(m.group('number')) > int(number))
        end = min(candidates) if candidates else len(text)
        qualifications.append((heading.start(), end))
        evidence.append(dict(kind='참가자격', location=location,
            excerpt=_quote(text[heading.start():end])[:MAX_QUALIFICATION_QUOTE], scope='참가자격 구역',
            status='영문 참가자격 구역·원문 검토', excerpt_truncated=len(_quote(text[heading.start():end]))>MAX_QUALIFICATION_QUOTE,
            start=heading.start(), end=end))
    for kind, pattern in PATTERNS.items():
        ends = -1
        for match in pattern.finditer(text):
            if match.start() < ends:
                continue
            start, end = max(0, match.start() - 160), min(len(text), match.end() + 500)
            section = next(((a,b) for a,b in qualifications if a <= match.start() < b), None)
            if section:
                start, end = max(start, section[0]), min(end, section[1])
            ends = end
            excerpt = _quote(text[start:end])
            evidence.append({"kind": kind, "location": location, "excerpt": excerpt,
                             "status": "검토용 근거 후보",
                             "scope": "참가자격 구역" if section else "문서 내 참고 언급",
                             "start": start, "end": end})
            if sum(e["kind"] == kind for e in evidence) >= 8:
                break
    for start, end in qualifications:
        for match in OTHER_REQUIREMENT.finditer(text, start, end):
            a, b = max(start, match.start() - 100), min(end, match.end() + 400)
            if any(e["kind"] == "기타 참가조건" and e["start"] <= match.start() < e["end"] for e in evidence):
                continue
            evidence.append(dict(kind="기타 참가조건", location=location, excerpt=_quote(text[a:b]),
                                 scope="참가자격 구역", status="검토용 근거 후보", start=a, end=b))
    return evidence


def _hwp_text(data: bytes) -> str:
    """HWP 5 PARA_TEXT. 제어문자 payload를 건너뛰고 본문만 보존한다."""
    if len(data) % 2:
        raise DocumentReadError('text_encoding')
    result, offset = [], 0
    extended = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
    while offset + 2 <= len(data):
        code = struct.unpack_from("<H", data, offset)[0]
        if code in extended:
            if offset + 16 > len(data):
                raise DocumentReadError('damaged_document')
            result.append(" ")
            offset += 16
        else:
            result.append(chr(code) if code >= 32 else "\n" if code in {10, 13} else " ")
            offset += 2
    # UTF-16의 서로게이트 쌍은 한 문자로 복원한다. 잘못된 쌍을 지우거나 추정하지 않는다.
    try:
        return "".join(result).encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='strict')
    except UnicodeError:
        raise DocumentReadError('text_encoding') from None


def _hwp_section(data: bytes) -> str:
    offset, paragraphs = 0, []
    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError("손상된 HWP 레코드입니다.")
        header = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        tag, size = header & 0x3ff, (header >> 20) & 0xfff
        if size == 0xfff:
            if offset + 4 > len(data):
                raise ValueError("손상된 HWP 길이입니다.")
            size = struct.unpack_from("<I", data, offset)[0]
            offset += 4
        if offset + size > len(data):
            raise ValueError("손상된 HWP 본문입니다.")
        if tag == 67:
            paragraphs.append(_hwp_text(data[offset:offset + size]))
        offset += size
    return "\n".join(paragraphs)


def _html_sections(blob: bytes):
    """HTML 공고 첨부만 평문으로 읽는다. 스크립트·외부 자원은 실행하지 않는다."""
    if len(blob) > 2 * 1024 * 1024:
        raise ValueError("HTML 첨부 본문 크기 한도를 초과했습니다.")
    if blob.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = blob.decode('utf-16', errors='strict')
    else:
        declared = re.search(br'charset\s*=\s*["\x27]?([a-zA-Z0-9_-]+)', blob[:8192], re.I)
        codecs = {'utf-8': 'utf-8-sig', 'utf8': 'utf-8-sig', 'euc-kr': 'cp949',
                  'cp949': 'cp949', 'ks_c_5601-1987': 'cp949', 'windows-1252': 'cp1252',
                  'iso-8859-1': 'latin1'}
        if declared:
            encoding = codecs.get(declared.group(1).decode('ascii').lower())
            if not encoding:
                raise ValueError("HTML 첨부 문자 인코딩 확인이 필요합니다.")
            text = blob.decode(encoding, errors='strict')
        else:
            try:
                text = blob.decode('utf-8-sig', errors='strict')
            except UnicodeDecodeError:
                text = blob.decode('cp949', errors='strict')
    if not re.search(r'<(?:html|head|body|div|p|table|h[1-6])\b', text[:8192], re.I):
        raise ValueError("HTML 첨부 문서 구조를 확인할 수 없습니다.")
    if re.search(r'<!ENTITY\b', text, re.I):
        raise ValueError("HTML 첨부의 엔티티 선언은 처리하지 않습니다.")

    class TextOnly(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts, self.hidden, self.length = [], [], 0

        def handle_starttag(self, tag, attrs):
            if tag in {'script', 'style', 'noscript', 'iframe', 'object', 'template'}:
                self.hidden.append(tag)
            if not self.hidden and tag in {'p', 'div', 'br', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                self.parts.append('\n')
            elif not self.hidden and tag in {'td', 'th'}:
                self.parts.append(' ')

        def handle_endtag(self, tag):
            if self.hidden:
                if tag == self.hidden[-1]:
                    self.hidden.pop()
                return
            if tag in {'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                self.parts.append('\n')

        def handle_data(self, value):
            if not self.hidden:
                self.length += len(value)
                if self.length > MAX_TEXT:
                    raise ValueError("HTML 첨부 텍스트 한도를 초과했습니다.")
                self.parts.append(value)

    parser = TextOnly()
    parser.feed(text)
    parser.close()
    content = '\n'.join(_quote(line) for line in ''.join(parser.parts).splitlines() if line.strip())
    if not content:
        raise ValueError("HTML 첨부에 읽을 수 있는 본문이 없습니다.")
    if re.fullmatch(r'(?:로그인|login|sign in)', content, re.I) or re.search(r'(?:access denied|request rejected|request blocked|captcha|접근이?\s*(?:차단|거부)|로그인이?\s*필요)', content, re.I):
        raise ValueError("첨부 대신 접근 제한 안내가 반환되었습니다. 우회하지 않고 수동 확인합니다.")
    sections = [('HTML 본문', content)]
    if re.search(r'<img\b', text, re.I):
        sections.append(('HTML 내부 이미지 · 미확인·수동 대조 필요', ''))
    return 'HTML', sections


def document_sections(blob: bytes, _archive_depth: int = 0, _inventory=None) -> tuple[str, list[tuple[str, str]]]:
    """형식은 확장자가 아닌 매직·내부 구조로 확인한다. HWP(X)는 구역, PDF는 페이지."""
    if len(blob) > MAX_BYTES:
        raise ValueError("첨부 파일은 30 MiB까지 확인합니다.")
    # 실제 공개 ZIP의 .hwp 3개에서 확인한 암호화 헤더. 보호 우회 없음.
    if blob.startswith((b'\x9b DRMONE', b'<DOCUMENTSAFER_0>\x00')):
        raise DocumentReadError('protected_document')
    sections = []
    xml_prefix=blob[:8192].removeprefix(b'\xef\xbb\xbf').lstrip()
    if (xml_prefix.startswith(b'<?xml') or xml_prefix.startswith(b'<HWPML')) and re.search(br'<HWPML\b',xml_prefix):
        from service.requirement_hwpml import hwpml_sections
        return 'HWPML',hwpml_sections(blob)
    if blob.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')):
        from PIL import Image
        from service.requirement_ocr import MAX_PIXELS, recognize
        with Image.open(BytesIO(blob)) as image:
            if image.width * image.height > MAX_PIXELS or getattr(image,'n_frames',1)!=1:
                raise ValueError('OCR 이미지 크기/프레임 한도·수동 확인 필요')
            ocr=recognize(image,timeout=8)
        location=f"이미지 · OCR 검토(신뢰도 {ocr['mean_confidence']}·낮은 점수 {ocr['low_confidence_words']}어절)"
        return 'IMAGE',[(location,ocr['text'])]
    if blob.startswith(b"%PDF-"):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(blob), strict=False)
        if reader.is_encrypted:
            raise ValueError("암호화 PDF는 수동 확인이 필요합니다.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"{MAX_PDF_PAGES}페이지를 초과한 PDF는 수동 확인이 필요합니다.")
        ocr_deadline = time.monotonic() + 14
        ocr_count = 0
        decoded_bytes = 0
        for i, page in enumerate(reader.pages, 1):
            content = page.get_contents()
            if content is not None:
                size = len(content.get_data())
                if size > 8 * 1024 * 1024:
                    raise ValueError("PDF 페이지 처리 한도를 초과했습니다.")
                decoded_bytes += size
                if decoded_bytes > MAX_EXPANDED:
                    raise ValueError("PDF 전체 본문 압축 해제 한도를 초과했습니다.")
        # 긴 PDF는 기존 문자 추출이 실제 640쪽에서65초를 초과했다.
        # 압축 해제 한도를 먼저 검사한 뒤 이미 OCR에 쓰는 PDFium으로만 텍스트를 읽는다.
        fast_texts = _long_pdf_texts(blob, len(reader.pages)) if len(reader.pages) > FAST_PDF_THRESHOLD else None
        text_chars = 0
        for i, page in enumerate(reader.pages, 1):
            text = fast_texts[i-1] if fast_texts is not None else (page.extract_text() or "")
            text_chars += len(text)
            if text_chars > MAX_TEXT:
                raise ValueError("PDF 전체 텍스트 한도를 초과했습니다.")
            location = f"{i}페이지"
            if len(re.sub(r"\s", "", text)) < 40:
                from service.requirement_ocr import render_page, recognize, MAX_OCR_PAGES
                remaining = ocr_deadline - time.monotonic()
                if ocr_count < MAX_OCR_PAGES and remaining > 1:
                    try:
                        ocr_count += 1
                        ocr = recognize(render_page(blob, i - 1), timeout=min(8, remaining))
                        text = text + "\n" + ocr['text']
                        location += f" · OCR 검토(신뢰도 {ocr['mean_confidence']}·낮은 점수 {ocr['low_confidence_words']}어절)"
                    except Exception:
                        location += " · OCR 읽기 실패·수동 확인 필요"
                else:
                    location += " · OCR 페이지·시간 한도·수동 확인 필요"
            sections.append((location, text))
        return "PDF", sections
    if blob.startswith(b"PK"):
        with ZipFile(BytesIO(blob)) as archive:
            entries = archive.infolist()
            if len(entries) > 2048 or sum(e.file_size for e in entries) > MAX_EXPANDED:
                raise ValueError("첨부 압축 해제 한도를 초과했습니다.")
            if len({e.filename for e in entries}) != len(entries):
                raise ValueError("중복 이름이 있는 ZIP은 수동 확인이 필요합니다.")
            if 'word/document.xml' in archive.namelist():
                if any('vbaproject' in name.lower() for name in archive.namelist()):
                    raise ValueError("매크로 포함 문서는 수동 확인이 필요합니다.")
                names = [name for name in archive.namelist() if re.fullmatch(r"word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml", name)]
                for name in sorted(names, key=lambda name: name != 'word/document.xml'):
                    if archive.getinfo(name).file_size > 8 * 1024 * 1024:
                        raise ValueError("DOCX 본문 크기 한도를 초과했습니다.")
                    xml = archive.read(name)
                    safe_xml = xml.replace(b'\x00',b'').upper()
                    if b"<!DOCTYPE" in safe_xml or b"<!ENTITY" in safe_xml:
                        raise ValueError("DTD·엔티티가 포함된 XML은 처리하지 않습니다.")
                    root = ET.fromstring(xml)
                    sections.append((name, '\n'.join(_paragraph_text(p) for p in root.iter() if p.tag.rsplit('}', 1)[-1] == 'p')))
                if any(name.startswith('word/media/') for name in archive.namelist()):
                    sections.append(('DOCX 내부 이미지 · 미확인·수동 대조 필요', ''))
                return "DOCX", sections
            if 'ppt/presentation.xml' in archive.namelist():
                from service.requirement_presentation import presentation_sections
                return 'PPTX', presentation_sections(archive)
            if 'xl/workbook.xml' in archive.namelist():
                if any('vbaproject' in name.lower() for name in archive.namelist()):
                    raise ValueError("매크로 포함 통합문서는 수동 확인이 필요합니다.")
                return "XLSX", _xlsx_sections(archive)
            names = sorted(e.filename for e in entries if re.fullmatch(r"Contents/section\d+\.xml", e.filename))
            if not names:
                if _archive_depth:
                    raise ValueError("중첩 ZIP은 수동 확인이 필요합니다.")
                if len({e.filename for e in entries}) != len(entries):
                    raise ValueError("중복 이름이 있는 ZIP은 수동 확인이 필요합니다.")
                documents = [e for e in entries if not e.is_dir() and re.search(r"\.(?:pdf|hwp|hwpx|docx|pptx|xlsx|xls|cell|png|jpe?g|html?)$", e.filename, re.I)]
                if not documents:
                    raise ValueError("지원하지 않는 ZIP 문서 구성입니다. 내부 파일 형식 확인이 필요합니다.")
                # 규격서가 많아도 원본 공고문까지 전부 거부하지 않는다.
                priority = re.compile(r'공고|입찰|invitation|\bbid\b|\bifb\b', re.I)
                documents.sort(key=lambda entry: not bool(priority.search(entry.filename)))
                pending = documents[MAX_ARCHIVE_DOCUMENTS:]
                documents = documents[:MAX_ARCHIVE_DOCUMENTS]
                if pending and _inventory is None:
                    raise ValueError('ZIP 문서 수 한도 초과·미열람 목록을 제공하는 추출 경로로 확인해야 합니다.')
                if any(e.flag_bits & 1 for e in documents):
                    raise ValueError("암호화 ZIP 문서는 수동 확인이 필요합니다.")
                if any(e.file_size > MAX_BYTES for e in documents):
                    raise ValueError("ZIP 내부 문서 크기 한도를 초과했습니다.")
                inventory = _inventory if _inventory is not None else []
                for entry in pending:
                    inventory.append(dict(name=entry.filename, status='미열람·ZIP 문서 수 한도', format=''))
                for entry in entries:
                    if not entry.is_dir() and entry not in documents and entry not in pending:
                        inventory.append(dict(name=entry.filename, status="미지원·미열람", format=""))
                for i, entry in enumerate(documents, 1):
                    try:
                        child_format, child = document_sections(archive.read(entry), _archive_depth=1)
                        # 경로는 표시에만 사용하고 디스크에는 압축을 풀지 않는다.
                        sections.extend((f"파일 {i} · {entry.filename} › {location}", text) for location, text in child)
                        status = "읽기 완료" if any(text.strip() for _, text in child) else "텍스트 없음·수동 확인 필요"
                        if any(re.search(r"OCR|미확인|미열람|한도", location) for location, _ in child):
                            status = "읽기 일부 완료·OCR/내부 이미지 대조 필요"
                        inventory.append(dict(name=entry.filename, format=child_format, status=status))
                    except ValueError as error:
                        if _inventory is None:
                            raise  # 기존 document_sections 직접 호출의 엄격 검사 유지.
                        inventory.append(dict(name=entry.filename, format="", status="읽기 실패·수동 확인 필요",
                                              error_code=document_error_code(error)))
                        sections.append((f"파일 {i} · {entry.filename} › 읽기 실패·미확인", ""))
                if not any(text.strip() for _, text in sections) and _inventory is None:
                    raise ValueError("ZIP 안의 지원 문서 본문을 읽지 못했습니다.")
                return "ZIP", sections
            for name in names:
                if archive.getinfo(name).file_size > 8 * 1024 * 1024:
                    raise ValueError("HWPX 구역 크기 한도를 초과했습니다.")
                xml = archive.read(name)
                safe_xml = xml.replace(b'\x00',b'').upper()
                if b"<!DOCTYPE" in safe_xml or b"<!ENTITY" in safe_xml:
                    raise ValueError("DTD·엔티티가 포함된 XML은 처리하지 않습니다.")
                root = ET.fromstring(xml)
                paragraphs = [_paragraph_text(p)
                              for p in root.iter() if p.tag.rsplit('}', 1)[-1] == "p"]
                sections.append((name, "\n".join(paragraphs)))
        return "HWPX", sections
    if blob.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        import olefile
        with olefile.OleFileIO(BytesIO(blob)) as compound:
            is_workbook = compound.exists('Workbook') or compound.exists('Book')
            is_word = compound.exists('WordDocument')
            is_hwp = compound.exists('FileHeader')
        if is_word and not is_hwp and not is_workbook:
            raise DocumentReadError('unsupported_format')
        if not is_workbook and not is_hwp:
            raise DocumentReadError('unsupported_format')
        if is_workbook:
            import xlrd
            try:
                workbook = xlrd.open_workbook(file_contents=blob, on_demand=True)
            except xlrd.biffh.XLRDError as error:
                # 실제 한셀 OLE는 Workbook이 있어도 BIFF 엑셀이 아닐 수 있다.
                if str(error) == "Can't determine file's BIFF version":
                    raise DocumentReadError('unsupported_format') from None
                raise
            try:
                if workbook.nsheets > 50:
                    raise ValueError("시트 처리 한도를 초과했습니다.")
                for sheet in workbook.sheets():
                    if sheet.nrows * sheet.ncols > 100_000:
                        raise ValueError("셀 처리 한도를 초과했습니다.")
                    for i in range(sheet.nrows):
                        text = ' '.join(str(v) for v in sheet.row_values(i) if v != '')
                        if text.strip():
                            sections.append((f"{sheet.name} · {i + 1}행", text))
            finally:
                workbook.release_resources()
            return "XLS", sections
        with olefile.OleFileIO(BytesIO(blob)) as document:
            header = document.openstream("FileHeader").read(256)
            if not header.startswith(b"HWP Document File") or len(header) < 40:
                raise ValueError("HWP 5 형식이 아닙니다.")
            flags = struct.unpack_from("<I", header, 36)[0]
            if flags & 6:
                raise ValueError("암호·배포용 HWP는 수동 확인이 필요합니다.")
            total = 0
            for name in sorted(document.listdir()):
                if len(name) != 2 or name[0] != "BodyText" or not re.fullmatch(r"Section\d+", name[1]):
                    continue
                data = document.openstream(name).read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("HWP 구역 크기 한도를 초과했습니다.")
                if flags & 1:
                    decoder = zlib.decompressobj(-15)
                    data = decoder.decompress(data, MAX_EXPANDED - total + 1)
                    if not decoder.eof:
                        raise ValueError("HWP 압축이 손상되었거나 해제 한도를 초과했습니다.")
                total += len(data)
                if total > MAX_EXPANDED:
                    raise ValueError("HWP 해제 한도를 초과했습니다.")
                sections.append(("/".join(name), _hwp_section(data)))
        return "HWP", sections
    # 바이너리 문서 안의 HTML 문자열을 문서 형식으로 오인하지 않는다.
    if re.search(br'<(?:html|head|body|div|p|table|h[1-6])\b', blob[:8192], re.I) or blob.startswith((b'\xff\xfe', b'\xfe\xff')):
        return _html_sections(blob)
    raise ValueError("지원하지 않는 첨부 형식입니다. PDF·HWP 5·HWPX·DOCX·XLS(X)·PNG/JPEG·HTML만 확인합니다.")


def _xlsx_sections(archive):
    """서식이 확장한 행렬 대신 실제 값 셀만 읽는다. 수식/외부 연결은 실행하지 않는다."""
    def xml(name):
        if archive.getinfo(name).file_size > 8 * 1024 * 1024:
            raise ValueError('엑셀 XML 크기 한도를 초과했습니다.')
        content = archive.read(name)
        safe_xml=content.replace(b'\x00',b'').upper()
        if b'<!DOCTYPE' in safe_xml or b'<!ENTITY' in safe_xml:
            raise ValueError('DTD·엔티티가 포함된 XML은 처리하지 않습니다.')
        try:
            return ET.fromstring(content)
        except ET.ParseError:
            raise ValueError('엑셀 XML 형식 오류입니다.') from None

    shared, text_size = [], 0
    if 'xl/sharedStrings.xml' in archive.namelist():
        for item in xml('xl/sharedStrings.xml'):
            value = ''.join(node.text or '' for node in item.iter() if node.tag.rsplit('}',1)[-1]=='t')
            text_size += len(value)
            shared.append(value)
            if len(shared)>100_000 or text_size>MAX_TEXT:
                raise ValueError('엑셀 문자열 처리 한도를 초과했습니다.')
    relationships = {item.attrib.get('Id'): item.attrib.get('Target')
                     for item in xml('xl/_rels/workbook.xml.rels') if item.attrib.get('TargetMode') != 'External'}
    sheets = [item for item in xml('xl/workbook.xml').iter() if item.tag.rsplit('}',1)[-1]=='sheet']
    if len(sheets)>50:
        raise ValueError('시트 처리 한도를 초과했습니다.')
    sections, values_count = [], 0
    for sheet in sheets:
        rid = next((value for key,value in sheet.attrib.items() if key.rsplit('}',1)[-1]=='id'),None)
        target = relationships.get(rid) or ''
        target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl',target))
        if not re.fullmatch(r'xl/worksheets/[^/]+\.xml',target) or target not in archive.namelist():
            raise ValueError('시트 경로/외부 참조 확인이 필요합니다.')
        for index,row in enumerate((item for item in xml(target).iter() if item.tag.rsplit('}',1)[-1]=='row'),1):
            number = row.attrib.get('r',str(index))
            if not number.isdigit() or len(number)>7 or not 1<=int(number)<=1048576:
                raise ValueError('엑셀 행 번호 확인이 필요합니다.')
            values=[]
            for cell in row:
                if cell.tag.rsplit('}',1)[-1]!='c':
                    continue
                children={item.tag.rsplit('}',1)[-1]:item for item in cell}
                if not any(key in children for key in ('f','v','is')):
                    continue  # 서식만 존재하는 빈 셀은 텍스트 처리 한도에 포함하지 않는다.
                values_count+=1
                if values_count>100_000:
                    raise ValueError('셀 처리 한도를 초과했습니다.')
                if 'f' in children:
                    continue  # 계산된 캐시 값도 자격 문장으로 사용하지 않는다.
                value=children['v'].text or '' if 'v' in children else ''
                if cell.attrib.get('t')=='s':
                    if not value.isdigit() or int(value)>=len(shared):
                        raise ValueError('엑셀 공유 문자열 번호 오류입니다.')
                    value=shared[int(value)]
                elif cell.attrib.get('t')=='inlineStr':
                    value=''.join(item.text or '' for item in cell.iter() if item.tag.rsplit('}',1)[-1]=='t')
                if value.strip():
                    values.append(value)
            if values:
                sections.append((f"{sheet.attrib.get('name','이름 미제공')} · {number}행",' '.join(values)))
    return sections


def _paragraph_text(paragraph) -> str:
    """표 셀의 중첩 문단은 각자 읽는다. 바깥 문단에서 다시 읽어 중복시키지 않는다."""
    parts = []
    def visit(node):
        for child in node:
            tag = child.tag.rsplit('}', 1)[-1]
            if tag == "p":
                continue
            if tag == "t":
                parts.append(child.text or "")
            elif tag in {"br", "cr"}:
                parts.append('\n')
            elif tag == "tab":
                parts.append(' ')
            visit(child)
    visit(paragraph)
    return "".join(parts)


def _long_pdf_texts(blob, expected_pages):
    """공식 PDFium Unicode API. 페이지 순서 보존·스크립트/폼 실행 없음."""
    import pypdfium2 as pdfium
    texts, total = [], 0
    with pdfium.PdfDocument(blob) as document:
        if len(document) != expected_pages:
            raise ValueError('PDF 읽기 간 페이지 수 불일치·수동 확인 필요')
        for index in range(expected_pages):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    if textpage.count_chars() > MAX_TEXT - total:
                        raise ValueError('PDF 전체 텍스트 한도를 초과했습니다.')
                    text = textpage.get_text_bounded(errors='strict').replace('\r\n', '\n')
                finally:
                    textpage.close()
            finally:
                page.close()
            total += len(text)
            if total > MAX_TEXT:
                raise ValueError('PDF 전체 텍스트 한도를 초과했습니다.')
            texts.append(text)
    return texts


def extract_document(blob: bytes) -> dict:
    inventory = []
    fmt, sections = document_sections(blob, _inventory=inventory) if blob.startswith(b'PK') else document_sections(blob)
    if sum(len(text) for _, text in sections) > MAX_TEXT:
        raise ValueError("첨부 전체 텍스트 한도를 초과했습니다.")
    groups = {}
    for location, text in sections:
        # ZIP 안의 서로 다른 파일로 참가자격 구역이 이어지는 것을 막는다.
        group = location.split(" · ", 1)[0] if fmt in {"ZIP", "XLS", "XLSX"} else "본문"
        if fmt == 'ZIP':
            sheet = re.search(r" › (.+) · \d+행", location)
            if sheet:
                group += '|' + sheet.group(1)  # ZIP 내부 엑셀도 시트 사이에 자격 구역을 이어 붙이지 않는다.
        groups.setdefault(group, []).append((location, text))
    evidence = [e for group in groups.values() for e in _sections_evidence(group)]
    result = {"format": fmt, "sha256": hashlib.sha256(blob).hexdigest(), "evidence": evidence[:120],
            "evidence_truncated": len(evidence) > 120,
            "ocr_pages": [location for location, _ in sections if "OCR" in location],
            "status": "근거 후보 발견" if evidence else "텍스트 근거 미발견",
            "text_available": any(text.strip() for _, text in sections),
            "document_gaps": [location for location, _ in sections if re.search(r"미확인|미열람|한도|읽기 실패", location)]}
    # 제목에서 취소 공고임이 확인되어도 API 현재 상태/이전 차수 조건을 추정하지 않는다.
    if any(re.search(r'^.{0,100}(?:취소\s*공고|cancellation\s+(?:of\s+)?(?:bid\s+)?notice)\s*$', line, re.I)
           for _, text in sections for line in text.splitlines()[:5]):
        result['document_notices'] = ['취소 공고 제목 확인·현재 공고 상태 별도 대조 필요']
    if fmt == 'ZIP':
        result.update(archive_inventory=inventory,
                      archive_complete=bool(inventory) and all(item['status'] == '읽기 완료' for item in inventory))
    return result


def _sections_evidence(sections):
    # 같은 파일의 페이지 사이 구역만 이어 분석하고 인용 위치를 연결한다.
    boundaries, offset = [], 0
    for location, text in sections:
        boundaries.append((offset, location))
        offset += len(text) + 1
    combined = "\n".join(text for _, text in sections)
    evidence = evidence_from_text(combined, "본문")
    for e in evidence:
        start, end = e.pop("start"), e.pop("end")
        first = next((location for pos, location in reversed(boundaries) if pos <= start), "본문")
        last = next((location for pos, location in reversed(boundaries) if pos < end), first)
        e["location"] = first if first == last else f"{first} ~ {last}"
        e["method"] = "ocr" if "OCR" in e["location"] else "text"
        if e['method'] == 'ocr':
            e['status'] = 'OCR 근거 후보·원본 이미지 대조 필요'
    return evidence


def extract_bounded(blob: bytes, timeout: float = 20) -> dict:
    """읽기 전용 별도 프로세스로 처리하고 시간 초과 시 종료한다. 원본을 디스크에 저장하지 않는다."""
    if len(blob) > MAX_BYTES:
        raise ValueError("첨부 크기 제한을 초과했습니다.")
    # multiprocessing spawn은 Streamlit/AppTest의 __main__을 재실행할 수 있다.
    # 고정된 파서만 별도 Python에서 실행하며 첨부는 stdin 데이터로 전달한다.
    script = ("import sys,json\nsys.path.insert(0,sys.argv[1])\n"
              "from service.requirement_documents import extract_document,document_error_code\n"
              "try:\n result=extract_document(sys.stdin.buffer.read())\n"
              "except Exception as error:\n result={'document_error':document_error_code(error)}\n"
              # 파서의 결과를 ASCII JSON으로 전달하고 부모에서 원래 문자를 복구한다.
              # Windows 파이프 문자 인코딩 오류로 읽은 근거 전체가 버려지는 것을 막는다.
              "sys.stdout.buffer.write(json.dumps(result,ensure_ascii=True).encode('ascii'))")
    try:
        response = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve().parents[1])],
                                  input=blob, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=True,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result = json.loads(response.stdout)
        if 'document_error' in result:
            raise DocumentReadError(result['document_error'])
        return result
    except DocumentReadError:
        raise
    except subprocess.TimeoutExpired:
        raise DocumentReadError('processing_limit') from None
    except Exception:
        raise DocumentReadError('read_failure') from None
