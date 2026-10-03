"""화면 → 데이터로 넘기는 필터 값 묶음. 빈 값은 '전체'.

화면(app_pages)은 사이드바 위젯 값을 이 묶음으로 만들어 service/queries.py에 넘긴다.
데이터 쪽을 S3·DB로 바꿔도 이 약속은 그대로 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

YEAR_RANGE = (2020, 2026)


@dataclass(frozen=True)
class Profile:
    """내 회사 조건(참여 판단용)."""
    region: tuple[str, ...] = ()
    licenses: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoticeFilter:
    types: tuple[str, ...]
    item: str | None = None
    keyword: str = ""
    status: str = "마감 전"          # "마감 전" | "최근 1개월" | "전체"
    deadline: str = "전체"           # "7일 안" | "30일 안" | "전체" (마감 전일 때만)
    agency_role: str = "수요기관"     # "수요기관" | "공고기관"
    agencies: tuple[str, ...] = ()
    judge: tuple[str, ...] = ()       # 참여 판단(빈 값 = 전체)
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class ItemFilter:
    years: tuple[int, int] = YEAR_RANGE
    agency_role: str = "수요기관"
    agencies: tuple[str, ...] = ()
    amounts: tuple[str, ...] = ()


@dataclass(frozen=True)
class OverviewFilter:
    years: tuple[int, int] = YEAR_RANGE
    types: tuple[str, ...] = ()
    agency_role: str = "수요기관"
    agencies: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    region: str | None = None
    amounts: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
