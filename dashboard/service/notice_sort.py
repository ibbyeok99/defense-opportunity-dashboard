"""표 정렬은 페이지 분할 전에 전체 검색 결과에 적용한다."""

from datetime import datetime

import pandas as pd

SORT_FIELDS = {"마감": "bid_close_date", "공고명": "notice_name", "수요기관": "demand_agency_name",
               "유형": "procurement_type", "참여 판단": "status", "면허·지역 요건": "license_values"}


def sort_by_deadline(frame: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """마감 전은 촉박한 순, 마감 후는 최근 마감순, 마감 미확인은 마지막.

    now와 마감일은 같은 시간대의 datetime이어야 한다. 원본 값·열·인덱스는 보존한다.
    """
    deadlines = frame["bid_close_date"]
    upcoming = frame.loc[deadlines >= now].sort_values(
        ["bid_close_date", "notice_date"], ascending=[True, False], kind="mergesort")
    expired = frame.loc[deadlines < now].sort_values(
        ["bid_close_date", "notice_date"], ascending=[False, False], kind="mergesort")
    unknown = frame.loc[deadlines.isna()].sort_values(
        "notice_date", ascending=False, kind="mergesort", na_position="last")
    return pd.concat([upcoming, expired, unknown])


def normalize_sort(value):
    if not isinstance(value, dict) or value.get("label") not in SORT_FIELDS or value.get("direction") not in (0, 1, 2):
        return {"label": None, "direction": 0}
    return {"label": value["label"], "direction": value["direction"]}


def sort_notices(frame, value):
    state = normalize_sort(value)
    if not state["direction"]:
        return frame.copy()
    field = SORT_FIELDS[state["label"]]
    if field not in frame.columns:
        return frame.copy()
    if state["label"] == "면허·지역 요건":
        out = frame.copy()
        out["_requirement_sort"] = out["license_values"].fillna("") + " | " + out["region_values"].fillna("")
        return out.sort_values("_requirement_sort", ascending=state["direction"] == 1, kind="mergesort").drop(columns="_requirement_sort")
    return frame.sort_values(field, ascending=state["direction"] == 1, kind="mergesort", na_position="last").copy()
