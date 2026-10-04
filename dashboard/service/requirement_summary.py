"""참가자격 발췌의 표시용 분류. 원문/회사 판정 불변·네트워크 호출 없음."""
import re

from service.requirement_structure import SIZE_PATTERNS, REGISTRATION_OPTIONS, factory_registrations, other_categories

PRODUCT = re.compile(r'(?:세부\s*품명\s*번호|세부\s*품명\s*분류\s*번호)\s*(?:10\s*자리)?\s*[:：]?\s*'
                     r'(?P<code>\d{10})(?!\d)(?:\s*[（(](?P<name>[^()（）\n]{1,60})[）)])?')


def _summary(category, excerpts):
    text = '\n'.join(excerpts)
    if category == '제조물품 등록':
        matches = list(PRODUCT.finditer(text))
        codes = list(dict.fromkeys(match['code'] for match in matches))
        names = list(dict.fromkeys(match['name'].strip() for match in matches if match['name']))
        return ('세부품명번호 ' + ' · '.join(codes) + (' (' + ' · '.join(names) + ')' if names else '')
                + ' · 제조물품 등록 관련 자격') if codes else '제조물품 등록 관련 자격 · 세부 내용은 근거 확인'
    if category == '직접생산':
        return '직접생산' + (' 확인증명서' if re.search(r'직접\s*생산\s*확인\s*증명서', text) else '') + ' 관련 자격 · 대상·유효기간은 근거 확인'
    if category == '공장등록':
        items = factory_registrations(text)
        values = list(dict.fromkeys(f"{item['name']} ({item['code']})" for item in items))
        return ('한국표준산업분류 ' + ' · '.join(values) if values else '공장등록 관련 자격') + ' · 허용 대상·충족 방식은 근거 확인'
    if category == '기업 규모':
        values = [name for name, pattern in SIZE_PATTERNS
            if re.search(pattern, text)]
        # 법률명 속 기업명도 있을 수 있어 '허용 기업'으로 확정하지 않는다.
        return (' · '.join(values) if values else '기업 규모 관련 문장') + ' 관련 자격 · 허용 대상·예외는 근거 확인'
    if category == '확인서·인증':
        names = [name for name, pattern in [
            ('소기업·소상공인 확인서', r'(?<![가-힣])소기업\s*[·ㆍ/\-]\s*소상공인\s*확인서'),
            ('중소기업 확인서', r'중소\s*기업\s*확인서'),
            ('직접생산 확인증명서', r'직접\s*생산\s*확인\s*증명서'),
            ('공동인증서', r'공동\s*인증서')]
            if re.search(pattern, text)]
        # 이름을 확실히 분리하지 못한 인증은 특정 인증명으로 추정하지 않는다.
        return (' · '.join(names) if names else '확인서·인증·허가 관련 문장') + ' · 발급·유효 조건은 근거 확인'
    if category == '공동수급·하도급':
        # 허용/불허를 문장 전체에서 섞어 단정하지 않고 연결된 원문 검토로 남긴다.
        return '공동수급·하도급 조건 · 허용 방식·대표사·예외는 근거 확인'
    if category == '전자입찰 등록·인증':
        return '전자입찰용 인증서 관련 절차 · 발급·업체등록·기한은 근거 확인'
    if category == '입찰참가 등록':
        options = [name for name, pattern in REGISTRATION_OPTIONS if re.search(pattern, text)]
        return (' · '.join(options) if options else '입찰참가자격 등록') + ' · 충족 방식·등록 기한은 근거 확인'
    if category == '기술·공급확약':
        return '기술보유·제품공급·기술지원 확약 요건 · 제출 대상·기한은 근거 확인'
    if category == '영문 공고 참가자격':
        return '영문 참가자격 구역 확인 · 허용 대상·법령 조건은 연결된 원문 검토'
    if category == '공급자 자격·대리권':
        return '공급자·대리인 자격 및 위임장 관련 조건 · 대리 범위·제출 기한은 원문 검토'
    return category + ' 관련 문장 확인 · 대상·예외·기준일은 근거 확인'


def clean_excerpt(text):
    """장식 구분선·중복 공백만 정리한다. 숫자·부정·예외 문구는 삭제하지 않는다."""
    text = re.sub(r"[-─━_=]{5,}", " ", str(text))
    text = re.sub(r"(?=[①-⑳])", "\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def summarize_participation(result):
    """확인된 참가자격 구역만 분류한다. 조건을 확정/추론하거나 예외를 버리지 않는다.

    요약은 명시된 번호/이름 또는 분류명만 사용한다. 근거에는 정리한 전체
    발췌/위치/읽기 방식/잘림 여부를 남기며 저장 원문은 수정하지 않는다.
    기존 저장 사본의 kind/relevant 오분류에도 현재 규칙으로 다시 분류한다.
    """
    if not isinstance(result, dict):
        return []
    if result.get('projection_schema'):
        from service.requirement_projection import validate
        return [dict(item, excerpts=[], evidence=[]) for item in validate(result).get('participation_summary', [])]
    entries, seen = {}, set()
    for index, evidence in enumerate(result.get('evidence', [])):
        if evidence.get('scope') != '참가자격 구역':
            continue
        text = clean_excerpt(evidence.get('excerpt', ''))
        for sentence in re.split(r"\n|(?<=[.;。])\s+(?=[가-힣①-⑳0-9])", text):
            sentence = sentence.strip()
            if not sentence:
                continue
            labels = []
            if re.search(r'제조\s*물품|제조\s*등록', sentence):
                labels.append('제조물품 등록')
            if re.search(r'직접\s*생산', sentence):
                labels.append('직접생산')
            for category in other_categories(sentence):
                if category == '제조·직접생산·생산능력':
                    if not labels:
                        labels.append('제조·생산능력')
                else:
                    labels.append({'기업 규모·대상': '기업 규모', '인증·확인서': '확인서·인증'}.get(category, category))
            for label in labels:
                key = (label, sentence, evidence.get('source'), evidence.get('location'))
                if key in seen:
                    continue
                seen.add(key)
                entry = entries.setdefault(label, dict(category=label, excerpts=[], evidence=[]))
                if sentence not in entry['excerpts']:
                    entry['excerpts'].append(sentence)
                entry['evidence'].append(dict(evidence_id=f'e{index}', quote=sentence,
                    source=evidence.get('source', ''), location=evidence.get('location', ''),
                    method=evidence.get('method', 'text'),
                    truncated=bool(evidence.get('excerpt_truncated'))))
    for entry in entries.values():
        entry['summary'] = _summary(entry['category'], entry['excerpts'])
    order = ['제조물품 등록', '직접생산', '기업 규모', '확인서·인증']
    return sorted(entries.values(), key=lambda entry: (order.index(entry['category'])
                  if entry['category'] in order else len(order)))
