"""품목 분석 — 분류 하나의 시장·경쟁 / 진입 조건 / 낙찰 업체.

사이드바 필터(사용자 지정 2026-09-28): 조달 유형, 품목·업종(번호 또는 공고 예), 분석 기간, 기관, 계약방법(자료 없음·비활성),
금액 범위. 요약·그래프는 개찰 1건 단위 자료를 걸러 다시 계산한다(service/queries.py·metrics.py — 필터 없으면 EDA와 같은 값).
업체 집중도·낙찰 업체는 EDA 집계라 기간 필터만 적용된다.
"""

import pandas as pd
import streamlit as st

from service import data, metrics, queries
from service.filters import YEAR_RANGE, ItemFilter
from view.charts import ITEM_CHART_H, card, kpi_tiles
from view.plotly_charts import bar_figure, histogram_figure, line_figure, show
from view.fmt import CONTRACT_AMOUNT_MESSAGES, num, pct, year_delta, region_display
from view.pdf import Report
from view.navigation import page_header
from view.reference_table import reference_table
from view.assets import procurement_icon_html
from view.help import help_label
from view.search_summary import search_summary
from view.entry_summary import entry_summary
from view.fmt import compact_filter_values
from view.widgets import (agency_filter, amount_filter, detail_expander, filter_area, pdf_button, period_filter,
                          pick_category, safe_name, sidebar_toolbar)

page_header("item")
export_slot = st.session_state._export_slot
with st.spinner("품목 자료를 불러오는 중입니다…"):
    _ = (metrics.events(), data.categories(), data.notices(), data.suppliers(), data.competition_levels())

# ---- 사이드바: [필터 초기화] → 조달 유형·품목 → 기간 → 상세 조건(기관·금액, 접힘) ----
item_categories = data.categories()
default_category = item_categories.loc[item_categories["procurement_type"].eq("물품")
                                      & item_categories["category_value"].eq("23261507")]
default_item = default_category.iloc[0]["item_code"] if len(default_category) == 1 else None
if default_item is None:
    st.warning("기본 분류 ‘3차원프린터 (23261507)’를 현재 자료에서 유일하게 확인할 수 없습니다. 현재 목록의 대표 분류를 표시합니다.")
IT_DEFAULTS = {"it_type": "물품", "it_item": default_item, "sel_item": default_item,
               "it_years": YEAR_RANGE, "it_agency_role": "수요기관", "it_agency_수요기관": [], "it_agency_공고기관": [],
               "it_amount": []}
with filter_area():
    sidebar_toolbar("it", IT_DEFAULTS)
sidebar_role = st.session_state.get("it_agency_role", "수요기관")
sidebar_counts = queries.item_event_counts(ItemFilter(
    tuple(st.session_state.get("it_years", YEAR_RANGE)), sidebar_role,
    tuple(st.session_state.get(f"it_agency_{sidebar_role}") or ()),
    tuple(st.session_state.get("it_amount") or ())))
cat = pick_category("it", item_categories, data.TYPES, event_counts=sidebar_counts, default_item=default_item)
if cat is None:
    st.stop()
code, ptype = cat["item_code"], cat["procurement_type"]

with filter_area():
    years = period_filter("it", YEAR_RANGE)
    active_detail = int(bool(st.session_state.get(f"it_agency_{st.session_state.get('it_agency_role', '수요기관')}")))
    active_detail += int(bool(st.session_state.get("it_amount")))
    with detail_expander("it", active_detail):
        role, agencies = agency_filter("it", queries.item_agency_options(code),
                                       labels_by_role=queries.agency_option_labels())
        amounts = amount_filter("it", list(metrics.AMOUNT_BINS), metrics.AMOUNT_NOTE)

# ---- 계산(service) ----
now = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None)
res = queries.item_view(code, ItemFilter(tuple(years), role, tuple(agencies), tuple(amounts or ())), now)
ev, filtered = res["ev"], res["filtered"]

