"""참가자격 발췌의 표시용 분류. 원문/회사 판정 불변·네트워크 호출 없음."""
import re

from service.requirement_structure import SIZE_PATTERNS, REGISTRATION_OPTIONS, factory_registrations, other_categories

PRODUCT = re.compile(r'(?:세부\s*품명\s*번호|세부\s*품명\s*분류\s*번호)\s*(?:10\s*자리)?\s*[:：]?\s*'
                     r'(?P<code>\d{10})(?!\d)(?:\s*[（(](?P<name>[^()（）\n]{1,60})[）)])?')


def _explicit_summary(category, excerpts):
    """명시된 증빙·기한·불허만 짧게 옮긴다. 예외/부정/상충은 단정하지 않는다."""
    text = '\n'.join(excerpts)
    compact = re.sub(r'\s+', '', text)
    # 예외·면제·부정이 연결된 증명서는 전부 필요하다고 요약하지 않는다.
    ambiguous = bool(re.search(r'다만|예외|제외|면제|아니|않아도|불필요|필요없|해당하지', compact))
    if category == '공동수급·하도급':
        conclusions = []
        for sentence in excerpts:
            value = re.sub(r'\s+|[.。]', '', sentence).strip('-·ㆍ①②③④⑤⑥⑦⑧⑨⑩')
            value = re.sub(r'^(?:[가-힣]|\d+)[)．]', '', value)
            match = re.fullmatch(r'(공동수급(?:및|과|·|ㆍ|/)하도급|공동수급|하도급)(?:은|는|을|를)?'
                                 r'(허용하지않음|불허|허용안함|금지|허용|가능)', value)
            if match:
                subject = '공동수급·하도급' if '하도급' in match[1] and '공동수급' in match[1] else match[1]
                conclusions.append(subject + (' 허용' if match[2] in {'허용','가능'} else ' 불허'))
        # 다른 연결 문장/예외를 버리지 않는다. 같은 문장의 중복만 허용한다.
        if conclusions and len(set(conclusions)) == 1 and not ambiguous and len(conclusions) == len(excerpts):
            return conclusions[0]
        return None
    if category not in {'직접생산', '기업 규모', '확인서·인증'}:
        return None
    certificate = None
    if category == '직접생산':
        certificate = '직접생산확인증명서'
    else:
        match = re.search(r'(소기업|중소기업)[·ㆍ‧/\-]소상공인확인서|중소기업확인서', compact)
        if match:
            certificate = re.sub(r'[ㆍ‧/\-]', '·', match[0])
    if not certificate:
        return None
    # 법령의 문서명 언급만으로 의무를 만들지 않는다.
    required = any(re.search(r'(?:확인서|확인증명서).{0,1000}(?:소지한자|소지하여야|보유한자|보유하여야|제출하여야|제출해야)',
                            re.sub(r'\s+', '', sentence)) for sentence in excerpts)
    if not required:
        return None
    parts = [certificate + (' 명시 · 적용 대상·예외 확인 필요' if ambiguous else ' 보유 요구')]
    if category == '직접생산':
        products = list(re.finditer(r'품명\s*[:：]\s*([^()（）\n]{1,80}?)\s*[,，]\s*품번\s*[:：]\s*(\d{10})(?!\d)', text))
        if len({product[2] for product in products}) > 1:
            return None  # 여러 품목의 AND/OR 관계를 하나로 축약하지 않는다.
        product = products[0] if products else None
        if product:
            name = product[1].strip()
            if not re.search(r'https?://|[<>]', name, re.I):
                parts.append(name + ' (' + product[2] + ')')
    for label, pattern in (
        ('발급: 전자입찰서 제출마감일 전일까지', r'전자입찰서제출마감일전일까지발급'),
        ('발급: 입찰참가자격 등록마감일까지', r'입찰참가자격등록마감일까지발급'),
    ):
        if re.search(pattern, compact):
            parts.append(label if not ambiguous else label.replace('발급:', '발급 기준 문구:'))
    if re.search(r'유효기간내에?있어야', compact):
        parts.append('유효기간 내')
    if re.search(r'공공구매.{0,80}확인이안될경우입찰참가자격이없', compact):
        parts.append('공공구매정보망에서 확인 가능해야 함')
    return ' · '.join(parts)


def _summary(category, excerpts, *, allow_explicit=True):
    explicit = _explicit_summary(category, excerpts) if allow_explicit else None
    if explicit:
        return explicit
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
    from service.notice_date_policy import cancelled
    if cancelled(result):
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
        uncertain = any(e['method'] == 'ocr' or e['truncated'] for e in entry['evidence'])
        entry['summary'] = _summary(entry['category'], entry['excerpts'], allow_explicit=not uncertain)
    order = ['제조물품 등록', '직접생산', '기업 규모', '확인서·인증']
    return sorted(entries.values(), key=lambda entry: (order.index(entry['category'])
                  if entry['category'] in order else len(order)))
