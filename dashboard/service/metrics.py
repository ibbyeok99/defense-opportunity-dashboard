"""개찰 1건 단위 재계산 — 품목 분석·시장 개요의 기관·금액·낙찰/유찰·지역 필터용(사용자 결정 2026-09-28).

EDA 집계표(분류×연도)에는 기관·금액 구간이 없어서, 필터가 걸리면 `mart_lifecycle`(개찰 1건 = 1행)을 거른 뒤
지표를 다시 계산한다. 필터가 없을 때 값이 EDA 집계와 같다는 것을 확인했다(2026-09-28, tests/test_metrics.py):
유형×연도 개찰 수·참가업체 중앙값·무응찰 비율 일치, 평균 낙찰가율 차이 ≤0.3%p.

주의
- 단독입찰 비율 = 단독입찰 수 ÷ (무응찰이 아닌 개찰 수). `single_bid_rate_base` 열은 쓰지 않는다.
- 금액 구간은 낙찰금액 기준. 단가계약(예: 항공유)은 낙찰금액이 단가로 들어와 있어 작은 구간에 섞일 수 있다.
- 업체 집중도(HHI·상위 3개)는 기관별 자료가 없어 여기서 계산하지 않는다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from service import data

AMOUNT_BINS = {  # 낙찰금액 구간(원)
    "1억 미만": (0, 1e8),
    "1억~10억": (1e8, 1e9),
    "10억~100억": (1e9, 1e10),
    "100억 이상": (1e10, float("inf")),
}
OUTCOMES = ["낙찰 있음", "무응찰(유찰)", "재입찰·재공고"]
AGENCY_ROLES = ["수요기관", "공고기관"]
AMOUNT_NOTE = "금액은 낙찰금액 기준입니다. 단가계약은 낙찰금액이 단가로 들어와 있어 작은 구간에 섞일 수 있습니다."


@st.cache_data(ttl=data.STATS_TTL)
def events() -> pd.DataFrame:
    """개찰 1건 = 1행 + 연도·참여 여부·기관 이름·참가가능지역·분류 표시명."""
    ev = data.lifecycle().copy()
    ev["year"] = ev["opening_date"].dt.year
    ev["participated"] = ~ev["no_bid"].fillna(False).astype(bool)
    names = data.agency_names()
    for name_col, code_col, raw_col in (
        ("demand_agency_name", "demand_agency_code", "dminsttNm"),
        ("notice_agency_name", "notice_agency_code", "ntceInsttNm"),
    ):
        # v5 lifecycle has role-specific names. mart_institution may have one
        # code in multiple roles, so its code→name map is fallback only.
        mapped = ev[code_col].map(names).fillna(ev[code_col])
        if raw_col in ev.columns:
            raw = ev[raw_col].astype("string").str.strip().replace("", pd.NA)
            ev[name_col] = raw.fillna(mapped)
        else:
            ev[name_col] = mapped
    regions = data.notices().drop_duplicates("notice_id").set_index("notice_id")[["region_state", "region_values"]]
    ev = ev.join(regions, on="notice_id")
    return ev


def filter_events(ev: pd.DataFrame, *, years: tuple[int, int] | None = None, types: list[str] | None = None,
                  items: list[str] | None = None, agencies: list[str] | None = None, agency_role: str = "수요기관",
                  amount_bins: list[str] | None = None, outcomes: list[str] | None = None,
                  region: str | None = None) -> pd.DataFrame:
    """비어 있는 조건은 '전체'. 순수 pandas라 테스트할 수 있다."""
    m = pd.Series(True, index=ev.index)
    if years:
        m &= ev["year"].between(years[0], years[1])
    if types:
        m &= ev["procurement_type"].isin(types)
    if items:
        m &= ev["item_code"].isin(items)
    if agencies:
        m &= data.agency_mask(ev, agency_role, agencies)
    if amount_bins:
        amt = ev["award_amount"]
        in_bin = pd.Series(False, index=ev.index)
        for b in amount_bins:
            lo, hi = AMOUNT_BINS[b]
            in_bin |= (amt >= lo) & (amt < hi)
        m &= in_bin
    if outcomes:
        hit = pd.Series(False, index=ev.index)
        if "낙찰 있음" in outcomes:
            hit |= ev["award_amount"].notna()
        if "무응찰(유찰)" in outcomes:
            hit |= ev["no_bid"].fillna(False).astype(bool)
        if "재입찰·재공고" in outcomes:
            hit |= ev["reprocedure"].fillna(False).astype(bool)
        m &= hit
    if region:
        vals = ev["region_values"].fillna("")
        allowed = vals.str.split("|").map(lambda xs: region in [x.strip() for x in xs])
        m &= (ev["region_state"] == "조건없음") | ((ev["region_state"] == "제한있음") & allowed)
    return ev[m]


def summarize(ev: pd.DataFrame) -> dict:
    n = len(ev)
    part = int(ev["participated"].sum())
    return {
        "events": n,
        "median_bidders": ev["n_bidders"].median() if n else None,
        "mean_bidders": ev["n_bidders"].mean() if n else None,
        "single_bid_rate": ev["single_bid"].fillna(False).astype(bool).sum() / part if part else None,
        "no_bid_rate": ev["no_bid"].fillna(False).astype(bool).mean() if n else None,
        "reprocedure_rate": ev["reprocedure"].fillna(False).astype(bool).mean() if n else None,
        "mean_award_rate": ev["award_rate"].mean() if n else None,
        "contract_count": ev["contract_count"].sum(),
        "contract_amount": ev["contract_amount"].sum(min_count=1),
        "median_days": ev["notice_to_contract_days"].median() if n else None,
    }


def by_year(ev: pd.DataFrame, extra: list[str] | None = None) -> pd.DataFrame:
    """연도(+추가 기준)별 지표 표. 차트용."""
    keys = ["year"] + (extra or [])
    rows = []
    for k, g in ev.groupby(keys, dropna=True):
        k = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(keys, k)), **summarize(g)})
    out = pd.DataFrame(rows)
    if len(out):
        out["year"] = out["year"].astype(int)
    return out


def contract_amount_availability(yearly: pd.DataFrame) -> str:
    """표시 상태만 판별한다. 금액 0과 연결 계약 없음은 구분하며 원본은 수정하지 않는다."""
    if yearly.empty:
        return "no_linked_contracts"
    counts = pd.to_numeric(yearly["contract_count"], errors="coerce")
    if counts.eq(0).all():
        return "no_linked_contracts"
    amounts = pd.to_numeric(yearly["contract_amount"], errors="coerce")
    return "available" if amounts.notna().any() else "missing_amount"