# ---- 제목 ----
level = res["level"]
search_summary([f"유형: {ptype}", f"분류: {cat['display']}", f"개찰 연도: {years[0]}~{years[1]}년",
                f"{role}: {compact_filter_values(agencies) if agencies else '전체'}",
                f"낙찰금액: {compact_filter_values(amounts) if amounts else '전체'}"], "search_filter_summary_it")
# 분석을 본 뒤 바로 할 수 있는 행동: 이 분류의 진행 중 공고로 이동
open_n = res["open_n"]


def _go_open_notices():
    st.session_state.nt_item = code
    st.session_state.nt_open_only = True
    st.session_state.nt_dates = ()
    st.session_state.nt_types = sorted(set(st.session_state.get("nt_types") or []) | {ptype}, key=data.TYPES.index)


with st.container(key="item_context", gap="xsmall"):
    st.space(8)
    type_icon = procurement_icon_html(ptype)
    with st.container(horizontal=True, gap="xsmall", vertical_alignment="center",
                      width="content", wrap=False, key="item_category_heading"):
        if type_icon:
            with st.container(width=36, key="item_procurement_icon"):
                st.html(type_icon, width=36)
            st.subheader(cat['display'], anchor=False)
        else:
            st.subheader(f"[{ptype}] {cat['display']}", anchor=False)
    # 두 기준 문구와 행동을 같은 행에 둔다. 좁은 화면에서는 자연스럽게 줄바꿈한다.
    # 빈 개찰 결과에서도 공고 이동은 유지하고, 기준 문구는 계산 후 슬롯에 채운다.
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="bottom",
                      key="item_context_row", gap="small"):
        with st.container(key="item_context_text", gap="xsmall"):
            with st.container(horizontal=True, gap="xsmall", vertical_alignment="center", key="item_context_meta"):
                st.caption(f"선택 기간 추이: {years[0]}~{years[1]}년 · 개찰 {len(ev):,}건", width="content")
                if level and level != "표본 적음":
                    with st.popover(f"경쟁 {level} · {int(res['level_year'])}년 분류 전체 기준", icon=":material/info:", type="tertiary", key="it_competition_criteria"):
                        st.caption("선택한 분석 기간·기관·낙찰금액 조건으로 다시 평가한 등급이 아닙니다. 분류 전체의 최근 연도 기준입니다.")
                        st.caption("경쟁 수준: 같은 조달 유형의 분류별 최근 연도 참가업체 중앙값 순위를 낮음·보통·높음으로 3등분한 상대 비교입니다. 동률은 원본 분류 순서로 나누며, 절대 진입 난이도가 아닙니다.")
                if filtered:
                    st.markdown(":blue-badge[선택 조건 적용]")
            kpi_basis_slot = st.empty()
        with st.container(horizontal_alignment="right", width="content", key="item_context_action"):
            go_notices = st.button(f"진행 중 공고 {open_n}건 보기", icon=":material/campaign:", type="primary",
                                  disabled=open_n == 0, on_click=_go_open_notices, key="it_go_notices", width="content")

if go_notices:
    st.switch_page("app_pages/notices.py")

if ev.empty:
    st.info("선택한 조건에 해당하는 개찰이 없습니다.", icon=":material/filter_alt_off:")
    st.stop()

summ, yearly, top3 = res["summary"], res["yearly"], res["top3"]
yearly["연도"] = yearly["year"].astype(str)

kcur, kprev, kyear = res["kpi_current"], res["kpi_previous"], res["kpi_year"]
no_previous_year = kyear == 2020
comparison_note = "전년 비교 자료 없음 (데이터는 2020년부터 제공)" if no_previous_year else f"{kyear - 1}년 전체 대비"
kpi_basis = f"상단 지표: {kyear}년 요약{' (부분연도)' if res['kpi_partial'] else ''} · {comparison_note}"
kpi_basis_slot.caption(kpi_basis)
kpis = [("참가업체 수 (중앙값)", f"{num(kcur['median_bidders'], 1)}곳"),
        ("단독입찰 비율", pct(kcur["single_bid_rate"])),
        ("상위 3개 업체 점유", pct(kcur["top3"])),
        ("계약 건수", f"{num(kcur['contract_count'])}건")]
