"""참가자격 문장의 명시적 요소만 구조화한다. 추론·법적 참가 판정은 하지 않는다."""
import re

PROVINCES = (
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시",
    "세종특별자치시", "경기도", "강원특별자치도", "강원도", "충청북도", "충청남도", "전북특별자치도",
    "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
)
OFFICE = re.compile(r"본점|본사(?!업)|주된\s*영업소|법인등기부상|참가\s*가능\s*지역")
LICENSE = re.compile(r"면허|업종|사업자|공사업|건설업|등록|신고|직접\s*생산|용역|여행업|사무소")
# OCR로 공백이 사라진 긴 문자열을 모든 위치에서 역추적하지 않는다.
# 한 단어80자/세부명80자를 넘으면 명칭을 잘라 만들지 않고 코드만 보류한다.
NAME_CODE = re.compile(r"(?<![가-힣A-Za-z])(?P<name>[가-힣A-Za-z][가-힣A-Za-z·/.-]{0,79}(?:\s+[가-힣A-Za-z·/.-]{1,80}){0,3}?)\s*[（(]\s*(?P<label>업종\s*(?:코드|번호)\s*[:：]?\s*)?(?P<code>\d{4})\s*[）)]")
NAME_DETAIL_CODE = re.compile(r"(?<![가-힣A-Za-z])(?P<name>[가-힣A-Za-z][가-힣A-Za-z·/.-]{0,79})\s*[（(]\s*(?:업종명\s*[:：]\s*)?(?P<detail>[^()（）\n]{1,80}?)\s*[,，]\s*업종\s*(?:코드|번호)\s*[:：]?\s*(?P<code>\d{4})\s*[）)]")
NAME_NESTED_CODE = re.compile(r"(?<![가-힣A-Za-z])(?P<name>[가-힣A-Za-z][가-힣A-Za-z·/.-]{0,79})\s*[（(](?P<detail>[^()（）\n]{1,80})[）)]\s*[（(]\s*(?:업종\s*(?:코드|번호)\s*[:：]?\s*)?(?P<code>\d{4})\s*[）)]")
BARE_CODE = re.compile(r"업종\s*(?:코드|번호)\s*[:：]?\s*([0-9]{4})(?![0-9])")
NAME_ONLY = re.compile(r"(?<![가-힣])(?P<name>[가-힣][가-힣·]{0,45}(?:사업자|공사업|건설업|용역업|여행업|연구용역|기술사사무소))(?!법|령|규칙)")
MANUFACTURING_PERMIT = re.compile(r"(?<![가-힣])(?P<name>[가-힣][가-힣·]{0,79}(?:\s+(?:및\s+)?[가-힣·]{1,80}){0,4}\s*제조업)\s*허가(?=를|\s|[（(]|$)")
INDUSTRY_CODE = re.compile(r"(?<!\d)(?P<code>\d{5})(?!\d)\s*[（(](?P<name>[^()（）\n]{1,80})[）)]")
JOINT = re.compile(r"공동\s*수급|공동\s*이행|분담\s*이행|대표\s*사|구성원")
EXCEPTION = re.compile(r"다만|예외|제외|면제|한하여|한해|경우")
REFERENCE = re.compile(r"공고일\s*(?:전일|전날)?|입찰\s*공고일\s*(?:전일|전날)?|개찰일\s*(?:전일|전날)?|입찰일|마감일|계약\s*체결일|등록\s*마감일|\d{4}[.년/-]\s*\d{1,2}[.월/-]\s*\d{1,2}일?")
SIZE_PATTERNS = (
    ('소기업', r'(?<![가-힣])소\s*기업'),
    ('소상공인', r'소상공인(?!\s*(?:기본법|보호|지원|시장진흥))'),
    ('중소기업', r'(?<![가-힣])중소\s*기업(?!\s*(?:기본법|제품|범위|청|부|자\s*간|공공\s*구매))'),
    ('비영리법인', r'비영리\s*법인'),
    ('적격조합', r'적격\s*조합'),
)
# 전자입찰 인증은 제품/기업 인증과 구분한다. 일반 인증명은 삭제하지 않는다.
ELECTRONIC_CERTIFICATE = re.compile(r'(?:공동|공인|전자|범용)\s*인증서|공인\s*인증기관(?:(?:으로부터|에서)?\s*인증서)?')
REGISTRATION_OPTIONS = (
    ('외자분야 등록', r'외자\s*분야\s*등록자'),
    ('동종 물품분야 등록', r'외자\s*물품.{0,80}동종.{0,80}물품\s*분야\s*등록자'),
    ('국외소재업체 등록', r'국외\s*소재\s*업체\s*등록자'),
)
PARTICIPATION_REGISTRATION = re.compile('|'.join(pattern for _, pattern in REGISTRATION_OPTIONS)
    + r'|입찰\s*참가\s*자격\s*등록\s*(?:자로서|자이어야|을\s*(?:하|필)|한\s*자|하여야)')
