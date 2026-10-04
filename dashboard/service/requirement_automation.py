"""새 공고에도 같은 규칙을 적용하고, 자동 해석을 보류한 이유를 분리한다.

조건 존재의 추출과 기업의 참가 적격성은 별개다. 스킵은 제한 없음이 아니다.
"""
from __future__ import annotations

SCHEMA = 'requirement-automation-v1'
KNOWN_SOURCE_SKIPS = frozenset({
    'protected_document', 'unsupported_format', 'processing_limit', 'download_size_limit',
    'download_not_permitted', 'unsafe_document', 'empty_text',
})


def classify_automation(prepared):
    """이미 읽은 결과만 사용한다. 네트워크/DB 조회·본문 원문 복붙 없음."""
    from service.requirement_overlay import usable_values
    clauses = prepared.get('structured', {}).get('clauses', [])
    global_skips = []
    for source in prepared.get('sources', []):
        code = source.get('error_code')
        if code:
            global_skips.append(dict(code=code, source=source.get('name', ''),
                action='자동 읽기 스킵·상세 확인' if code in KNOWN_SOURCE_SKIPS else '새 오류·원인 점검',
                repeat_same_input=False))
        if source.get('ocr_pages') or source.get('document_gaps'):
            global_skips.append(dict(code='original_comparison_required', source=source.get('name', ''),
                                     action='원본 대조·자동 확정 스킵', repeat_same_input=False))
    fields = {}
    for kind, collection in (('license', 'licenses'), ('region', 'allowed_regions')):
        resolved = prepared.get('resolved', {}).get(kind, {})
        values = usable_values(resolved.get('values', ''))
        related = [c for c in clauses if c.get(collection)]
        reasons = []
        if resolved.get('review') == '근거 충돌':
            reasons.append('conflicting_evidence')
        if prepared.get('structured', {}).get('truncated'):
            reasons.append('clause_limit')
        if any(c.get('method') == 'ocr' for c in related):
            reasons.append('ocr_comparison_required')
        if any(c.get('logic') in {'복합·원문 검토', '그룹·충족 방식 원문 확인'} for c in related):
            reasons.append('compound_logic')
        if any(c.get('joint_bidding') or c.get('exceptions') for c in related):
            reasons.append('joint_or_exception')
        if kind == 'license' and any(v.get('name') == '명칭 미확인' for c in related for v in c.get('licenses', [])):
            reasons.append('license_name_unresolved')
        if values and resolved.get('state') == '제한있음':
            status = '조건 추출·관계 해석 보류' if reasons else '조건 추출'
        elif resolved.get('state') == '조건없음':
            status = '명시적 없음 추출'
        else:
            status = '후보 추출·자동 해석 스킵' if values else '자동 판정 스킵'
            reasons.append('candidate_not_confirmed' if values else 'no_structured_condition')
        fields[kind] = dict(status=status, values=values,
            reason_codes=list(dict.fromkeys(reasons)),
            evidence_ids=list(dict.fromkeys(c['evidence_id'] for c in related if c.get('evidence_id'))),
            requires_review=bool(resolved.get('manual', True) or reasons),
            retry='입력·읽기 규칙 변경 또는 명시적 재확인', eligibility_decided=False)
    return dict(schema=SCHEMA, fields=fields, source_skips=global_skips,
                all_requirements_confirmed=False, eligibility_decided=False)