kpi_items = [
    {"label": kpis[0][0], "value": kpis[0][1], "color": "blue", "delta": year_delta(kcur['median_bidders'], kprev['median_bidders'], '곳'), "help": "기준 연도·조건의 개찰 1건당 참가업체 수"},
    {"label": kpis[1][0], "value": kpis[1][1], "color": "orange", "delta": year_delta(kcur['single_bid_rate'], kprev['single_bid_rate'], '%p'), "help": "참여가 있었던 개찰 중 업체가 1곳뿐인 비율"},
    {"label": kpis[2][0], "value": kpis[2][1], "color": "violet",
     "delta": year_delta(kcur['top3'], kprev['top3'], '%p'), "help": "기준 연도 낙찰 건수 기준. 기관·금액 필터 적용 시 계산하지 않습니다."},
    {"label": kpis[3][0], "value": kpis[3][1], "color": "green", "delta": year_delta(kcur['contract_count'], kprev['contract_count'], '건'), "help": "계약일 기준 계약 수. 기관·금액 상세 필터 적용 시 비교 불가로 표시하지 않습니다."},
]
if no_previous_year:
    for item in kpi_items:
        item.update(delta=None, delta_description=None, note=":gray[전년 비교 자료 없음]")
kpi_tiles(kpi_items, prefix="it")


licenses, region_tbl = res["licenses"], res["regions"]
lic_share, reg_share = res["license_share"], res["region_share"]
days, top_agencies = res["days"], res["top_agencies"]
checks = pd.DataFrame([
    ("경쟁 수준", f"개찰 1건당 참가업체 {num(summ['median_bidders'], 1)}곳 (중앙값)", "많을수록 가격 경쟁이 치열합니다."),
    ("단독입찰", pct(summ["single_bid_rate"]), "높으면 참여 업체가 적은 분야입니다. 규격·자격이 좁은지 원문 확인."),
    ("업체 쏠림", f"상위 3개 업체가 낙찰의 {pct(top3)}" if top3 is not None else "–",
     "높으면 기존 업체가 대부분을 가져갑니다."),
    ("면허 제한", f"공고의 {pct(lic_share.get('제한있음'))}",
     "대표 면허: " + (", ".join(licenses["조건"].head(3)) if len(licenses) else "없음")),
    ("지역 제한", f"공고의 {pct(reg_share.get('제한있음'))}",
     "자주 허용된 지역: " + (", ".join(region_tbl["조건"].head(3).map(region_display)) if len(region_tbl) else "없음")),
    ("계약까지 걸린 날", f"{days.median():.0f}일 (중앙값)" if len(days) else "–", "자금·생산 계획에 참고하세요."),
    ("주요 수요기관", ", ".join(top_agencies.index) if len(top_agencies) else "–", "공고 수가 많은 순입니다."),
], columns=["확인 항목", "관측값", "설명"])
checks.insert(2, "기준", [
    f"{years[0]}~{years[1]}년 개찰", f"{years[0]}~{years[1]}년 개찰",
    f"{res['top3_year']}년 분류 전체 낙찰" if res["top3_year"] is not None else "–",
    f"{years[0]}~{years[1]}년 공고일", f"{years[0]}~{years[1]}년 공고일",
    f"{years[0]}~{years[1]}년 개찰에 연결된 계약", f"{years[0]}~{years[1]}년 공고일",
])

top_sup = res["suppliers"]

tab_market, tab_entry, tab_sup = st.tabs(["시장·경쟁", "진입 조건", "낙찰 업체"])

long = yearly.melt(id_vars="연도", value_vars=["single_bid_rate", "reprocedure_rate", "no_bid_rate"],
                   var_name="지표", value_name="비율")
long["지표"] = long["지표"].map({"single_bid_rate": "단독입찰", "reprocedure_rate": "재입찰", "no_bid_rate": "무응찰"})