OTHER_RULES = {
    "기업 규모·대상": re.compile('|'.join(pattern for _, pattern in SIZE_PATTERNS)),
    "제조·직접생산·생산능력": re.compile(r"직접\s*생산|제조물품|제조업|제조\s*등록|생산\s*능력"),
    "실적": re.compile(r"납품\s*실적|수행\s*실적|사업\s*실적|실적\s*(?:제한|이상|보유)"),
    "인증·확인서": re.compile(r"인증|확인서|허가"),
    "전자입찰 등록·인증": ELECTRONIC_CERTIFICATE,
    "입찰참가 등록": PARTICIPATION_REGISTRATION,
    "공장등록": re.compile(r"공장\s*등록"),
    "지명·참가대상": re.compile(r"지명\s*경쟁|지명한|업체.{0,60}지명"),
    "보안": re.compile(r"보안|비밀\s*취급"),
    "제재·결격": re.compile(r"부정당|조세\s*포탈|참가\s*(?:자격)?\s*제한|제한\s*기간"),
    "보증": re.compile(r"보증금|보증서"),
    "공동수급·하도급": re.compile(r"공동\s*수급|공동\s*도급|공동\s*이행|분담\s*이행|하도급"),
    "기술·공급확약": re.compile(r"기술\s*보유|기술\s*지원\s*확약|제품\s*공급.{0,15}확약|제작사.{0,30}확약|공급사.{0,30}확약"),
    "영문 공고 참가자격": re.compile(r"qualifications?\s+(?:of|for)\s+bidders?|qualified\s+and\s+eligible|eligible\s+bidders?|applicable\s+laws\s+and\s+regulations", re.I),
    "공급자 자격·대리권": re.compile(r"power\s+of\s+attorney|(?:authorized|authorised)\s+(?:agent|dealer|representative)|korean\s+agent|manufacturers?['’]?s?\s+authori[sz]ation", re.I),
}


def other_categories(sentence):
    """법명/공인 전자서명 문구를 별도 분류. 혼합 문장의 다른 인증은 보존한다."""
    labels = []
    for label, pattern in OTHER_RULES.items():
        target = ELECTRONIC_CERTIFICATE.sub('', sentence) if label == '인증·확인서' else sentence
        if pattern.search(target):
            labels.append(label)
    return labels


def _name(value):
    value = re.sub(r"^.*(?:따른|따라|의한|의하여|반드시|및|또는)\s+", "", value.strip()).strip()
    value = re.sub(r"^(?:에|의|인|로|으로)\s+", "", value)
    # 평문 PDF에서 줄바꿈이 업종 앞에 붙는 실제 사례. 마감일은 업종명의 일부가 아니다.
    return value.split()[-1] if re.search(r"입찰|제출|마감|전일", value) and " " in value else value


def _logic(text):
    all_rule = bool(re.search(r"모두|전부|동시|및", text))
    any_rule = bool(re.search(r"또는|중\s*(?:하나|1)|어느\s*하나", text))
    return "복합·원문 검토" if all_rule and any_rule else "하나 충족" if any_rule else "모두 충족" if all_rule else "문장만으로 미확정"


def factory_registrations(text):
    """산업분류 5자리와 공장등록의 명시적 연결만. 면허 4자리로 변환하지 않는다."""
    anchor = re.search(r"한국\s*표준\s*산업\s*분류\s*(?:코드|번호)", text)
    if not anchor:
        return []
    segment = re.split(r"[\n;。]", text[anchor.end():anchor.end() + 500])[0]
    registration = re.search(r"공장\s*등록", segment)
    if not registration:
        return []
    return [dict(code=m['code'], name=m['name'].strip())
            for m in INDUSTRY_CODE.finditer(segment[:registration.start()])]


