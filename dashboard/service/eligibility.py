"""공고 참여 판단 보조 — 내 회사 조건(소재지 시·도, 보유 면허)과 공고의 면허·지역 조건 비교.

판단은 **보조**다. 최종 자격은 공고 원문 기준이다.
- 면허: EDA `license_values`는 면허 그룹(lmtGrpNo)을 합쳐 버려 "모두 필요"인지 "하나만 있으면 됨"인지
  알 수 없다. 그래서 보유 면허와 겹쳐도 '가능'으로 확정하지 않고 '확인'으로 둔다.
- 지역: 회사 소재지는 시·도 단위로만 받는다. 허용 지역이 시·군 단위면 '확인'이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from service.requirement_overlay import usable_values

OK, CHECK, NO, NEED_INPUT = "● 참여 가능", "▲ 원문 확인", "■ 참여 불가", "○ 내 조건 미입력"
STATUS_OPTIONS = [OK, CHECK, NO, NEED_INPUT]
DISCLAIMER = "판단 보조입니다. 최종 참가 자격은 공고 원문을 기준으로 확인하세요."
# 사용자 질문(2026-09-28) "확인 필요는 어떤 의미야?"에 대한 화면 설명
LEGEND = {
    OK: "내 소재지·면허로 참여 조건을 모두 충족합니다.",
    CHECK: "수집된 자료만으로는 판단할 수 없어 **공고 원문에서 조건을 직접 확인**해야 합니다. "
           "(① 조건 정보가 아직 수집되지 않음 ② 요구 면허 중 일부만 보유 ③ 지역 제한이 시·군 단위)",
    NO: "요구 면허를 하나도 보유하지 않았거나, 내 소재지가 허용 지역이 아닙니다.",
    NEED_INPUT: "왼쪽 **내 회사 조건**에 소재지·보유 면허를 넣으면 판단합니다.",
}


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str


def split_values(value) -> list[str]:
    if not isinstance(value, str):
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def license_name(value: str) -> str:
    """'건축공사업/0002' → '건축공사업' (뒤의 코드는 떼고 이름으로 비교)."""
    return value.rsplit("/", 1)[0].strip()


def judge_license(state, values, my_licenses: list[str]) -> Verdict:
    if state == "조건없음":
        return Verdict(OK, "면허 제한 없음")
    if state != "제한있음":
        return Verdict(CHECK, "면허 조건 미확인 — 원문 확인")
    required = {license_name(v) for v in usable_values(values)}
    if not required:
        return Verdict(CHECK, "면허 제한 상세 미확인 — 원문 확인")
    if not my_licenses:
        return Verdict(NEED_INPUT, "보유 면허를 입력하면 비교합니다")
    matched = required & set(my_licenses)
    if not matched:
        return Verdict(NO, "요구 면허 중 보유한 것 없음")
    if len(required) == 1:
        return Verdict(CHECK, f"요구 면허 보유({next(iter(matched))}) — 세부 조건 원문 확인")
    return Verdict(CHECK, f"{len(required)}개 중 {len(matched)}개 보유 — 모두 필요한지 원문 확인")


def judge_region(state, values, my_region: str | list[str] | tuple[str, ...] | None) -> Verdict:
    if state == "조건없음":
        return Verdict(OK, "지역 제한 없음")
    if state != "제한있음":
        return Verdict(CHECK, "지역 조건 미확인 — 원문 확인")
    allowed = usable_values(values)
    if not allowed:
        return Verdict(CHECK, "지역 제한 상세 미확인 — 원문 확인")
    if not my_region:
        return Verdict(NEED_INPUT, "소재지를 입력하면 비교합니다")
    regions = [my_region] if isinstance(my_region, str) else list(my_region)
    matched = [r for r in regions if r in allowed]
    if matched:
        return Verdict(OK, f"{', '.join(matched)} 허용")
    partial = [r for r in regions if any(a.startswith(r + " ") for a in allowed)]
    if partial:
        return Verdict(CHECK, f"{', '.join(partial)} 안 일부 시·군만 허용 — 소재 시·군 확인")
    return Verdict(NO, f"선택한 소재지 불가 (허용: {', '.join(allowed[:3])}{' 외' if len(allowed) > 3 else ''})")


def overall(lic: Verdict, reg: Verdict) -> str:
    statuses = {lic.status, reg.status}
    if NO in statuses:
        return NO
    if statuses == {OK}:
        return OK
    if NEED_INPUT in statuses and CHECK not in statuses:
        return NEED_INPUT
    return CHECK


def judge(row, my_region: str | list[str] | tuple[str, ...] | None, my_licenses: list[str]) -> tuple[str, Verdict, Verdict]:
    lic = judge_license(row["license_state"], row["license_values"], my_licenses)
    reg = judge_region(row["region_state"], row["region_values"], my_region)
    # 문서 후보·상충 근거는 확인된 것처럼 회사의 충족/불가 판정에 쓰지 않는다.
    if row.get("license_requires_review", False):
        lic = Verdict(CHECK, "면허 근거 확인 — 문장 전체·예외 원문 검토 필요")
    if row.get("region_requires_review", False):
        reg = Verdict(CHECK, "지역 근거 확인 — 문장 전체·예외 원문 검토 필요")
    return overall(lic, reg), lic, reg
