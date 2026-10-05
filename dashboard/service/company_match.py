"""입력한 회사 조건과 확인된 등록 요건의 일치 표시. 최종 참가 판단과 별개다."""

from service.eligibility import OK, judge_region, license_name, comparable_condition
from service.requirement_overlay import usable_values


def matching_dimensions(row, profile):
    """표시된 면허명·시도와 회사 입력의 일치. 문서 해석/최종 자격 판정은 하지 않는다."""
    required = {license_name(v) for v in usable_values(row.get('license_values'))}
    lic = bool(profile.licenses) and (
        row.get('license_state') == '조건없음' or
        (row.get('license_state') == '제한있음' and bool(required) and required <= set(profile.licenses)))
    reg = bool(profile.region) and judge_region(
        row.get('region_state'), row.get('region_values'), profile.region).status == OK
    return {'license': lic, 'region': reg}


def matches_company(row, profile):
    """입력한 항목마다 알려진 조건이 맞을 때만 표시한다. 미확인·후보는 제외한다."""
    if not (profile.region or profile.licenses):
        return False
    if profile.region:
        if not comparable_condition(row, 'region'):
            return False
        if judge_region(row.get('region_state'), row.get('region_values'), profile.region).status != OK:
            return False
    if profile.licenses:
        if not comparable_condition(row, 'license'):
            return False
        state = row.get('license_state')
        required = {license_name(v) for v in usable_values(row.get('license_values'))}
        if state != '조건없음' and not (
                state == '제한있음' and required and required <= set(profile.licenses)):
            return False
    return True