def structure_requirements(result):
    """각 요소에 근거 ID/문장/출처/위치 연결. 일반 언급은 자격 조건으로 승격하지 않는다."""
    clauses, seen = [], set()
    for index, evidence in enumerate(result.get("evidence", [])):
        if evidence.get('scope') == '공개 화면 구조화 조건':
            kind, name = evidence.get('kind'), evidence.get('name', '')
            if kind in {'면허', '지역'} and isinstance(name, str) and name.strip():
                code = str(evidence.get('code', ''))
                clauses.append(dict(evidence_id=f'e{index}', source=evidence.get('source', ''),
                    location=evidence.get('location', ''), quote=evidence.get('excerpt', ''),
                    licenses=[dict(name=name, code=code if re.fullmatch(r'\d{4}', code) else '')] if kind=='면허' else [],
                    allowed_regions=[name] if kind=='지역' else [], factory_registrations=[], other_requirements=[],
                    logic='그룹·충족 방식 원문 확인', group=evidence.get('group', ''), sequence=evidence.get('sequence', ''),
                    joint_bidding='', joint_rule='', exceptions='', reference_dates=[], method='public-json', requires_review=True))
                if len(clauses) >= 80:
                    return {'schema':'requirement-structure-v1', 'clauses':clauses, 'truncated':True}
            continue
        if evidence.get("scope") != "참가자격 구역" or evidence.get("relevant") is False:
            continue
        text = evidence.get("excerpt", "")
        for match in re.finditer(r"[^。;\n]+(?:[。;\n]|$)", text):
            sentence = match.group().strip()
            key = (evidence.get("source"), evidence.get("location"), sentence)
            if not sentence or key in seen:
                continue
            # 『건축공사업』(업종코드:0002), 업종명/코드 한 괄호, 중첩 괄호도
            # 같은 규칙으로 연결한다. 원래 근거 문장은 바꾸지 않는다.
            parse_text = re.sub(r'[『』「」【】]', ' ', sentence)
            licenses = []
            for pattern in (NAME_DETAIL_CODE, NAME_NESTED_CODE):
                for m in pattern.finditer(parse_text):
                    if LICENSE.search(m['name']) and re.search(r'사업|업|사무소',m['detail']):
                        licenses.append(dict(name=_name(m['name'])+'('+m['detail'].strip()+')',code=m['code']))
            for m in NAME_CODE.finditer(parse_text):
                explicit_registered_group = (re.search(r'업종\s*(?:코드|번호)',parse_text)
                    and re.search(r'등록',parse_text) and re.search(r'(?:업|기업|대학|협력단)$',m['name']))
                if (LICENSE.search(m['name']) or m['label'] or explicit_registered_group) and not any(v['code']==m['code'] for v in licenses):
                    licenses.append(dict(name=_name(m['name']),code=m['code']))
            codes = {item["code"] for item in licenses}
            licenses.extend(dict(name="명칭 미확인", code=m.group(1)) for m in BARE_CODE.finditer(sentence) if m.group(1) not in codes)
            names = {item['name'].split('(',1)[0] for item in licenses}
            for match in NAME_ONLY.finditer(sentence):
                # 코드가 없는 법정 업종도 원문 명칭만 보존한다. 비슷한 코드로 매칭하지 않는다.
                if match.group('name') not in names and re.search(r"등록|신고|면허|자격", sentence[match.end():match.end() + 120]):
                    licenses.append(dict(name=match.group('name'), code=""))
                    names.add(match.group('name'))
            for permit in MANUFACTURING_PERMIT.finditer(sentence):
                name = re.sub(r"^.*(?:따른|따라)\s+", "", permit['name'].strip()) + " 허가"
                # 대상 업종 없는 ‘제조업 허가’는 면허명으로 만들지 않는다. 원문은 기타 조건에 보존한다.
                if name == '제조업 허가':
                    continue
                # 허가에 대한 법률 소개만으로 보유 조건을 만들지 않는다.
                if name not in names and re.search(r"받은|보유|가진|소지", sentence[permit.end():permit.end() + 60]):
                    licenses.append(dict(name=name, code=""))
                    names.add(name)
            factories = factory_registrations(sentence)
            # 납품/수행 장소의 지역명은 본점 자격이 아니다. 같은 문장에서도 별도 구간을 사용한다.
            office = OFFICE.search(sentence)
            region_text = sentence[office.start():] if office else ""
            region_text = re.split(r"납품\s*장소|수행\s*장소|문의처", region_text)[0]
            regions = list(dict.fromkeys(re.findall("|".join(PROVINCES), region_text)))
            other = [dict(category=label, quote=sentence) for label in other_categories(sentence)]
            if not licenses and not regions and not other and not JOINT.search(sentence) and not EXCEPTION.search(sentence) and not REFERENCE.search(sentence):
                continue
            seen.add(key)
            clauses.append({"evidence_id": f"e{index}", "source": evidence.get("source", ""),
                            "location": evidence.get("location", ""), "quote": sentence,
                            "licenses": licenses, "allowed_regions": regions,
                            "factory_registrations": factories,
                            "other_requirements": other,
                            "logic": _logic(sentence),
                            "joint_bidding": sentence if JOINT.search(sentence) else "",
                            "joint_rule": "불허" if JOINT.search(sentence) and re.search(r"허용하지\s*않|불허|허용\s*안|금지", sentence) else "원문 검토" if JOINT.search(sentence) else "",
                            "exceptions": sentence if EXCEPTION.search(sentence) else "",
                            "reference_dates": list(dict.fromkeys(REFERENCE.findall(sentence))),
                            "method": evidence.get("method", "text"), "requires_review": True})
            if len(clauses) >= 80:
                return {"schema": "requirement-structure-v1", "clauses": clauses, "truncated": True}
    return {"schema": "requirement-structure-v1", "clauses": clauses, "truncated": False}
