"""공고 — 첫 화면. 목록은 기본 정보만, '상세보기'를 누르면 공고 상세 창이 열린다.

필터는 사이드바에 있고, 내 회사 조건·마지막 필터·저장한 검색은 브라우저에 저장된다(view/store.py).
거르기·판단은 service/queries.py가 하고, 이 파일은 위젯과 그리기만 한다.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from service import data, queries
from service.eligibility import CHECK, NEED_INPUT, NO, OK, STATUS_OPTIONS
from service.filters import NoticeFilter, Profile
from service.notice_sort import sort_notices
from view import store
from view.calendar import period_calendar
from view.notice_table import notice_table
from view.help import help_icon, help_label
from view.charts import kpi_tiles
from view.fmt import (STATUS_COLORS, num, pct, region_display, notice_status_label, company_empty_hint,
                      notice_requirement_summary, compact_filter_values, notice_identifier, dday_text)
from view.notice_detail import show_detail
from view.pdf import Report
from view.navigation import page_header
from view.widgets import (agency_filter, company_profile, detail_expander, filter_area, pdf_button, safe_name,
                          sidebar_toolbar)

KST = ZoneInfo("Asia/Seoul")
now = datetime.now(KST).replace(tzinfo=None)
today = now.date()

page_header("notices")
export_slot = st.session_state._export_slot


def _scope_changed():
    if st.session_state.nt_scope == store.SCOPE_COMPANY:
        st.session_state.pf_box = True


# ---- 사이드바 필터 (기본값은 한 번만 넣고, 위젯에는 default를 주지 않는다) ----
# Codex, 2026-09-30: 검색·유형 → 상세 조건(공고일 달력·마감 전·기관) → 내 회사 조건.
# 상세·회사 조건은 기본 접힘. 첫 접속은 오늘을 포함한 최근 7일·전체 유형이며 저장값은 복원한다.
NT_DEFAULTS = store.initial_notice_filters(today, data.TYPES)
for k, v in NT_DEFAULTS.items():
    st.session_state.setdefault(k, v)
if st.session_state.nt_scope == "참여 가능 공고":
    st.session_state.nt_scope = store.SCOPE_COMPANY
if st.session_state.nt_scope not in store.SCOPE_OPTIONS:
    st.session_state.nt_scope = store.SCOPE_ALL
if st.session_state.nt_when not in store.WHEN_OPTIONS:
    st.session_state.nt_when = store.WHEN_DEFAULT


def _clear_item_filter():
    st.session_state.nt_item = None


def _saved_searches():
    """저장한 검색: 불러오기·현재 조건 저장·지우기를 팝오버 하나에."""
    saved = store.presets()
    with st.popover("저장한 검색", icon=":material/bookmark:", type="tertiary"):
        if saved:
            st.selectbox("불러오기", [p["name"] for p in saved], index=None, placeholder="선택",
                         key="nt_preset", on_change=lambda: store.apply_preset(st.session_state.nt_preset))
        st.markdown(":gray[검색 조건과 내 회사 조건을 함께 저장합니다.]")
        name = st.text_input("이름", placeholder="예: 대전 전기공사", key="nt_preset_name")
        if st.button("현재 조건 저장", type="primary", disabled=not name.strip(), key="nt_preset_save"):
            store.save_preset(name)
            st.toast(f"'{name.strip()}' 저장했습니다. 다음에 '저장한 검색'에서 불러오세요.")
        if saved:
            victim = st.selectbox("지우기", [p["name"] for p in saved], index=None, key="nt_preset_del")
            if st.button("선택한 검색 지우기", disabled=victim is None, key="nt_preset_delete"):
                store.delete_preset(victim)
                st.rerun()


with filter_area():
    sidebar_toolbar("nt", NT_DEFAULTS, extra=_saved_searches)
    if st.session_state.get("nt_item"):  # 품목 분석의 '진행 중 공고 보기'에서 넘어온 분류 필터
        st.button(f"분류: {data.category_display(st.session_state.nt_item)}  ✕", on_click=_clear_item_filter,
                  icon=":material/filter_alt:", help="누르면 분류 필터를 없앱니다.", key="nt_item_clear")
    help_label("공고명·분류 번호 검색", "공고명 또는 품목 분류 번호(8자리)로 찾습니다.", key="help_nt_kw")
    st.text_input("공고명·분류 번호 검색", placeholder="예: 전투복, 72154090", key="nt_kw", persist_state="session",
                  label_visibility="collapsed")
    st.pills("조달 유형", data.TYPES, selection_mode="multi", key="nt_types", persist_state="session")
    st.caption("유형 1개 이상 선택 · 모두 해제 시 검색 안 함")
    active_detail = int(bool(st.session_state.get(f"nt_agency_{st.session_state.nt_agency_role}")))
    with detail_expander("nt", active_detail):
        dates = period_calendar("공고 기간 (공고일 기준)", key="nt_dates", today=today,
                                minimum=datetime(2020, 1, 1).date(), maximum=today + timedelta(days=365))
        open_only = st.toggle("마감 전 공고만", key="nt_open_only", persist_state="session")
        agency_role, agencies = agency_filter("nt", queries.notice_agency_options(),
                                              labels_by_role=queries.agency_option_labels())
    if st.session_state.nt_scope == store.SCOPE_COMPANY:
        st.caption("내 회사 조건으로 공고의 소재지·면허 조건을 비교합니다.")
        my_region, my_licenses = company_profile(data.provinces(), data.license_names())
    else:
        saved_region = st.session_state.get("pf_region") or []
        my_region = [saved_region] if isinstance(saved_region, str) else saved_region
        my_licenses = st.session_state.get("pf_licenses") or []
nt_status, nt_deadline = ("마감 전" if open_only else "전체"), "전체"

# ---- 사용자가 조달 유형을 모두 해제했을 때만 안내(팝업 없이) ----
if not st.session_state.nt_types:
    with st.container(border=True, key="card_need_types"):
        st.markdown("#### 조달 유형을 1개 이상 골라 주세요")
        st.markdown("왼쪽 **조달 유형**에서 물품·용역·공사·외자 중 고르면 공고가 나옵니다.")
    st.stop()

# ---- 거르기(service) ----
kw = st.session_state.nt_kw.strip()
profile = Profile(tuple(my_region), tuple(my_licenses))
f = queries.find_notices(NoticeFilter(
    types=tuple(st.session_state.nt_types), item=st.session_state.get("nt_item"), keyword=kw,
    status=nt_status, deadline=nt_deadline, agency_role=agency_role,
    agencies=tuple(agencies), date_from=dates[0] if dates else None,
    date_to=dates[-1] if dates else None), profile, now)
summary = queries.notice_summary(f)          # 요약 숫자는 참여 판단 전체 기준
found_n = len(f)
if st.session_state.nt_scope != store.SCOPE_ALL:   # 목록만 '참여 가능'으로 좁힌다(사용자 지시 2026-09-29)
    f = queries.only_status(f, [OK])
    if not my_region and not my_licenses:
        f = f.iloc[0:0]


# ---- 요약 (색 타일 5개, 같은 높이) ----
counts = summary["counts"]
# 현재 실제 적용 조건을 요약한다. 오늘 기준 최근 7일 기본값도 달력 범위와 동일하다.
conditions = ["유형: " + compact_filter_values(st.session_state.nt_types, separator="·")]
conditions.append("공고일: " + (f"{dates[0]:%Y.%m.%d}~{dates[-1]:%Y.%m.%d}" if dates else "전체 기간"))
conditions.append("마감 전만" if open_only else "마감 여부 전체")
if kw:
    conditions.append(f"검색어: {kw}")
if st.session_state.get("nt_item"):
    conditions.append("분류: " + data.category_display(st.session_state.nt_item))
if agencies:
    conditions.append(f"{agency_role}: " + compact_filter_values(agencies))
conditions.append("목록: " + st.session_state.nt_scope)
if st.session_state.nt_scope == store.SCOPE_COMPANY:
    conditions.append("회사 소재지: " + compact_filter_values(map(region_display, my_region)))
    conditions.append("보유 면허: " + compact_filter_values(my_licenses))
with st.container(border=True, gap="xsmall", key="notice_filter_summary"):
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="notice_summary_heading"):
        with st.container(width=48, key="notice_summary_icon"):
            st.markdown(":blue[:material/manage_search:]")
        with st.container(width="stretch", gap="xxsmall", key="notice_summary_text"):
            st.markdown("**현재 검색 조건**")
            st.caption("  |  ".join(conditions))
        with st.container(width=28, key="notice_summary_basis"):
            help_icon("상단 지표 집계 기준", "상단 지표는 검색 결과 전체 기준입니다.\n‘내 회사 조건에 맞는 공고’는 아래 목록만 좁힙니다.",
                      key="help_notice_summary_basis", symbol="i")
urgent_n = summary["urgent"]
company_instruction = None
if st.session_state.nt_scope == store.SCOPE_ALL:
    company_instruction = "‘내 회사 조건에 맞는 공고’를 선택한 뒤 사이드바에 소재지·면허를 입력하세요."
elif not my_region and not my_licenses:
    company_instruction = "사이드바의 ‘내 회사 조건’에 소재지·면허를 입력하세요."
kpi_tiles([
    {"label": "찾은 공고", "value": f"{found_n:,}건", "color": "blue"},
    {"label": "마감 7일 안", "value": f"{urgent_n:,}건", "color": "blue"},
    {"label": "회사 조건 충족", "value": f"{counts.get(OK, 0) if my_region or my_licenses else 0:,}건", "color": "green",
     "instruction": company_instruction,
     "help": "입력한 소재지·면허와 공개된 조건을 비교한 결과입니다. 최종 참가 자격은 공고 원문을 확인하세요."},
    {"label": "원문 확인 필요", "value": f"{counts.get(CHECK, 0):,}건", "color": "orange"},
], prefix="nt")
# 보조 지표(참여 불가·조건 미입력)는 작게 한 줄로(디자인 검토 2026-09-28)
st.caption(f":red[{NO}] {counts.get(NO, 0):,}건 · {NEED_INPUT} {counts.get(NEED_INPUT, 0):,}건")

# ---- 목록 (기본 정보만) ----
if st.session_state.nt_scope == store.SCOPE_ALL and (st.session_state.get("nt_sort") or {}).get("label") == "참여 판단":
    # 숨겨진 열로 목록이 정렬되어 보이지 않도록 해당 정렬만 기본값으로 복원한다.
    st.session_state.nt_sort = {"label": None, "direction": 0}
f = sort_notices(f, st.session_state.get("nt_sort"))
show_requirements = not (my_region or my_licenses)
table = pd.DataFrame({
    "마감": f["dday"].map(dday_text),
    "공고명": f["notice_name"],
    "수요기관": f["demand_agency_name"],
    "유형": f["procurement_type"],
    "참여": f["status"].map(lambda s: [notice_status_label(s)]),
    "상세": ":material/open_in_new:",
})
if show_requirements:
    table["면허·지역 요건"] = f.apply(
        lambda r: notice_requirement_summary(r.get("license_state"), r.get("license_values"),
                                             r.get("region_state"), r.get("region_values")).replace(" | ", "\n"), axis=1)
    table = table[["마감", "공고명", "수요기관", "유형", "면허·지역 요건", "참여", "상세"]]

# 표 안 스크롤을 없애려고 20건씩 페이지로 나눈다(표 높이 = 내용 높이).
PAGE_SIZE = 20
pages_total = max(1, -(-len(table) // PAGE_SIZE))
if st.session_state.get("nt_page", 1) > pages_total:
    st.session_state.nt_page = 1
page_no = st.session_state.get("nt_page", 1)
start = (page_no - 1) * PAGE_SIZE
table = table.iloc[start:start + PAGE_SIZE]
st.session_state._nt_ids = f["notice_id"].iloc[start:start + PAGE_SIZE].tolist()


table["공고번호·차수"] = f.iloc[start:start + PAGE_SIZE].apply(notice_identifier, axis=1)
table = table[["마감", "유형"] + [column for column in table.columns if column not in ("마감", "유형", "상세")] + ["상세"]]
if st.session_state.nt_scope == store.SCOPE_ALL:
    table = table.drop(columns="참여")
results_panel = st.container(border=True, gap="small", key="notice_results_panel")
with results_panel, st.container(horizontal=True, vertical_alignment="center", key="notice_results_heading"):
    st.markdown(f"**:blue[:material/list_alt:] {st.session_state.nt_scope}**", width="stretch")
    st.badge(f"총 {len(f):,}건", color="gray")
with results_panel, st.container(horizontal=True, vertical_alignment="center"):
    st.segmented_control("목록", store.SCOPE_OPTIONS, required=True, key="nt_scope", persist_state="session",
                         label_visibility="collapsed", on_change=_scope_changed)
    with st.container(horizontal=True, horizontal_alignment="right", width="stretch", key="nt_view_controls"):
        st.segmented_control("보기", ["표", "카드"], required=True, key="nt_view", persist_state="session",
                             default="표", label_visibility="collapsed",
                             help="휴대폰처럼 좁은 화면에서는 '카드'가 보기 편합니다.")
with results_panel:
    if show_requirements:
        st.caption("요건 미확인은 제한 없음이 아닙니다. 확인된 내용도 최종 참가 자격은 공고 원문으로 확인하세요.")
    st.caption("☆를 눌러 공고를 즐겨찾기에 저장하세요. 최대 10개를 저장하고, 즐겨찾기에서 최대 4개를 비교할 수 있습니다.")
if f.empty and st.session_state.nt_scope != store.SCOPE_ALL:
    with results_panel, st.container(key="notice_empty_state"):
        st.info("선택한 조건에 해당하는 공고가 없습니다.", icon=":material/filter_alt_off:")
        if my_region or my_licenses:
            st.caption(company_empty_hint(True))
elif st.session_state.nt_scope == store.SCOPE_COMPANY:
    with results_panel:
        st.caption("입력한 소재지·면허 기준으로 조건을 충족한 공고입니다. 최종 참가 자격은 공고 원문에서 확인하세요.")
elif f.empty:
    with results_panel, st.container(key="notice_empty_state"):
        st.info("선택한 조건에 해당하는 공고가 없습니다.", icon=":material/filter_alt_off:")
if st.session_state.get("nt_view", "표") == "표":
    with results_panel:
        with st.container(key="table_scroll_hint"):
            st.caption(":material/swipe: 표를 좌우로 이동하면 나머지 열을 볼 수 있습니다. 좁은 화면은 ‘카드’ 보기를 권장합니다.")
        notice_table(table, st.session_state._nt_ids)
else:  # 카드형 목록(좁은 화면용, 디자인 검토 2026-09-28) — 공고 하나가 카드 하나
    colors = dict(zip(STATUS_OPTIONS, STATUS_COLORS))
    page_rows = f.iloc[start:start + PAGE_SIZE]
    for _, r in page_rows.iterrows():
        d = r["dday"]
        with results_panel, st.container(border=True, key=f"card_nt_{r['notice_id']}"):
            st.markdown(f":{'orange' if pd.notna(d) and 0 <= d <= 7 else 'gray'}-badge[{dday_text(d)}] "
                        f":{colors.get(r['status'], 'gray')}-badge[{notice_status_label(r['status'])}]")
            st.markdown(f"**{r['notice_name']}**")
            st.caption(f"공고번호·차수: {notice_identifier(r)}")
            st.markdown(f"{r['demand_agency_name']} · {r['procurement_type']} · 마감 "
                        f"{r['bid_close_date']:%Y-%m-%d %H:%M}" if pd.notna(r["bid_close_date"]) else r["demand_agency_name"])
            if show_requirements:
                st.caption(notice_requirement_summary(r.get("license_state"), r.get("license_values"),
                                                      r.get("region_state"), r.get("region_values")).replace(" | ", "  \n"))
            with st.container(horizontal=True, gap="small", wrap=True, key=f"nt_card_actions_{r['notice_id']}"):
                if st.button("상세보기", icon=":material/open_in_new:", key=f"nt_card_btn_{r['notice_id']}"):
                    st.session_state.open_notice = r["notice_id"]
                st.button("즐겨찾기 해제" if r["notice_id"] in store.favorites() else "즐겨찾기 추가",
                          icon=":material/star:" if r["notice_id"] in store.favorites() else ":material/star_border:",
                          key=f"nt_star_{r['notice_id']}", on_click=store.toggle_favorite, args=(r["notice_id"],))
sort_state = st.session_state.get("nt_sort", {})
sort_note = (str(sort_state["label"]) + (" 오름차순" if sort_state["direction"] == 1 else " 내림차순")
             if sort_state.get("direction") else ("마감이 가까운 순" if nt_status == "마감 전" else "최근 공고 순"))
with results_panel, st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="right", key="nt_paging"):
    st.caption(f"전체 {len(f):,}건 중 {start + 1 if len(f) else 0:,}~{min(start + PAGE_SIZE, len(f)):,}번째 · "
               f"{sort_note}",
               width="content", text_alignment="right")
    if pages_total > 1:
        st.pagination(pages_total, key="nt_page", max_visible_pages=5)

if st.session_state.get("open_notice"):
    detail = queries.notice_detail(st.session_state.pop("open_notice"), profile)
    if detail is not None:
        show_detail(detail, today, dict(zip(STATUS_OPTIONS, STATUS_COLORS)).get(detail["status"], "gray"))

# ---- 내보내기 ----
conditions_text = [f"공고일 {dates[0]}~{dates[-1]}" if dates else "공고일 전체", f"유형 {', '.join(st.session_state.nt_types or data.TYPES)}"]
if kw:
    conditions_text.append(f"검색어 '{kw}'")
if my_region:
    conditions_text.append(f"소재지 {', '.join(my_region)}")
export = f[["procurement_type", "notice_name", "notice_date", "bid_close_date", "demand_agency_name",
            "category_value", "status", "license_values", "region_values", "notice_url"]].copy()
export["status"] = export["status"].map(notice_status_label)


def build_list_pdf() -> bytes:
    rep = Report("국방 공고 검색 결과", " · ".join(conditions_text) + f" · 기준 {now:%Y-%m-%d %H:%M}",
                 footer="Frontline Data · 국방 조달 탐색")
    rep.kv([("찾은 공고", f"{found_n:,}건"), (OK, f"{counts.get(OK, 0):,}건"), (NO, f"{counts.get(NO, 0):,}건")])
    rep.para("상단 지표는 검색 결과 전체 기준이며, 회사 조건 선택은 공고 목록만 좁힙니다.")
    t = pd.DataFrame({"마감": f["dday"].map(dday_text), "공고명": f["notice_name"], "수요기관": f["demand_agency_name"],
                      "참여 판단": f["status"].map(notice_status_label)}).head(200)
    rep.table(t, max_rows=200)
    return rep.build()


if export.empty:
    st.stop()
with export_slot:
    st.download_button("CSV", export.to_csv(index=False).encode("utf-8-sig"), "국방공고_검색결과.csv",
                       mime="text/csv", icon=":material/download:", on_click="ignore", type="tertiary", help="CSV 내보내기")
    pdf_button("PDF", "국방공고_검색결과.pdf", build_list_pdf, key="nt_pdf", help="PDF 내보내기 · 최대 200건", type="tertiary")