with tab_market:  # 그래프 4개를 2×2로(사용자 지시 2026-09-29). 같은 줄 카드는 같은 높이.
    row1, row2 = st.columns(2), st.columns(2)
    market_amount = st.session_state.get("it_market_measure") == "계약 금액"
    market_title = "해마다 계약금액은 얼마였나요?" if market_amount else "해마다 개찰이 몇 번 있었나요?"
    market_note = "개찰에 연결된 계약금액의 연도별 합계입니다." if market_amount else "개찰 수가 많을수록 기회가 자주 나옵니다."
    with row1[0], card(market_title, market_note):
        measure = st.segmented_control("시장 지표", ["개찰 건수", "계약 금액"], default="개찰 건수", required=True, key="it_market_measure", label_visibility="collapsed")
        field, unit = ("events", "개찰 수 (건)") if measure == "개찰 건수" else ("contract_eok", "계약금액 (억원)")
        amount_state = metrics.contract_amount_availability(yearly) if measure == "계약 금액" else "available"
        if measure == "계약 금액" and res["detail_filter"]:
            st.info("기관·낙찰금액 상세 필터는 계약일 기준 계약 집계에 적용되지 않아 금액을 표시하지 않습니다.",
                    icon=":material/info:")
        elif amount_state == "no_linked_contracts":
            st.info(CONTRACT_AMOUNT_MESSAGES[amount_state], icon=":material/info:")
        elif ptype == "외자" and measure == "계약 금액":
            st.caption("외자 계약은 통화별로 확인해야 합니다. 원화 합계에 포함하지 않습니다.")
        elif amount_state != "available":
            st.info(CONTRACT_AMOUNT_MESSAGES[amount_state], icon=":material/info:")
        else:
            chart_yearly = yearly.assign(contract_eok=yearly["contract_amount"] / 1e8)
            show(bar_figure(chart_yearly, "연도", field, value_title=unit,
                            integer=measure == "개찰 건수", height=ITEM_CHART_H), key="it_events_chart")
    with row1[1], card("개찰 한 번에 몇 곳이 참여하나요?", "개찰 1건당 참가업체 수. 많을수록 경쟁이 치열합니다."):
        center = st.segmented_control("참가업체 집계", ["중앙값", "평균값"], default="중앙값", required=True, key="it_bidder_measure", label_visibility="collapsed")
        bidder_field = "median_bidders" if center == "중앙값" else "mean_bidders"
        show(line_figure(yearly, "연도", bidder_field, y_title=f"참가업체 수 ({center}, 곳)",
                         integer=True, height=ITEM_CHART_H), key="it_bidders_chart")
    # 같은 세로 거리에는 같은 비율 차이가 대응하도록 0 기준 선형 축을 사용한다.
    with row2[0], card("단독입찰·재입찰·무응찰 비율은?", "개찰 가운데 각 경우가 차지한 비율입니다."):
        show(line_figure(long, "연도", "비율", y_title="비율 (%)", series="지표",
                         order=["단독입찰", "재입찰", "무응찰"], percent=True, height=ITEM_CHART_H), key="it_rates_chart")
    with row2[1], card("공고부터 계약까지 며칠 걸리나요?",
              f"중앙값 {days.median():.0f}일 · 계약이 연결된 {len(days):,}건" if len(days) else "표시할 항목이 없습니다."):
        if len(days):
            threshold = days.quantile(0.98)
            tail_count = int((days > threshold).sum())
            help_label("분포 표시 기준", f"긴 기간에 축이 과도하게 늘어나지 않도록 {threshold:.1f}일을 넘는 {tail_count:,}건을 경계 구간에 모아 표시합니다. 상위 약 2%의 표시용 처리이며, 위 중앙값은 원본 일수로 계산합니다.", key="help_it_days_distribution")
            clipped = pd.DataFrame({"days": days.clip(upper=threshold)})
            show(histogram_figure(clipped["days"], x_title="공고부터 첫 계약까지 (일)", height=ITEM_CHART_H), key="it_days_chart")

