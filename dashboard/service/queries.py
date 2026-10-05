"""화면별 결과 계산 — 필터 묶음(service/filters.py)을 받아 표·숫자를 돌려준다. 화면을 그리지 않는다.

화면(app_pages)은 여기서 받은 결과를 view/ 조각으로 그리기만 한다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import pandas as pd

from service import data, metrics
from service.eligibility import judge, split_values
from service.company_match import matches_company, matching_dimensions
from service.notice_date_policy import notice_kind
from service.filters import YEAR_RANGE, ItemFilter, NoticeFilter, OverviewFilter, Profile
from service.notice_sort import sort_by_deadline, sort_notices
from service.notice_saved_details import saved_notice_details
from service.requirement_overlay import usable_values


def _agency_col(role: str) -> str:
    return "demand_agency_name" if role == "수요기관" else "notice_agency_name"


def _agency_options(df: pd.DataFrame) -> dict[str, list[str]]:
    """기관 역할별 선택지(많이 나온 순)."""
    return {"수요기관": df["demand_agency_name"].value_counts().index.tolist(),
            "공고기관": df["notice_agency_name"].value_counts().index.tolist()}


# ---- 공고 ----
def notice_agency_options() -> dict[str, list[str]]:
    return _agency_options(data._base_notices())


def agency_option_labels() -> dict[str, dict[str, str]]:
    """필터 값은 유지하고 검색창에서만 기관명 (코드)를 표시한다."""
    frame = data._base_notices()
    labels = {}
    for role, stem in (("수요기관", "demand"), ("공고기관", "notice")):
        name_col, code_col = f"{stem}_agency_name", f"{stem}_agency_code"
        mapping = {}
        if code_col in frame:
            # 같은 기관이 공고마다 반복된다. 전체 행·원문 열 대신 고유 이름/코드만 묶는다.
            pairs = frame[[name_col, code_col]].drop_duplicates()
            for name, rows in pairs.groupby(name_col, sort=False):
                codes = rows[code_col].dropna().astype(str).drop_duplicates().tolist()
                mapping[name] = f"{name} ({', '.join(codes)})" if codes else name
                mapping.update({code: f"{name} ({code})" for code in codes})
        labels[role] = mapping
    return labels


def find_notices(f: NoticeFilter, profile: Profile, now: datetime, *, stored_only=False) -> pd.DataFrame:
    """조건에 맞는 공고 + 참여 판단(status)·남은 날(dday). 상태 필터와 무관하게 마감이 가까운 순."""
    df = data.stored_notices() if stored_only else data.notices()
    out = df[df["procurement_type"].isin(f.types)]
    if f.item:
        out = out[out["item_code"] == f.item]
    kw = f.keyword.strip()
    if kw:  # 공고명·분류 번호와 보완된 요건 근거
        out = out[out["notice_name"].str.contains(kw, case=False, na=False, regex=False)
                  | out["item_code"].str.contains(kw, na=False, regex=False)
                  | out.get("requirement_search_text", pd.Series("", index=out.index)).str.contains(kw, case=False, na=False, regex=False)]
    if f.status == "마감 전":
        out = out[out["bid_close_date"] >= now]
        limit = {"7일 안": 7, "30일 안": 30}.get(f.deadline)
        if limit:
            out = out[out["bid_close_date"] < now + timedelta(days=limit)]
    elif f.status == "최근 1개월":
        out = out[out["notice_date"] >= now - timedelta(days=30)]
    if f.date_from:
        out = out[out["notice_date"] >= pd.Timestamp(f.date_from)]
    if f.date_to:
        out = out[out["notice_date"] < pd.Timestamp(f.date_to) + pd.Timedelta(days=1)]
    if f.agencies:
        out = out[data.agency_mask(out, f.agency_role, f.agencies)]
    out = out.copy()
    out["status"] = [judge(r, profile.region, list(profile.licenses))[0] for r in out.to_dict("records")]
    # 회사 입력은 검색 결과를 줄이지 않는다. 진행 중인 일치 공고만 우선 표시한다.
    out["company_match"] = [matches_company(r, profile) and notice_kind(r) != '취소공고'
                            for r in out.to_dict("records")]
    out["company_match"] &= (out["bid_close_date"].ge(now) & out["notice_date"].le(now))
    out["company_match"] &= (out["bid_close_date"] - out["notice_date"]).le(pd.Timedelta(days=365))
    if f.judge:
        out = out[out["status"].isin(f.judge)]
    out["dday"] = (out["bid_close_date"].dt.normalize() - pd.Timestamp(now.date())).dt.days
    return sort_notices(sort_by_deadline(out, now), None)


def only_status(found: pd.DataFrame, statuses: list[str]) -> pd.DataFrame:
    """찾은 공고 중 참여 판단이 statuses인 것만."""
    return found[found["status"].isin(statuses)]


def notice_summary(found: pd.DataFrame) -> dict:
    """찾은 공고 요약: 판단별 건수, 7일 안 마감 수, 조건 자료 미확인 비율."""
    unknown = ((found["license_state"] == "미확인") | (found["region_state"] == "미확인")).mean() if len(found) else 0
    return {"counts": found["status"].value_counts().to_dict(),
            "urgent": int(((found["dday"] >= 0) & (found["dday"] <= 7)).sum()),
            "unknown_share": float(unknown)}


def notice_detail(notice_id: str, profile: Profile, *, notice=None, include_competition=True) -> dict | None:
    """공고 한 건 + 참여 조건 비교표 + 이 분류의 과거 경쟁(최근 연도)·계약까지 일수."""
    if notice is None:
        df = data.notices()
        rows = df[df["notice_id"] == notice_id]
        if rows.empty:
            return None
        n = rows.iloc[0]
    else:
        n = pd.Series(notice).copy()
        if n.get('notice_id') != notice_id:
            raise ValueError('선택한 상세 공고와 전달 행 불일치')
    status, lic, reg = judge(n.to_dict(), profile.region, list(profile.licenses))
    conditions = pd.DataFrame([
        ["면허", ", ".join(split_values(n["license_values"])) or n["license_state"],
         ", ".join(profile.licenses) or "미입력", lic.status, lic.reason],
        ["지역", ", ".join(split_values(n["region_values"])) or n["region_state"], ", ".join(profile.region) or "미입력",
         reg.status, reg.reason],
    ], columns=["구분", "요구 조건", "내 조건", "판단", "이유"])
    names_match = matching_dimensions(n, profile)
    conditions['입력조건일치'] = [names_match['license'], names_match['region']]
    # 회사 입력 부족과 공고 근거 검토는 별개다. 안내를 추가하되 보수적인 판정은 유지한다.
    conditions["입력 안내"] = [
        f"회사 {label}를 입력해 비교하세요."
        if n[f"{kind}_state"] == "제한있음" and usable_values(n[f"{kind}_values"]) and not supplied else ""
        for kind, label, supplied in (("license", "면허", profile.licenses), ("region", "소재지", profile.region))
    ]
    for index, kind in enumerate(("license", "region")):
        review = n.get(f"{kind}_review_status", "미조회")
        if review != "미조회":
            if n[f"{kind}_state"] == "미확인" or review == "공식 업종 제한 없음":
                values = str(n.get(f"{kind}_values", "") or "")
                conditions.at[index, "요구 조건"] = review + (" — " + values if values else "")
            conditions.at[index, "이유"] += f" · {review} · 근거 조회 {n.get('requirement_checked_at', '')}"
    stats = notice_competition(n['item_code']) if include_competition else {'competition': None, 'contract_days': None}
    from service.requirement_summary import summarize_participation
    return {"notice": n, "status": status, "conditions": conditions,
            "participation_requirements": summarize_participation(n.get('requirement_evidence')),
            "saved_details": saved_notice_details(n),
            **stats,
            "category": data.category_display(n["item_code"], n["category_value"])}


def notice_competition(item_code):
    comp = data.competition_levels().set_index('item_code')
    return {'competition': comp.loc[item_code] if item_code in comp.index else None,
            'contract_days': data.contract_days().get(item_code)}


def update_detail_evidence(detail, profile, result):
    from service.requirement_overlay import overlay
    current = overlay(pd.DataFrame([detail['notice']]), [result]).iloc[0]
    updated = notice_detail(current.notice_id, profile, notice=current, include_competition=False)
    updated.update({key: detail[key] for key in ('competition', 'contract_days')})
    return updated


def favorite_requirement_rows(rows, reader):
    """저장된 즐겨찾기 행만 요청한다. 상태 읽기는 완료를 기다리지 않는다."""
    from service.requirement_overlay import overlay
    snapshots, results = {}, []
    rows = rows.drop_duplicates('notice_id').head(10)
    for _, row in rows.iterrows():
        # 즐겨찾기는 API 값이 있어도 기타 참가자격/예외를 확인한다. poll은 저장 결과/작업을 재사용한다.
        snapshot = reader(row)
        snapshots[row.notice_id] = snapshot
        if snapshot.get('result'):
            results.append(snapshot['result'])
    # 완료 결과가 없는 행은 이미 연결한 사본/DB 값을 보존한다.
    out = rows.copy()
    if results:
        refreshed = overlay(rows, results)
        from service.requirement_overlay import identity
        keys = {identity(result) for result in results}
        mask = refreshed.apply(lambda row: identity(row) in keys, axis=1)
        out.loc[mask, refreshed.columns] = refreshed.loc[mask]
    return out, snapshots


# ---- 품목 분석 ----
def item_agency_options(code: str) -> dict[str, list[str]]:
    ev = metrics.events()
    return _agency_options(ev[ev["item_code"] == code])


def _split_counts(series: pd.Series, top: int = 10) -> pd.DataFrame:
    c = Counter(v.strip() for s in series.dropna() for v in s.split("|") if v.strip())
    return pd.DataFrame(c.most_common(top), columns=["조건", "공고 수"])


def _contract_year_summary(types: list[str], years: tuple[int, int], items: list[str] | None = None) -> pd.DataFrame:
    """계약일 기준 계약 통계. lifecycle의 공고 단위 계약값은 개찰마다 반복되므로 사용하지 않는다."""
    market = data.category_market()
    selected = market[market["procurement_type"].isin(types)
                      & market["year"].between(years[0], years[1])].copy()
    if items:
        selected = selected[selected["item_code"].isin(items)]
    if selected.empty:
        return pd.DataFrame(columns=["year", "contract_count", "contract_amount"])
    return (selected.groupby("year", as_index=False)
            .agg(contract_count=("contract_count", "sum"),
                 contract_amount=("contract_amount", lambda values: values.sum(min_count=1))))


def _contract_type_year_summary(types: list[str], years: tuple[int, int],
                                items: list[str] | None = None) -> pd.DataFrame:
    """계약일·조달유형 기준 요약. 금액은 국내 원화 계약만 해당한다."""
    market = data.category_market()
    selected = market[market["procurement_type"].isin(types)
                      & market["year"].between(years[0], years[1])].copy()
    if items:
        selected = selected[selected["item_code"].isin(items)]
    if selected.empty:
        return pd.DataFrame(columns=["year", "procurement_type", "contract_count", "contract_amount"])
    return (selected.groupby(["year", "procurement_type"], as_index=False)
            .agg(contract_count=("contract_count", "sum"),
                 contract_amount=("contract_amount", lambda values: values.sum(min_count=1))))


def item_event_counts(f: ItemFilter) -> dict[str, int]:
    """분류 선택칸도 본문과 같은 개찰 원천·기간·기관·금액 조건으로 센다."""
    ev = metrics.filter_events(metrics.events(), years=f.years, agencies=list(f.agencies),
                               agency_role=f.agency_role, amount_bins=list(f.amounts))
    return ev.groupby("item_code").size().to_dict()


def favorite_company_statuses(rows: pd.DataFrame, profile: Profile) -> dict:
    """검증된 서버 행만 비교. 브라우저 표시 사본·IO·원문 확인을 사용하지 않는다."""
    return {r['notice_id']: judge(r, profile.region, list(profile.licenses))[0]
            for r in rows.head(10).to_dict('records')}


def item_suppliers(code: str, f: ItemFilter) -> pd.DataFrame:
    y0, y1 = f.years
    sup = data.suppliers().query("item_code == @code and @y0 <= year <= @y1")
    if not len(sup):
        return pd.DataFrame()
    agg = sup.groupby("supplier_name", as_index=False).agg(award_count=("award_count", "sum"))
    agg["count_share"] = agg["award_count"] / agg["award_count"].sum()
    return agg.sort_values("award_count", ascending=False).head(15)


def item_view(code: str, f: ItemFilter, now: pd.Timestamp, *, include_suppliers=True) -> dict:
    """분류 하나의 요약·연도별 지표·진입 조건·낙찰 업체. 기관·금액 필터는 개찰 1건 단위로 다시 계산한다."""
    ev_all = metrics.events()
    ev = metrics.filter_events(ev_all[ev_all["item_code"] == code], years=f.years, agencies=list(f.agencies),
                               agency_role=f.agency_role, amount_bins=list(f.amounts))
    detail_filter = bool(f.agencies or f.amounts)          # EDA 집계로는 반영할 수 없는 필터
    nt_all = data.notices().query("item_code == @code")
    nt = nt_all[nt_all["notice_date"].dt.year.between(f.years[0], f.years[1])]
    if f.agencies:
        nt = nt[data.agency_mask(nt, f.agency_role, f.agencies)]
    out = {"ev": ev, "detail_filter": detail_filter, "filtered": detail_filter or tuple(f.years) != YEAR_RANGE,
           "open_n": int((nt_all["bid_close_date"] >= now).sum()),
           "level": data.competition_levels().set_index("item_code")["level"].get(code, ""),
           "level_year": data.competition_levels().set_index("item_code")["year"].get(code)}
    if ev.empty:
        return out
    y0, y1 = f.years
    hist = data.category_market().query("item_code == @code and @y0 <= year <= @y1").sort_values("year")
    mysql_source = data.SOURCE in {"mysql", "api"}
    contract_supported = not detail_filter if mysql_source else True
    contract_year = (_contract_year_summary([str(hist["procurement_type"].iloc[0])] if len(hist) else [],
                                             f.years, [code]) if mysql_source and contract_supported else
                     pd.DataFrame(columns=["year", "contract_count", "contract_amount"]))
    contract_type_year = (_contract_type_year_summary(
        [str(hist["procurement_type"].iloc[0])] if len(hist) else [], f.years, [code])
        if mysql_source and contract_supported else
        pd.DataFrame(columns=["year", "procurement_type", "contract_count", "contract_amount"]))
    yearly = metrics.by_year(ev)
    if mysql_source and contract_supported:
        yearly = yearly.drop(columns=["contract_count", "contract_amount"], errors="ignore").merge(
            contract_year, on="year", how="left", validate="one_to_one")
    elif mysql_source:
        yearly["contract_count"] = pd.NA
        yearly["contract_amount"] = pd.NA
    top_sup = item_suppliers(code, f) if include_suppliers else pd.DataFrame()
    summary = metrics.summarize(ev)
    if mysql_source and contract_supported:
        summary["contract_count"] = int(contract_year["contract_count"].sum()) if len(contract_year) else 0
        summary["contract_amount"] = contract_year["contract_amount"].sum(min_count=1) if len(contract_year) else None
    elif mysql_source:
        summary["contract_count"] = None
        summary["contract_amount"] = None
    out.update({
        "summary": summary,
        "yearly": yearly,
        "contract_year": contract_year,
        "top3": hist["top3_share_count"].iloc[-1] if len(hist) and not detail_filter else None,
        "top3_year": int(hist["year"].iloc[-1]) if len(hist) and not detail_filter else None,
        "licenses": _split_counts(nt.loc[nt["license_state"] == "제한있음", "license_values"]),
        "regions": _split_counts(nt.loc[nt["region_state"] == "제한있음", "region_values"]),
        "license_share": nt["license_state"].value_counts(normalize=True).to_dict(),
        "region_share": nt["region_state"].value_counts(normalize=True).to_dict(),
        "days": ev["notice_to_contract_days"].dropna(),
        "top_agencies": nt["demand_agency_name"].value_counts().head(3),
        "suppliers": top_sup,
    })
    # 누적 KPI와 단년 증감을 섞지 않는다. 선택 기간 안 최신 완료 연도를 우선한다.
    as_of = pd.to_datetime(ev_all["data_as_of"], utc=True, errors="coerce").max()
    completed_year = as_of.year - 1 if pd.notna(as_of) else now.year - 1
    kpi_year = min(y1, completed_year) if y0 <= completed_year else y1
    comparison_ev = metrics.filter_events(ev_all[ev_all["item_code"] == code],
        years=(kpi_year - 1, kpi_year), agencies=list(f.agencies), agency_role=f.agency_role,
        amount_bins=list(f.amounts))
    kpi_hist = data.category_market().query("item_code == @code")
    snapshots = []
    for year in (kpi_year, kpi_year - 1):
        sample = comparison_ev[comparison_ev["year"] == year]
        snapshot = metrics.summarize(sample)
        if mysql_source and contract_supported:
            contract_row = contract_year[contract_year["year"] == year]
            snapshot["contract_count"] = int(contract_row["contract_count"].sum()) if len(contract_row) else 0
            snapshot["contract_amount"] = (contract_row["contract_amount"].sum(min_count=1)
                                            if len(contract_row) else None)
        elif mysql_source:
            snapshot["contract_count"] = None
            snapshot["contract_amount"] = None
        if sample.empty:
            snapshot = {key: None for key in snapshot}
        rows = kpi_hist[kpi_hist["year"] == year]
        snapshot["top3"] = rows["top3_share_count"].iloc[-1] if len(rows) and not detail_filter else None
        snapshots.append(snapshot)
    out.update(kpi_year=kpi_year, kpi_partial=kpi_year > completed_year,
               kpi_current=snapshots[0], kpi_previous=snapshots[1])
    return out


# ---- 시장 개요 ----
def overview_agency_options() -> dict[str, list[str]]:
    return _agency_options(metrics.events())


def overview_view(f: OverviewFilter) -> dict:
    """시장 개요: 공고 수(공고 표)와 개찰·계약 지표(개찰 1건 단위 재계산)."""
    types = list(f.types) or list(data.TYPES)
    ev = metrics.filter_events(metrics.events(), years=f.years, types=types, items=list(f.items),
                               agencies=list(f.agencies), agency_role=f.agency_role, amount_bins=list(f.amounts),
                               outcomes=list(f.outcomes), region=f.region)
    nt_all = data.notices()
    nt = nt_all[nt_all["notice_date"].dt.year.between(f.years[0], f.years[1]) & nt_all["procurement_type"].isin(types)]
    if f.items:
        nt = nt[nt["item_code"].isin(f.items)]
    if f.agencies:
        nt = nt[data.agency_mask(nt, f.agency_role, f.agencies)]
    if f.region:
        ok = nt["region_values"].fillna("").str.split("|").map(lambda xs: f.region in [x.strip() for x in xs])
        nt = nt[(nt["region_state"] == "조건없음") | ((nt["region_state"] == "제한있음") & ok)]
    mysql_source = data.SOURCE in {"mysql", "api"}
    contract_supported = not (f.agencies or f.amounts or f.outcomes or f.region) if mysql_source else True
    contract_year = (_contract_year_summary(types, f.years, list(f.items))
                     if mysql_source and contract_supported else
                     pd.DataFrame(columns=["year", "contract_count", "contract_amount"]))
    if mysql_source and contract_supported:
        contract_type_year = _contract_type_year_summary(types, f.years, list(f.items))
    elif mysql_source:
        contract_type_year = pd.DataFrame(columns=["year", "procurement_type", "contract_count", "contract_amount"])
    else:
        contract_type_year = metrics.by_year(ev, ["procurement_type"])
    notice_year = (nt.assign(year=nt["notice_date"].dt.year).groupby(["year", "procurement_type"]).size()
                   .rename("notice_count").reset_index())
    share = nt.groupby("procurement_type").size().rename("notice_count").reset_index()
    share["비중"] = share["notice_count"] / max(share["notice_count"].sum(), 1)
    top_cat = (ev.groupby(["item_code", "procurement_type"]).size().rename("event_count").reset_index()
               .nlargest(10, "event_count"))
    top_cat["분류"] = top_cat["item_code"].map(data.category_display)
    summary = metrics.summarize(ev)
    if mysql_source and contract_supported:
        summary["contract_count"] = int(contract_year["contract_count"].sum()) if len(contract_year) else 0
        summary["contract_amount"] = contract_year["contract_amount"].sum(min_count=1) if len(contract_year) else None
    elif mysql_source:
        summary["contract_count"] = None
        summary["contract_amount"] = None
    return {
        "types": types, "ev": ev, "notice_total": len(nt), "summary": summary,
        "contract_supported": contract_supported, "contract_year": contract_year,
        "contract_type_year": contract_type_year,
        "notice_year": notice_year, "event_year": metrics.by_year(ev, ["procurement_type"]), "share": share,
        "top_agencies": nt[_agency_col(f.agency_role)].value_counts().head(10).rename_axis("agency")
        .reset_index(name="notice_count"),
        "top_categories": top_cat,
        "empty": ev.empty and nt.empty,
    }
