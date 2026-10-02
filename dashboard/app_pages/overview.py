"""시장 개요 — 사이드바 필터(사용자 지정 2026-09-28)로 거른 자료를 다시 계산해 보여 준다.

필터: 분석 기간, 조달 유형, 기관(수요기관/공고기관), 품목·업종, 계약방법(자료 없음·비활성), 지역, 금액 범위, 낙찰·유찰 여부.
- 공고 수: 공고 표(`mart_notice_eligibility`) 행 수 — 필터 없으면 EDA `notice_count`와 같다(2026-09-28 확인).
- 개찰·경쟁·계약: 개찰 1건 단위 자료(service/metrics.py) — 필터 없으면 EDA와 같다(tests/test_metrics.py).
- 금액·낙찰/유찰은 개찰에만 있는 정보라 공고 수 그래프에는 적용되지 않는다(화면에 표시).
거르기·계산은 service/queries.py가 하고, 이 파일은 위젯과 그리기만 한다.
"""

import pandas as pd
import streamlit as st

from service import data, metrics, queries
from service.filters import YEAR_RANGE, OverviewFilter
from view.charts import card, kpi_tiles
from view.plotly_charts import bar_figure, line_figure, show, show_donut
from view.fmt import CONTRACT_AMOUNT_MESSAGES, num, pct, region_display
from view.pdf import Report
from view.navigation import page_header
from view.help import help_label
from view.search_summary import search_summary
from view.contract_patterns import show_contract_patterns
from view.fmt import compact_filter_values
from view.widgets import (agency_filter, amount_filter, detail_expander, filter_area, pdf_button, period_filter,
                          sidebar_toolbar, summarize_tags)

page_header("overview")
export_slot = st.session_state._export_slot
with st.spinner("시장 자료를 불러오는 중입니다…"):  # 첫 접속 때 빈 화면처럼 보이지 않게
    _ = (metrics.events(), data.notices())
    cats = data.categories()

OV_DEFAULTS = {"ov_years": YEAR_RANGE, "ov_types": [], "ov_agency_role": "수요기관", "ov_agency_수요기관": [],
               "ov_agency_공고기관": [], "ov_items": [], "ov_region": None, "ov_amount": [], "ov_outcome": []}
item_labels = dict(zip(cats["item_code"], cats["label"]))
with filter_area():
    sidebar_toolbar("ov", OV_DEFAULTS)
    years = period_filter("ov", YEAR_RANGE)
    types = st.pills("조달 유형", data.TYPES, selection_mode="multi", key="ov_types",
                     persist_state="session") or list(data.TYPES)
    st.caption("현재: 전체 유형 (미선택 시 전체)" if not st.session_state.get("ov_types")
               else "현재: " + "·".join(types))
    active_detail = sum(bool(st.session_state.get(k)) for k in
                        (f"ov_agency_{st.session_state.get('ov_agency_role', '수요기관')}", "ov_items", "ov_region",
                         "ov_amount", "ov_outcome"))
    with detail_expander("ov", active_detail):
        role, agencies = agency_filter("ov", queries.overview_agency_options(),
                                       labels_by_role=queries.agency_option_labels())
        items = st.multiselect("품목·업종 (번호 또는 공고 예로 검색)", cats["item_code"].tolist(), key="ov_items",
                               format_func=lambda c: item_labels.get(c, c), placeholder="전체 품목", persist_state="session")
        summarize_tags(".st-key-ov_items", len(items))
        help_label("지역 (참가 가능)", "이 지역 업체가 참가할 수 있는 공고(지역 제한 없음 포함)만 봅니다.", key="help_ov_region")
        region = st.selectbox("지역 (참가 가능)", data.provinces(), index=None, placeholder="전체 지역", key="ov_region",
                              format_func=region_display,
                              persist_state="session", label_visibility="collapsed")
        amounts = amount_filter("ov", list(metrics.AMOUNT_BINS), metrics.AMOUNT_NOTE)
        outcomes = st.pills("낙찰·유찰 여부", metrics.OUTCOMES, selection_mode="multi", key="ov_outcome",
                            persist_state="session")
        st.caption(":gray[아무것도 고르지 않으면 전체 표시됩니다.]")


# ---- 계산(service) ----
res = queries.overview_view(OverviewFilter(tuple(years), tuple(types), role, tuple(agencies), tuple(items), region,
                                           tuple(amounts or ()), tuple(outcomes or ())))
ev = res["ev"]
filtered = any([tuple(years) != YEAR_RANGE, st.session_state.get("ov_types"), agencies, items, region, amounts,
                outcomes])

