"""공개 기관 표의 표시만 정리한다. 원본 판정·근거는 수정하지 않는다. Codex 2026-10-01."""

import re


def public_reason(value: str) -> str:
    """수동판정 표식은 공개용 날짜만 남긴다. 담당자 정보는 원본에 보존한다."""
    def manual_marker(match):
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", match[1])
        return f"[수동판정 {dates[-1]}]" if dates else "[수동판정]"

    text = re.sub(r"\[수동판정(?=\s|\])([^\[\]]*)\]", manual_marker, str(value))
    return re.sub(r'\[전체재검토 [0-9a-f]{32}\]', '[수동판정]', text)


def roles_label(value: str) -> str:
    return ", ".join(dict.fromkeys(part.strip() for part in str(value).split("|") if part.strip()))


def reason_label(value: str) -> str:
    """대장에 기록된 근거의 표현만 변환한다. 새로운 사실·확정 판정을 만들지 않는다."""
    text = " ".join(public_reason(value).split())
    if text.startswith("기존 검토완료 참조자료(") and text.endswith("기관코드 일치, 최종판정=Y"):
        return "검토 완료된 기준 목록과 기관코드 일치"
    unit = re.fullmatch(r"기관코드가 군부대 전용 코드 패턴\(ZD0#####\)이며 기관명에 부대성 표현\('(.+)'\) 포함", text)
    if unit:
        return f"군부대 코드(ZD0)와 기관명 ‘{unit[1]}’ 규칙 일치"
    anchor = re.fullmatch(r"명칭 규칙 일치\(R_ANCHOR:(.+)\) - 토큰 시작 앵커 기반, 부분문자열 아님", text)
    if anchor:
        return f"기관명 단어의 시작이 ‘{anchor[1]}’ 규칙과 일치"
    guessed = re.fullmatch(r"명칭 규칙 일치\(R_UNIT\) - 토큰 시작 앵커 기반, 부분문자열 아님; 군 구분은 부대 유형으로 추정\((.+)\)", text)
    if guessed:
        return f"군부대 명칭 규칙 일치 · 군 구분: {guessed[1]}(추정)"
    manual = re.fullmatch(r"국방 관련 키워드\('.+'\) 포함, 코드로는 뒷받침 안 되어 개별 확인 완료 - (.+)", text)
    if manual:
        detail = manual[1].replace(" - ZD0 군부대 코드 + '해병대' 확인, 최종 검토에서 추가 발견", " · 군부대 코드와 해병대 명칭 확인")
        return f"개별 검토: {detail} (기관코드만으로 확인 불가)"
    if text.startswith("정부조직법 제36조: 국방부장관 소속 외청(병무청)으로 확인"):
        return "병무청 소속 기관으로 대장 등록 · 기록 근거: 정부조직법 제36조"
    if text == "2022 신규 국방기관":
        return "2022년 신규 국방기관으로 대장 등록"
    if text.startswith("군부대 전용 코드(ZD0#####)이나 이름에 가드 키워드가 전혀 없어 개별 확인 완료 - "):
        return "개별 검토: " + text.split(" - ", 1)[1] + " · 기관명 규칙만으로 확인 불가"
    # 새로운/알 수 없는 근거는 생략하거나 확정으로 바꾸지 않는다.
    return text
