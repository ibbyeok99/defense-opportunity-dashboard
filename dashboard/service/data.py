"""게시된 MySQL 지표·공고를 화면 데이터 계약에 맞게 변환한다.

기본 원천은 defense_analysis의 v5 분석 스냅샷이며, 실시간 수집 파이프라인과는 별도다.
CSV는 FRONTLINE_DATA_SOURCE=eda_csv로 명시했을 때만 사용한다.
화면을 그리지 않는다(streamlit은 캐시에만 쓴다). 열 이름·단위 약속은 dashboard/README.md.
"""


from __future__ import annotations

import pandas as pd
import streamlit as st

from service.source import (NOTICE_TTL, STATS_TTL, SOURCE, read_metadata, read_pending_institutions,
                            read_defense_institutions, PUBLISHED_TABLES)
from service.source import read_table as _read
from service.source import read_automatic_institutions
from service.source import read_product_name_reference
from service.category_quality import apply_official_names, catalog_audit
from service.institution_display import roles_label, reason_label

TYPES = ["물품", "용역", "공사", "외자"]


@st.cache_data(ttl=NOTICE_TTL)
def automatic_institutions() -> pd.DataFrame:
    return read_automatic_institutions()


@st.cache_data(ttl=NOTICE_TTL)
def defense_institutions() -> pd.DataFrame:
    """국방 조달 분석 대상으로 판정된 Y 기관만 제공한다. 기관코드는 문자열로 유지한다."""
    raw = read_defense_institutions()
    cols = {"institution_code": "기관코드", "institution_name_std": "기관명",
            "defense_group": "소속 분류", "parent_institution": "상위 기관",
            "institution_roles": "관측 역할",
            "classification_reason": "포함 근거"}
    out = raw.loc[raw["is_defense"].str.strip().str.upper() == "Y", list(cols)].rename(columns=cols).fillna("")
    out["관측 역할"] = out["관측 역할"].map(roles_label)
    out["포함 근거"] = out["포함 근거"].map(reason_label)
    out = out.drop_duplicates("기관코드").sort_values("기관코드", kind="stable")
    out.attrs.update(raw.attrs)
    return out