search_summary([f"개찰 연도: {years[0]}~{years[1]}년", "유형: " + compact_filter_values(types, separator="·"),
                f"{role}: {compact_filter_values(agencies) if agencies else '전체'}",
                "분류: " + (compact_filter_values([item_labels.get(i, i) for i in items]) if items else "전체"),
                f"참가 지역: {region_display(region) if region else '전체'}",
                "낙찰금액: " + (compact_filter_values(amounts) if amounts else "전체"),
                "낙찰·유찰: " + (compact_filter_values(outcomes) if outcomes else "전체")], "search_filter_summary_ov")
badges = []
if filtered:
    badges.append(":blue-badge[필터 적용 · 대시보드 재계산]")
st.markdown(" ".join(badges) + f"  {years[0]}~{years[1]}년 · 조달 유형: **{', '.join(types)}**")

if res["empty"]:
    st.info("선택한 조건에 해당하는 자료가 없습니다.", icon=":material/filter_alt_off:")
    st.stop()

summ = res["summary"]
kpis = [("공고 수", f"{res['notice_total']:,}건"), ("개찰 수", f"{summ['events']:,}건"),
        ("계약 건수", f"{num(summ['contract_count'])}건"), ("단독입찰 비율", pct(summ["single_bid_rate"]))]
kpi_tiles([
    {"label": kpis[0][0], "value": kpis[0][1], "color": "blue", "help": "선택 기간·조건의 공고(차수 포함)"},
    {"label": kpis[1][0], "value": kpis[1][1], "color": "violet", "help": "선택 기간·조건의 개찰"},
    {"label": kpis[2][0], "value": kpis[2][1], "color": "green",
     "help": "계약일 기준으로 집계한 분석용 대표 계약 수"},
    {"label": kpis[3][0], "value": kpis[3][1], "color": "orange", "help": "참여가 있었던 개찰 중 업체가 1곳뿐인 비율"},
], prefix="ov")


def year_label(y: int) -> str:
    return str(y)


notice_year = res["notice_year"]
notice_year["연도"] = notice_year["year"].map(year_label)
ev_year = res["event_year"]
if len(ev_year):
    ev_year["연도"] = ev_year["year"].map(year_label)

tab_size, tab_comp, tab_major, tab_contract = st.tabs(["시장 규모", "경쟁 수준", "주요 분야·기관", "계약 특성"])
with tab_size:
    left, right = st.columns([1.8, 1])
    with left, card("연도별 공고 수는 어떻게 변했나요?", "유형별 국방 공고 수(건)"):
        with st.container(key="ov_size_plot_left"):
            show(line_figure(notice_year, "연도", "notice_count", y_title="공고 수 (건)",
                             series="procurement_type", integer=True), key="ov_notices_chart")
    share = res["share"]
    with right, card("어느 유형 공고가 많나요?", f"{years[0]}~{years[1]}년 유형별 공고 비중"):
        if len(share):
            with st.container(key="ov_size_plot_right"):
                show_donut(share)
    krw = res["contract_type_year"].copy()
    krw["연도"] = krw["year"].astype(str)
    krw = krw[krw["procurement_type"] != "외자"].assign(amount_eok=lambda d: d["contract_amount"] / 1e8)
    with card("연도별 계약금액 (외자 제외)", "원화 계약 · 개별 축은 유형 내부 추이 비교용이며 축 크기가 서로 다릅니다."):
        amount_view = st.segmented_control("금액 비교 방식", ["유형별 개별 축", "전체 규모 비교"], default="유형별 개별 축", required=True, key="ov_amount_view", label_visibility="collapsed")
        amount_state = metrics.contract_amount_availability(krw)
        amount_types = [typ for typ in ["공사", "물품", "용역"] if typ in types]
        if not res["contract_supported"]:
            st.info("기관·지역·금액·낙찰/유찰 필터는 계약일 기준 계약 집계에 적용되지 않아 금액을 표시하지 않습니다.",
                    icon=":material/info:")
        elif not amount_types:
            st.caption("외자 계약은 통화별로 확인해야 합니다. 원화 계약금액 비교에서는 제외합니다.")
        elif amount_view == "전체 규모 비교":
            if amount_state != "available":
                st.info(CONTRACT_AMOUNT_MESSAGES[amount_state], icon=":material/info:")
            else:
                show(bar_figure(krw, "연도", "amount_eok", value_title="계약금액 (억원)",
                                series="procurement_type", height=280), key="ov_amount_total_chart")
        else:
            # 반응형 열을 사용하고 각 유형에 0 기준 독립 선형 축을 둔다.
            slots = st.columns(len(amount_types))
            for slot, typ in zip(slots, amount_types):
                with slot:
                    st.markdown(f"**{typ}**")
                    sample = krw[krw["procurement_type"] == typ] if len(krw) else krw
                    sample_state = metrics.contract_amount_availability(sample)
                    if sample_state != "available":
                        st.info(CONTRACT_AMOUNT_MESSAGES[sample_state], icon=":material/info:")
                    else:
                        show(bar_figure(sample, "연도", "amount_eok",
                                        value_title="계약금액 (억원)", series="procurement_type", show_legend=False,
                                        height=252, max_category_ticks=4), key=f"ov_amount_{typ}_chart")