with tab_entry:
    entry_summary(checks, level=level, level_year=res["level_year"])
    entry_cols = st.columns(2)
    # 면허 축의 두 줄 라벨이 서로 겹치지 않도록 같은 줄의 두 그래프 높이를 맞춘다.
    entry_height = max(220, 48 * max(len(licenses), len(region_tbl)) + 56)
    with entry_cols[0], card("어떤 면허를 요구하나요?", "면허 제한이 있는 공고에서 자주 나온 면허 (상위 10)"):
        if len(licenses):
            show(bar_figure(licenses, "조건", "공고 수", category_title=None, value_title="공고 수 (건)",
                            horizontal=True, sort_desc=True, integer=True, height=entry_height,
                            wrap_labels=True), key="it_license_chart")
            st.caption("등장 빈도 순입니다. 복수 면허의 필수·대체 관계는 공고 원문에서 확인하세요.")
        else:
            st.markdown("표시할 항목이 없습니다.")
    with entry_cols[1], card("어느 지역 업체만 받나요?", "지역 제한이 있는 공고에서 자주 허용된 지역 (상위 10)"):
        if len(region_tbl):
            display_regions = region_tbl.assign(표시지역=region_tbl["조건"].map(region_display))
            show(bar_figure(display_regions, "표시지역", "공고 수", category_title=None, value_title="공고 수 (건)",
                            horizontal=True, sort_desc=True, integer=True, height=entry_height), key="it_region_chart")
        else:
            st.markdown("표시할 항목이 없습니다.")

with tab_sup:
    st.markdown(f"#### 누가 낙찰받았나요? ({years[0]}~{years[1]}년 합계, 낙찰 건수 상위 15)")
    st.caption("선택한 분류·기간 전체 기준입니다. 기관·낙찰금액 필터는 이 업체 표에 적용되지 않습니다.")
    if len(top_sup):
        reference_table(top_sup.rename(columns={"supplier_name": "업체", "award_count": "낙찰 (건)", "count_share": "낙찰 비중"}),
                        key="it_supplier_table", label="낙찰 업체", compact=True, width_scale=1.4,
                        formats={"낙찰 (건)": "integer", "낙찰 비중": "percent"},
                        widths={"낙찰 (건)": 110, "낙찰 비중": 312}, progress_columns=("낙찰 비중",))
    else:
        st.markdown("표시할 항목이 없습니다.")


def build_pdf() -> bytes:
    rep = Report(f"품목 분석: {cat['display']}", f"{ptype} · {years[0]}~{years[1]}년 · 개찰 {len(ev):,}건",
                 footer="Frontline Data · 국방 조달 탐색")
    rep.kv(kpis)
    rep.para(kpi_basis)

    def draw(ax):
        ax.bar(yearly["year"], yearly["events"], color="#2563EB")
        ax.set_title("해마다 개찰이 몇 번 있었나요?", fontsize=10)
        ax.set_xlabel("연도", fontsize=8)
        ax.set_ylabel("개찰 수 (건)", fontsize=8)

    rep.heading("연도별 개찰").chart(draw)
    t = yearly[["year", "events", "median_bidders", "single_bid_rate", "no_bid_rate", "contract_count"]].copy()
    t["single_bid_rate"] = t["single_bid_rate"].map(pct)
    t["no_bid_rate"] = t["no_bid_rate"].map(pct)
    t.columns = ["연도", "개찰(건)", "참가업체(곳, 중앙값)", "단독입찰", "무응찰", "계약(건)"]
    rep.table(t)
    rep.heading("진입 조건").table(checks[["확인 항목", "관측값", "기준"]])
    if len(licenses):
        rep.heading("자주 요구된 면허").table(licenses)
    if len(top_sup):
        s = top_sup.copy()
        s["count_share"] = s["count_share"].map(pct)
        s.columns = ["업체", "낙찰(건)", "비중"]
        rep.heading(f"낙찰 업체 ({years[0]}~{years[1]}년)")
        rep.para("분류·기간 전체 기준. 기관·낙찰금액 필터 미적용.").table(s)
    return rep.build()


with export_slot:
    pdf_button("PDF", f"품목분석_{safe_name(cat['category_value'])}.pdf", build_pdf, key="it_pdf", type="tertiary", help="PDF 내보내기")
