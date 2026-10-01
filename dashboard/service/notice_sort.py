"""표 정렬은 페이지 분할 전에 전체 검색 결과에 적용한다."""

SORT_FIELDS = {"마감": "bid_close_date", "공고명": "notice_name", "수요기관": "demand_agency_name",
               "유형": "procurement_type", "참여 판단": "status", "면허·지역 요건": "license_values"}


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