with tab_comp:
    c1, c2 = st.columns(2)
    with c1, card("개찰 한 번에 몇 곳이 참여하나요?", "개찰 1건당 참가업체 수의 중앙값. 공사는 수백 곳이라 로그 눈금으로 그렸습니다."):
        if len(ev_year):
            show(line_figure(ev_year[ev_year["median_bidders"] > 0], "연도", "median_bidders",
                             y_title="참가업체 수 (곳, 로그 눈금)", series="procurement_type", integer=True,
                             log=True, ticks=[1, 3, 10, 30, 100, 300, 1000]), key="ov_bidders_chart")
    with c2, card("단독입찰 비율은 얼마나 되나요?", "단독입찰 비율 = 참여 업체가 1곳뿐인 개찰 ÷ 참여가 있었던 개찰"):
        if len(ev_year):
            show(line_figure(ev_year, "연도", "single_bid_rate", y_title="단독입찰 비율 (%)",
                             series="procurement_type", percent=True), key="ov_single_chart")

top_ag, top_cat = res["top_agencies"], res["top_categories"]
with tab_major:
    c3, c4 = st.columns(2)
    with c3, card(f"공고를 가장 많이 낸 {role} TOP 10", f"{years[0]}~{years[1]}년 공고 수"):
        show(bar_figure(top_ag, "agency", "notice_count", category_title=None, value_title="공고 수 (건)",
                        horizontal=True, sort_desc=True, integer=True,
                        height=max(420, 34 * max(len(top_ag), len(top_cat)) + 100)), key="ov_agencies_chart")
    with c4, card("개찰이 많은 품목·업종 TOP 10", f"{years[0]}~{years[1]}년 개찰 수"):
        show(bar_figure(top_cat, "분류", "event_count", category_title=None, value_title="개찰 수 (건)",
                        horizontal=True, sort_desc=True, integer=True, series="procurement_type",
                        height=max(420, 34 * max(len(top_ag), len(top_cat)) + 100)), key="ov_categories_chart")

with tab_contract:
    from service.institution_names import contract_institution_names
    show_contract_patterns(res["contract_type_year"], res["contract_supported"], data.institutions(),
                           years=years, types=types, names=contract_institution_names(data.defense_institutions()))

conditions = [f"{years[0]}~{years[1]}년", f"유형 {', '.join(types)}"]
if agencies:
    conditions.append(f"{role} {len(agencies)}곳")
if region:
    conditions.append(f"지역 {region_display(region)}")


def build_pdf() -> bytes:
    rep = Report("국방 조달 시장 개요", " · ".join(conditions), footer="Frontline Data · 국방 조달 탐색")
    rep.kv(kpis)
    pivot = notice_year.pivot_table(index="year", columns="procurement_type", values="notice_count", aggfunc="sum")

    def draw_notices(ax):
        for t in pivot.columns:
            ax.plot(pivot.index, pivot[t], marker="o", label=t)
        ax.set_title("연도별 공고 수", fontsize=10)
        ax.set_xlabel("연도", fontsize=8)
        ax.set_ylabel("공고 수 (건)", fontsize=8)
        ax.legend()

    rep.heading("연도별 추이").chart(draw_notices)
    if len(ev_year):
        t = ev_year[["procurement_type", "연도", "events", "median_bidders", "single_bid_rate", "contract_count"]].copy()
        t["single_bid_rate"] = t["single_bid_rate"].map(pct)
        t.columns = ["유형", "연도", "개찰(건)", "참가업체(곳, 중앙값)", "단독입찰", "계약(건)"]
        rep.table(t, max_rows=40)
    rep.heading(f"공고를 가장 많이 낸 {role} TOP 10").table(
        top_ag.rename(columns={"agency": "기관", "notice_count": "공고 수(건)"}))
    return rep.build()


with export_slot:
    pdf_button("PDF", f"국방조달_시장개요_{years[0]}-{years[1]}.pdf", build_pdf, key="ov_pdf", type="tertiary", help="PDF 내보내기")