def _num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _bool(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            normalized = df[c].astype("string").str.strip().str.casefold()
            df[c] = normalized.map({"true": True, "false": False, "1": True, "1.0": True,
                                    "0": False, "0.0": False}).astype("boolean")
    return df


@st.cache_data(ttl=STATS_TTL)
def metadata() -> dict:
    return read_metadata()


@st.cache_data(ttl=STATS_TTL)
def run_checks() -> pd.DataFrame:
    if SOURCE in {"mysql", "api"}:
        meta = metadata()
        return pd.DataFrame([
            {"검사 항목": "대시보드 지표 테이블 조회", "통과": meta.get("required_tables_present", False),
             "결과": f"{len(PUBLISHED_TABLES)}개 핵심 테이블"},
            {"검사 항목": "게시 버전 일관성", "통과": meta.get("version_consistent"),
             "결과": str(meta.get("run_id") or "게시 버전 확인 불가")},
        ])
    return _read("실행점검.csv")


@st.cache_data(ttl=STATS_TTL)
def overview() -> pd.DataFrame:
    df = _read("mart_procurement_overview.csv")
    return _num(df, ["year", "notice_count", "opening_count", "mean_bidders", "median_bidders", "no_bid_rate",
                     "single_bid_count", "participated_event_count", "valid_bidder_count",
                     "single_bid_rate", "reprocedure_rate", "award_count", "award_amount", "mean_award_rate",
                     "identified_supplier_count", "contract_count", "contract_amount", "contract_agency_count"])


@st.cache_data(ttl=STATS_TTL)
def ytd_overview() -> pd.DataFrame:
    df = _read("latest_ytd_overview.csv")
    return _num(df, ["year", "opening_count", "identified_award_event_count", "contract_count", "contract_amount",
                     "previous_ytd_contract_amount", "growth_rate_yoy_ytd"])


@st.cache_data(ttl=STATS_TTL)
def category_market() -> pd.DataFrame:
    df = _read("mart_category_market.csv")
    return _num(df, ["year", "event_count", "valid_bidder_count", "mean_bidders", "median_bidders", "no_bid_rate",
                     "single_bid_rate", "reprocedure_rate", "mean_award_rate", "award_amount", "supplier_count",
                     "total_wins", "hhi_count", "top3_share_count", "new_supplier_rate", "contract_count",
                     "contract_amount", "median_contract_amount", "agency_count", "growth_rate_yoy", "amount_coverage"])


@st.cache_data(ttl=STATS_TTL)
def ytd_market() -> pd.DataFrame:
    df = _read("latest_ytd_market.csv")
    return _num(df, ["year", "event_count", "mean_bidders", "single_bid_rate", "supplier_count", "hhi_count",
                     "new_supplier_rate", "contract_count", "contract_amount"])


@st.cache_data(ttl=STATS_TTL)
def category_examples() -> dict[str, str]:
    """분류 코드 → 가장 흔한 공고명.

    물품분류번호·공공조달분류코드는 EDA 결과에 **이름이 없고 번호만** 있다. 사용자가 알아보도록
    '예: 공고명'을 붙이는 용도이며 분류의 공식 이름이 아니다(공식 이름표는 EDA 담당에게 요청 중).
    """
    # 예시에는 요건이 필요 없다. 전체 문서 근거 재해석/overlay를 실행하지 않는다.
    n = _base_notices()[["item_code", "notice_name"]].dropna()
    return n.groupby("item_code")["notice_name"].agg(lambda s: s.value_counts().index[0]).to_dict()


@st.cache_data(ttl=STATS_TTL)
def categories() -> pd.DataFrame:
    """분류 선택 목록: 현재 공식 product8 품명 적용(2026-10-02 v2), 가나다·코드순. 집계·키 보존."""
    m = category_market()
    if "classification_type" in m.columns and "category_value" in m.columns:
        agg = (m.groupby(["procurement_type", "item_code", "classification_type", "category_value"], dropna=False)
               .agg(events=("event_count", "sum")).reset_index())
    else:
        # v5 마트의 분류 이름·분류체계는 category_catalog가 기준이다.
        catalog = _read("category_catalog.csv")
        catalog_cols = ["procurement_type", "item_code", "classification_type", "category_value"]
        for col in ("item_label", "item_name", "item_name_status"):
            if col in catalog.columns:
                catalog_cols.append(col)
        catalog = catalog[catalog_cols].drop_duplicates(["procurement_type", "item_code"])
        agg = (m.groupby(["procurement_type", "item_code"], dropna=False)
               .agg(events=("event_count", "sum")).reset_index()
               .merge(catalog, on=["procurement_type", "item_code"], how="left", validate="one_to_one"))
    agg["category_value"] = agg["category_value"].fillna("(분류 미상)")
    examples = category_examples()
    # 분류 이름 자료가 없는 번호 분류는 **번호로만** 표시한다(가장 흔한 공고명을 이름처럼 붙이면 실제 품목명으로
    # 오해된다 — 외부 검토 2026-09-28). 공고 예시는 선택 목록과 설명 줄에서 "공고 예"로 분명히 구분해 보여 준다.
    is_code = agg["category_value"].str.fullmatch(r"\d+").fillna(False)
    agg["example"] = agg["item_code"].map(examples).fillna("").str.slice(0, 24)
    kind = agg["classification_type"].fillna("").str.replace(r"\(.*\)", "", regex=True)
    kind = kind.replace({"product8": "물품분류번호"})
    fallback = agg["category_value"].where(~is_code, kind + " " + agg["category_value"])
    if "item_label" in agg.columns:
        label_status = agg.get("item_name_status", pd.Series("", index=agg.index)).fillna("")
        confirmed = label_status.isin(["CONFIRMED", "SOURCE_MATCH"])
        official = agg["item_label"].fillna("").astype(str).str.strip()
        agg["display"] = official.where(confirmed & official.ne(""), fallback)
    else:
        agg["display"] = fallback
    agg = apply_official_names(agg, read_product_name_reference())
    use_example = is_code & agg["example"].ne("") & agg["display"].eq(fallback)
    agg["label"] = agg["display"].where(~use_example, agg["display"] + "  (공고 예: " + agg["example"] + ")")
    return agg.sort_values(["procurement_type", "display", "item_code"], kind="stable")


@st.cache_data(ttl=STATS_TTL)
def category_name_audit():
    catalog = _read("category_catalog.csv")
    market = category_market()
    market_keys = market[["procurement_type", "item_code"]].drop_duplicates()
    if "procurement_type" not in catalog:
        # 과거 오프라인 카탈로그에는 유형 열이 없다. 같은 내부 키의 분석 유형만 연결한다.
        catalog = catalog.merge(market_keys, on="item_code", how="left", validate="one_to_one")
    reference = read_product_name_reference()
    out = catalog_audit(catalog, reference)
    out["화면 표시"] = out["분류키"].map(categories().set_index("item_code")["display"]).fillna("현재 분석 목록에 없음")
    out.attrs["checked_at"] = reference["checked_at"]
    out.attrs["source"] = reference["source"]
    out.attrs["display_policy"] = "현재 공식 product8 품명 · 확정/충돌 모두 적용"
    out.attrs["duplicate_keys"] = int(catalog.duplicated(["procurement_type", "item_code"]).sum())
    out.attrs["missing_catalog_keys"] = int((~market_keys.item_code.isin(catalog.item_code)).sum())
    out.attrs["catalog_only_count"] = int((~catalog.item_code.isin(market.item_code)).sum())
    return out


def category_display(item_code: str, fallback: str = "") -> str:
    d = categories().set_index("item_code")["display"]
    return d.get(item_code, fallback)


@st.cache_data(ttl=STATS_TTL)
def suppliers() -> pd.DataFrame:
    df = _read("mart_supplier_structure.csv")
    df = _num(df, ["year", "award_count", "award_amount", "total_wins", "supplier_count", "count_share",
                   "amount_share"])
    return _bool(df, ["observed_new_supplier"])


@st.cache_data(ttl=STATS_TTL)
def lifecycle() -> pd.DataFrame:
    df = _read("mart_lifecycle.csv")
    df = _num(df, ["n_bidders", "award_amount", "award_rate", "contract_count", "contract_amount",
                   "notice_to_contract_days"])
    df = _bool(df, ["no_bid", "single_bid", "reprocedure"])
    for c in ("notice_date", "opening_date", "first_contract_date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


@st.cache_data(ttl=STATS_TTL)
def followup_monthly() -> pd.DataFrame:
    df = _read("h05_monthly_monitoring.csv")
    df = _num(df, ["initial_notice_count", "matured_30d_count", "confirmed_followup_30d_count",
                   "confirmed_followup_30d_rate"])
    df["month"] = pd.to_datetime(df["month"] + "-01", errors="coerce")
    return df


@st.cache_data(ttl=STATS_TTL, show_spinner=False)
def institutions() -> pd.DataFrame:
    df = _read("mart_institution.csv")
    return _num(df, ["notice_count", "budget", "contract_count", "contract_amount"])


@st.cache_data(ttl=STATS_TTL, show_spinner=False)
def agency_names() -> dict[str, str]:
    inst = institutions()
    return dict(zip(inst["agency_code"], inst["agency_name"]))


@st.cache_data(ttl=NOTICE_TTL, show_spinner=False)
def _base_notices() -> pd.DataFrame:
    """공고 탐색기용 표(실시간 공고 표를 가정). 한 행 = 공고 1건의 1개 차수."""
    df = _read("mart_notice_eligibility.csv")
    df = _num(df, ["license_count", "region_count"])
    for c in ("notice_date", "bid_close_date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    names = agency_names()
    for col, code_col, raw_col in (("demand_agency_name", "demand_agency_code", "dminsttNm"),
                                   ("notice_agency_name", "notice_agency_code", "ntceInsttNm")):
        codes = df.get(code_col, pd.Series("", index=df.index, dtype="string"))
        standard = df.get(col, pd.Series(pd.NA, index=df.index, dtype="string")).astype("string").str.strip().replace("", pd.NA)
        standard = standard.mask(standard.eq(codes))
        raw = df.get(raw_col, pd.Series(pd.NA, index=df.index, dtype="string")).astype("string").str.strip().replace("", pd.NA)
        df[col] = raw.fillna(standard).fillna(codes.map(names)).fillna(codes)
    if "eligibility_notice_url" in df.columns:
        df["notice_url"] = df["notice_url"].fillna("").replace("", pd.NA).fillna(df["eligibility_notice_url"])
    df["category_value"] = df["category_value"].fillna("(분류 미상)")
    return df


def notices() -> pd.DataFrame:
    """공고 원본은 캐시하고 근거 보완은 매 호출 재연결해 조회 직후 반영한다."""
    from service.requirement_overlay import overlay
    from service.source import read_requirement_evidence
    return overlay(_base_notices(), read_requirement_evidence())


@st.cache_data(ttl=NOTICE_TTL, show_spinner=False)
def _stored_notices() -> pd.DataFrame:
    """목록용 DB 저장 요건만. 근거 사본 읽기·공식 조회·문서 해석을 하지 않는다."""
    from service.requirement_overlay import usable_values
    out = _base_notices().copy()
    for kind in ('license', 'region'):
        if kind + '_values' not in out:
            out[kind + '_values'] = ''
        if kind + '_state' not in out:
            out[kind + '_state'] = '미확인'
        values = out[kind + '_values'].map(lambda value: ' | '.join(usable_values(value)))
        out[kind + '_values'] = values
        missing = out[kind + '_state'].ne('조건없음') & (out[kind + '_state'].ne('제한있음') | values.eq(''))
        out.loc[missing, kind + '_state'] = '미확인'
        out[kind + '_review_status'] = '미조회'
        out.loc[missing, kind + '_review_status'] = '상세 확인'
        out[kind + '_requires_review'] = False
        out[kind + '_evidence_quote'] = ''
    out['requirement_search_text'] = out.license_values + ' ' + out.region_values
    out['requirement_evidence'] = pd.Series([None] * len(out), index=out.index, dtype=object)
    out['requirement_other_summary'] = ''
    out['requirement_checked_at'] = ''
    return out


def stored_notices() -> pd.DataFrame:
    """DB와 저장된 공식 API 값만. 원문/첨부 읽기·문서 추출·네트워크 조회는 하지 않는다."""
    from service.requirement_overlay import overlay
    from service.source import read_api_requirement_evidence
    stored = _stored_notices()
    records = read_api_requirement_evidence()
    out = overlay(stored, records) if records else stored
    for kind in ('license', 'region'):
        missing = out[kind + '_state'].eq('미확인')
        out.loc[missing, kind + '_review_status'] = '상세 확인'
    # DB에만 있는 값도 검색 대상이다. 문서 발췌/조건 후보는 목록에 넣지 않는다.
    out['requirement_search_text'] = out.license_values + ' ' + out.region_values
    return out


def favorite_notices(ids) -> pd.DataFrame:
    """즐겨찾기 최대10건에만 저장 근거를 연결한다. 전체 공고 보완은 생략한다."""
    from service.requirement_overlay import overlay
    from service.source import read_notice_requirement_evidence
    from service.requirement_overlay import identity
    selected = _stored_notices()
    selected = selected[selected.notice_id.isin(list(dict.fromkeys(ids))[:10])].drop_duplicates('notice_id')
    if not len(selected):
        return selected
    records=[read_notice_requirement_evidence(*identity(row)) for row in selected.to_dict('records')]
    return overlay(selected,[r for r in records if r is not None])


def _clear_notices():
    _base_notices.clear()
    _stored_notices.clear()


notices.clear = _clear_notices
stored_notices.clear = _stored_notices.clear


def agency_mask(frame: pd.DataFrame, role: str, selected) -> pd.Series:
    """기관명과 코드로 저장된 기존 검색을 모두 비교한다. 원본 코드는 변경하지 않는다."""
    stem = "demand" if role == "수요기관" else "notice"
    mask = frame[f"{stem}_agency_name"].isin(selected)
    code_col = f"{stem}_agency_code"
    if code_col in frame:
        mask |= frame[code_col].isin(selected)
    return mask


@st.cache_data(ttl=STATS_TTL)
def license_names() -> list[str]:
    """공고에 나온 면허 이름 목록(회사 보유 면허 입력용). '이름/코드'에서 이름만."""
    vals = stored_notices()["license_values"].dropna()
    names = {v.strip().rsplit("/", 1)[0].strip() for s in vals for v in s.split("|") if v.strip()}
    return sorted(n for n in names if n)  # '/코드'처럼 이름이 빈 값은 뺀다(빈 선택지로 보임)


@st.cache_data(ttl=STATS_TTL)
def provinces() -> list[str]:
    """시·도 목록(회사 소재지 입력용). 허용 지역 값 중 시·군이 붙지 않은 것."""
    vals = stored_notices()["region_values"].dropna()
    names = {v.strip() for s in vals for v in s.split("|") if v.strip() and " " not in v.strip()}
    return sorted(names)


@st.cache_data(ttl=STATS_TTL)
def competition_levels() -> pd.DataFrame:
    """분류별 최근 연도 경쟁 수준. 같은 조달 유형 안에서 참가업체 중앙값을 3등분(낮음/보통/높음).

    화면 표시용 구분이며 예측이 아니다. 표본 부족이면 '표본 적음'.
    """
    m = category_market().sort_values("year").groupby("item_code").tail(1).copy()
    m["level"] = ""
    for _, idx in m.groupby("procurement_type").groups.items():
        sub = m.loc[idx, "median_bidders"]
        if sub.notna().sum() >= 3:
            m.loc[idx, "level"] = pd.qcut(sub.rank(method="first"), 3, labels=["낮음", "보통", "높음"]).astype(str)
    small = m["competition_sample_status"].fillna("").str.contains("부족") | m["median_bidders"].isna()
    m.loc[small, "level"] = "표본 적음"
    return m[["item_code", "year", "level", "median_bidders", "single_bid_rate", "top3_share_count", "mean_award_rate",
              "event_count"]]


@st.cache_data(ttl=STATS_TTL)
def contract_days() -> dict[str, float]:
    """분류별 공고→첫 계약 소요일 중앙값."""
    lc = lifecycle()
    return lc.groupby("item_code")["notice_to_contract_days"].median().dropna().to_dict()


@st.cache_data(ttl=STATS_TTL)
def link_quality() -> pd.DataFrame:
    return _num(_read("link_quality.csv"), ["numerator", "denominator", "rate"])


@st.cache_data(ttl=STATS_TTL)
def detail_coverage() -> pd.DataFrame:
    return _num(_read("detail_coverage.csv"), ["year", "contract_count", "contracts_with_linked_details",
                                               "detail_contract_coverage", "eligible_detail_contract_coverage"])


@st.cache_data(ttl=STATS_TTL)
def data_quality() -> pd.DataFrame:
    return _num(_read("mart_data_quality.csv"), ["year", "approx_rows", "value", "numerator", "denominator",
                                                   "input_rows", "review_excluded_rows", "missing_date_rows",
                                                   "future_date_rows", "before_baseline_rows", "included_rows",
                                                   "count", "rate"])


@st.cache_data(ttl="5m")
def pending_institutions() -> pd.DataFrame:
    """관리자 화면용 기관 판정 대기 목록(읽기 전용).

    운영 원천은 S3 `reference/institutions/Allowlist_Pending.xlsx`다. 프로토타입은 로컬 사본이 있으면 읽고,
    없으면 빈 표를 돌려준다. 판정 입력은 여기서 쓰지 않는다(수집기 `run.py judge`가 잠금과 함께 쓴다).
    """
    cols = ["institution_code", "institution_name_raw", "institution_roles", "first_observed_date",
            "classification_reason", "manual_is_defense"]
    df = read_pending_institutions(cols)
    df = df[[c for c in cols if c in df.columns]]
    return df[df["manual_is_defense"].fillna("").str.upper().isin(["", "NAN"])] if "manual_is_defense" in df else df
