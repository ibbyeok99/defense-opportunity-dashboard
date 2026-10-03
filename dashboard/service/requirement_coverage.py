"""읽은 범위와 조건 발견 여부를 분리한다. 미탐지를 제한 없음으로 바꾸지 않는다."""
import re


def coverage(result):
    sources = result.get("sources", [])
    attachments = [s for s in sources if s.get("name") not in {"공식 API 면허", "공식 API 지역", "원문 페이지"}]
    pages = [s for s in sources if s.get("name") == "원문 페이지"]
    gaps = []
    if not pages or any(re.search(r"실패|미확인|미열람", s.get("status", "")) for s in pages):
        gaps.append("원문 페이지 본문 미확인")
    if not result.get("attachment_inventory_complete"):
        gaps.append("이전 조회의 전체 첨부 목록 미기록")
    if not attachments:
        gaps.append("확인 가능한 첨부 없음")
    for source in attachments:
        status = source.get("status", "")
        if re.search(r"실패|한도|미열람|미확인|텍스트 없음", status):
            gaps.append("첨부 읽기 미완료")
        if "OCR" in status or source.get("ocr_pages"):
            gaps.append("OCR 원본 대조 필요")
        if source.get("format") == "ZIP" and not source.get("archive_complete", False):
            gaps.append("ZIP 안의 미지원·미확인 파일 가능")
        if source.get("evidence_truncated"):
            gaps.append("발췌 한도·전체 요건 검토 필요")
        if source.get("document_gaps"):
            gaps.append("문서 내부 이미지·읽기 범위 대조 필요")
    if any("한도" in w and "첨부" in w for w in result.get("warnings", [])):
        gaps.append("첨부 확인 한도 도달")
    if not any(e.get("scope") == "참가자격 구역" for e in result.get("evidence", [])):
        gaps.append("참가자격 구역 미탐지")
    if any(e.get('excerpt_truncated') for e in result.get('evidence', [])):
        gaps.append("참가자격 발췌 길이 한도")
    gaps = list(dict.fromkeys(gaps))
    return {"schema": "requirement-coverage-v1", "status": "자료 확인 미완료" if gaps else "제공 자료 읽기 완료·내용 검토 필요",
            "gaps": gaps, "attachments_listed": len(attachments),
            "attachments_read": sum(bool(s.get("format")) and not re.search(r"실패|미열람|텍스트 없음", s.get("status", "")) for s in attachments),
            "absence_proven": False}
