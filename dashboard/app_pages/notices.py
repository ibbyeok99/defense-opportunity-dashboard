"""공고 — 첫 화면. 목록은 기본 정보만, '상세보기'를 누르면 공고 상세 창이 열린다.

필터는 사이드바에 있고, 내 회사 조건·마지막 필터·저장한 검색은 브라우저에 저장된다(view/store.py).
거르기·판단은 service/queries.py가 하고, 이 파일은 위젯과 그리기만 한다.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from service import data, queries
from service.eligibility import OK, STATUS_OPTIONS, usable_values
from service.filters import NoticeFilter, Profile
from service.notice_sort import sort_notices
from service.notice_list_refresh import refresh_deadline
from service.notice_list_cache import NoticeListCache, source_version
from view import store
from view.calendar import period_calendar
from view.notice_table import notice_table
from view.help import help_icon, help_label
from view.charts import kpi_tiles
from view.fmt import (STATUS_COLORS, registered_requirement_summary,
                      compact_filter_values, notice_identifier, dday_text, deadline_tone)
from view.notice_detail import show_detail
from service.notice_requirements import fetch_evidence
from view.pdf import Report
from view.navigation import page_header
from view.loading import read
from view.widgets import (agency_filter, company_profile, detail_expander, filter_area, pdf_button, safe_name,
                          sidebar_toolbar)

KST = ZoneInfo("Asia/Seoul")
now = datetime.now(KST).replace(tzinfo=None)
today = now.date()

page_header("notices")
export_slot = st.session_state._export_slot


# ---- 사이드바 필터 (기본값은 한 번만 넣고, 위젯에는 default를 주지 않는다) ----
# Codex, 2026-09-30: 검색·유형 → 상세 조건(공고일 달력·마감 전·기관) → 내 회사 조건.
# 상세·회사 조건은 기본 접힘. 첫 접속은 오늘을 포함한 최근 7일·전체 유형이며 저장값은 복원한다.
NT_DEFAULTS = store.initial_notice_filters(today, data.TYPES)
for k, v in NT_DEFAULTS.items():
    st.session_state.setdefault(k, v)
st.session_state.nt_scope = store.SCOPE_ALL
if st.session_state.nt_when not in store.WHEN_OPTIONS:
    st.session_state.nt_when = store.WHEN_DEFAULT


def _clear_item_filter():
    st.session_state.nt_item = None


def _save_search():
    # 폼 제출 시 이름과 현재 조건을 함께 받는다. 입력 중인 값으로 버튼을 비활성화하지 않는다.
    name = str(st.session_state.get("nt_preset_name") or "").strip()
    if not name:
        st.session_state.nt_preset_feedback = ("warning", "검색 조건 이름을 입력하세요.")
        return
    store.save_preset(name)
    st.session_state.nt_preset_feedback = ("success", f"'{name}' 저장했습니다.")


def _delete_search():
    victim = st.session_state.get("nt_preset_del")
    if victim not in {p["name"] for p in store.presets()}:
        st.session_state.nt_preset_feedback = ("warning", "지울 검색 조건을 선택하세요.")
        return
    store.delete_preset(victim)
    if st.session_state.get("nt_preset") == victim:
        st.session_state.nt_preset = None
    st.session_state.nt_preset_del = None
    st.session_state.nt_preset_feedback = ("success", f"'{victim}' 삭제했습니다.")


def _saved_searches():
    """저장한 검색: 불러오기·현재 조건 저장·지우기를 팝오버 하나에."""
    saved = store.presets()
    with st.popover("저장한 검색", icon=":material/bookmark:", type="tertiary"):
        if saved:
            st.selectbox("불러오기", [p["name"] for p in saved], index=None, placeholder="선택",
                         key="nt_preset", on_change=lambda: store.apply_preset(st.session_state.nt_preset))
        st.markdown(":gray[검색 조건과 내 회사 조건을 함께 저장합니다.]")
        with st.form("nt_preset_save_form", border=False):
            st.text_input("이름", placeholder="예: 대전 전기공사", key="nt_preset_name")
            st.form_submit_button("현재 조건 저장", type="primary", key="nt_preset_save", on_click=_save_search)
        if saved:
            st.selectbox("지우기", [p["name"] for p in saved], index=None, key="nt_preset_del")
            can_delete = st.session_state.get("nt_preset_del") in {p["name"] for p in saved}
            st.button("선택한 검색 지우기", key="nt_preset_delete", on_click=_delete_search,
                      disabled=not can_delete, type="primary" if can_delete else "secondary")
        feedback = st.session_state.get("nt_preset_feedback")
        if feedback:
            getattr(st, feedback[0])(feedback[1])


with filter_area():
    sidebar_toolbar("nt", NT_DEFAULTS, extra=_saved_searches)
    if st.session_state.get("nt_item"):  # 품목 분석의 '진행 중 공고 보기'에서 넘어온 분류 필터
        st.button(f"분류: {data.category_display(st.session_state.nt_item)}  ✕", on_click=_clear_item_filter,
                  icon=":material/filter_alt:", help="누르면 분류 필터를 없앱니다.", key="nt_item_clear")
    help_label("공고명·분류·요건 검색", "공고명·분류 번호와 확인된 면허·지역 조건으로 검색합니다. 공고문·첨부 내용은 상세 페이지 또는 즐겨찾기에서 확인할 수 있습니다.", key="help_nt_kw")
    st.text_input("공고명·분류·요건 검색", placeholder="예: 전투복, 72154090, 충청북도", key="nt_kw", persist_state="session",
                  label_visibility="collapsed")
    st.pills("조달 유형", data.TYPES, selection_mode="multi", key="nt_types", persist_state="session")
    active_detail = int(bool(st.session_state.get(f"nt_agency_{st.session_state.nt_agency_role}")))
    with detail_expander("nt", active_detail):
        dates = period_calendar("공고 기간 (공고일 기준)", key="nt_dates", today=today,
                                minimum=datetime(2020, 1, 1).date(), maximum=today + timedelta(days=365))
        open_only = st.toggle("마감 전 공고만", key="nt_open_only", persist_state="session")
        agency_role, agencies = agency_filter("nt", queries.notice_agency_options(),
                                              labels_by_role=queries.agency_option_labels())
    my_region, my_licenses = company_profile(data.provinces(), data.license_names())
nt_status, nt_deadline = ("마감 전" if open_only else "전체"), "전체"

# ---- 사용자가 조달 유형을 모두 해제했을 때만 안내(팝업 없이) ----
if not st.session_state.nt_types:
    with export_slot:
        st.download_button("CSV", b"", "국방공고_검색결과.csv", mime="text/csv",
                           icon=":material/download:", disabled=True, type="tertiary",
                           help="조달 유형을 선택하면 다운로드할 수 있습니다.")
        st.download_button("PDF", b"", "국방공고_검색결과.pdf", mime="application/pdf",
                           icon=":material/picture_as_pdf:", disabled=True, type="tertiary",
                           help="조달 유형을 선택하면 다운로드할 수 있습니다.")
    with st.container(border=True, key="card_need_types"):
        st.markdown("#### 조달 유형을 1개 이상 골라 주세요")
        st.markdown("왼쪽 **조달 유형**에서 물품·용역·공사·외자 중 선택하면 공고를 검색할 수 있습니다.")
    st.stop()

# ---- 거르기(service) ----
kw = st.session_state.nt_kw.strip()
profile = Profile(tuple(my_region), tuple(my_licenses))
notice_filter = NoticeFilter(
    types=tuple(st.session_state.nt_types), item=st.session_state.get("nt_item"), keyword=kw,
    status=nt_status, deadline=nt_deadline, agency_role=agency_role,
    agencies=tuple(agencies), date_from=dates[0] if dates else None,
    date_to=dates[-1] if dates else None)


# ---- 요약 (4개 슬롯, 같은 높이; 우측 슬롯은 내용 없이 보존) ----
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
with st.container(border=True, gap="xsmall", key="notice_filter_summary"):
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="notice_summary_heading"):
        with st.container(width=48, key="notice_summary_icon"):
            st.markdown(":blue[:material/manage_search:]")
        with st.container(width="stretch", gap="xxsmall", key="notice_summary_text"):
            st.markdown("**현재 검색 조건**")
            st.caption("  |  ".join(conditions))
        with st.container(width=28, key="notice_summary_basis"):
            help_icon("상단 지표 집계 기준", "상단 지표는 검색 결과 전체 기준입니다. 회사 입력은 목록을 줄이지 않으며 진행 중인 조건 일치 공고를 먼저 보여줍니다.",
                      key="help_notice_summary_basis", symbol="i")
if '_notice_list_cache' not in st.session_state:
    st.session_state._notice_list_cache = NoticeListCache()
f, list_loaded_at = st.session_state._notice_list_cache.read(
    (notice_filter, profile, source_version()), now,
    lambda: read('공고 목록을 불러오는 중…', queries.find_notices, notice_filter, profile, now, stored_only=True))
summary = queries.notice_summary(f)
found_n, counts, urgent_n = len(f), summary['counts'], summary['urgent']
new_today_n = int((pd.to_datetime(f["notice_date"]).dt.date == today).sum()) if len(f) else 0
company_instruction = None if my_region or my_licenses else "사이드바의 ‘내 회사 조건’을 입력하면 일치 공고를 먼저 보여줍니다."
kpi_tiles([
    {"label": "찾은 공고", "value": f"{found_n:,}건", "color": "blue"},
    {"label": "마감 7일 안", "value": f"{urgent_n:,}건", "color": "blue"},
    {"label": "회사 조건 일치", "value": f"{int(f['company_match'].sum()):,}건", "color": "green",
     "instruction": company_instruction,
     "help": "진행 중인 공고 중 입력한 소재지·면허가 확인된 등록 요건에 맞는 건수입니다. 미확인 항목은 일치로 세지 않습니다. 최종 참가 자격은 원문 기준입니다."},
    {"label": "오늘 올라온 신규 공고", "value": f"{new_today_n:,}건", "color": "orange",
     "help": "검색 결과 중 공고일이 오늘인 공고 수입니다. 수집 시점에 따라 오늘 게시된 공고가 아직 반영되지 않았을 수 있습니다."},
], prefix="nt")

# ---- 목록 (기본 정보만) ----
if (st.session_state.get("nt_sort") or {}).get("label") == "참여 판단":
    # 숨겨진 열로 목록이 정렬되어 보이지 않도록 해당 정렬만 기본값으로 복원한다.
    st.session_state.nt_sort = {"label": None, "direction": 0}
f = sort_notices(f, st.session_state.get("nt_sort"))
# 페이지 이동·표/카드 전환은 목록 영역만 실행한다. 검색·회사 조건은 전체 실행으로 갱신한다.
@st.fragment
def render_notice_list(f, profile, today, valid_until, initial_sort, initial_source_version):
    if datetime.now(KST).replace(tzinfo=None) >= valid_until or source_version() != initial_source_version:
        st.rerun()
    # 정렬을 바꾸면 내보내기와 목록의 순서도 함께 갱신한다.
    if (st.session_state.get("nt_sort") or {}) != initial_sort:
        st.rerun()
    my_region, my_licenses = profile.region, profile.licenses
    show_requirements = True
    # 표 안 스크롤을 없애려고 20건씩 페이지로 나눈다(표 높이 = 내용 높이).
    PAGE_SIZE = 20
    pages_total = max(1, -(-len(f) // PAGE_SIZE))
    if st.session_state.get("nt_page", 1) > pages_total:
        st.session_state.nt_page = 1
    page_no = st.session_state.get("nt_page", 1)
    start = (page_no - 1) * PAGE_SIZE
    page_rows = f.iloc[start:start + PAGE_SIZE]
    table = pd.DataFrame({
        "마감": page_rows["dday"].map(dday_text),
        "공고명": page_rows["notice_name"],
        "수요기관": page_rows["demand_agency_name"],
        "유형": page_rows["procurement_type"],
        "상세": ":material/open_in_new:",
    })
    if show_requirements:
        table_requirements = page_rows.apply(
            lambda r: registered_requirement_summary(r.get("license_state"), r.get("license_values"),
                                                 r.get("region_state"), r.get("region_values"),
                                                 license_requires_review=r.get("license_requires_review", False),
                                                 region_requires_review=r.get("region_requires_review", False),
                                                 license_review_status=r.get('license_review_status', ''),
                                                 region_review_status=r.get('region_review_status', '')).replace(" | ", "\n"), axis=1) if len(page_rows) else pd.Series(index=page_rows.index, dtype=object)
        table["면허·지역 요건"] = table_requirements
        table["_company_match"] = page_rows["company_match"]
        table = table[["마감", "공고명", "수요기관", "유형", "면허·지역 요건", "_company_match", "상세"]]

    st.session_state._nt_ids = f["notice_id"].iloc[start:start + PAGE_SIZE].tolist()
    store.remember_sources(f.iloc[start:start + PAGE_SIZE])


    table["공고번호·차수"] = page_rows.apply(notice_identifier, axis=1) if len(page_rows) else pd.Series(index=page_rows.index, dtype=object)
    table = table[["마감", "유형"] + [column for column in table.columns if column not in ("마감", "유형", "상세")] + ["상세"]]
    results_panel = st.container(border=True, gap="small", key="notice_results_panel")
    with results_panel, st.container(horizontal=True, vertical_alignment="center", key="notice_results_heading"):
        st.markdown(f"**:blue[:material/list_alt:] {st.session_state.nt_scope}**", width="stretch")
        st.badge(f"총 {len(f):,}건", color="gray")
    # 안내 문장은 표|카드 선택과 같은 줄 왼쪽에 둔다(별도 줄이면 ‘모든 공고’ 아래 공백이 커진다). 표|카드의 모양·위치는 그대로다.
    with results_panel, st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", key="nt_view_row"):
        if show_requirements:
            st.caption("회사 조건에 맞는 진행 중 공고를 먼저 보여주고 나머지는 마감이 가까운 순으로 표시합니다. 저장된 면허·지역 요건을 비교합니다. 그 밖의 참가조건은 공고 원문에서 확인해 주세요.", width="stretch")
        with st.container(horizontal=True, horizontal_alignment="right", width="content", key="nt_view_controls"):
            st.segmented_control("보기", ["표", "카드"], required=True, key="nt_view", persist_state="session",
                                 default="표", label_visibility="collapsed",
                                 help="휴대폰처럼 좁은 화면에서는 ‘카드’ 보기를 권장합니다.")
    if f.empty:
        with results_panel, st.container(key="notice_empty_state"):
            st.info("선택한 조건에 해당하는 공고가 없습니다.", icon=":material/filter_alt_off:")
    if st.session_state.get("nt_view", "표") == "표":
        with results_panel:
            with st.container(key="table_scroll_hint"):
                st.caption(":material/swipe: 표를 좌우로 이동하면 나머지 열을 볼 수 있습니다. 좁은 화면은 ‘카드’ 보기를 권장합니다.")
            notice_table(table, st.session_state._nt_ids)
    else:  # 카드형 목록(좁은 화면용, 디자인 검토 2026-09-28) — 공고 하나가 카드 하나
        page_rows = f.iloc[start:start + PAGE_SIZE]
        for _, r in page_rows.iterrows():
            d = r["dday"]
            # 내용은 그대로 두고 배치만 정리: 머리 한 줄(마감·제목·일치 표시·버튼) + 아래 두 칸(공고 정보 / 면허·지역 요건).
            with results_panel, st.container(border=True, gap="xsmall", key=f"card_nt_{r['notice_id']}"):
                with st.container(horizontal=True, vertical_alignment="center", gap="small", wrap=True,
                                  key=f"nt_card_head_{r['notice_id']}"):
                    st.markdown(f":{deadline_tone(d)}-badge[{dday_text(d)}]", width="content")  # 표·상세와 같은 기준: 7일 이내 빨강, 그 외 파랑, 마감/미정 회색
                    st.markdown(f"**{r['notice_name']}**", width="stretch")
                    if show_requirements and r['company_match']:
                        st.badge('조건에 맞는 공고', color='green')
                    with st.container(horizontal=True, gap="small", wrap=True, width="content",
                                      key=f"nt_card_actions_{r['notice_id']}"):
                        if st.button("상세보기", icon=":material/open_in_new:", key=f"nt_card_btn_{r['notice_id']}"):
                            st.session_state.open_notice = r["notice_id"]
                        st.button("즐겨찾기 해제" if r["notice_id"] in store.favorites() else "즐겨찾기 추가",
                                  icon=":material/star:" if r["notice_id"] in store.favorites() else ":material/star_border:",
                                  key=f"nt_star_{r['notice_id']}", on_click=store.toggle_favorite, args=(r["notice_id"],))
                info_col, requirement_col = st.columns([5, 4], gap="small")
                with info_col, st.container(gap="xxsmall", key=f"nt_card_info_{r['notice_id']}"):
                    st.markdown(f"{r['demand_agency_name']} · {r['procurement_type']} · 마감 "
                                f"{r['bid_close_date']:%Y-%m-%d %H:%M}" if pd.notna(r["bid_close_date"]) else r["demand_agency_name"])
                    st.caption(f"공고번호·차수: {notice_identifier(r)}")
                if show_requirements:
                    requirement_text = registered_requirement_summary(
                        r.get("license_state"), r.get("license_values"), r.get("region_state"), r.get("region_values"),
                        license_requires_review=r.get("license_requires_review", False),
                        region_requires_review=r.get("region_requires_review", False),
                        license_review_status=r.get('license_review_status', ''),
                        region_review_status=r.get('region_review_status', ''))
                    if requirement_text:
                        with requirement_col, st.container(key=f"nt_card_req_{r['notice_id']}"):
                            st.caption(requirement_text.replace(" | ", "  \n"))
    sort_state = st.session_state.get("nt_sort", {})
    sort_note = (str(sort_state["label"]) + (" 오름차순" if sort_state["direction"] == 1 else " 내림차순")
                 if sort_state.get("direction") else "마감이 가까운 순")
    if my_region or my_licenses:
        sort_note = "회사 조건 일치 우선 · " + sort_note
    with results_panel, st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="right", key="nt_paging"):
        st.caption(f"전체 {len(f):,}건 중 {start + 1 if len(f) else 0:,}~{min(start + PAGE_SIZE, len(f)):,}번째 · "
                   f"{sort_note}",
                   width="content", text_alignment="right")
        if pages_total > 1:
            st.pagination(pages_total, key="nt_page", max_visible_pages=5)

    if st.session_state.get("open_notice"):
        detail_id = st.session_state.pop("open_notice")
        selected_rows = f[f.notice_id.eq(detail_id)]
        detail = queries.notice_detail(detail_id, profile, notice=selected_rows.iloc[0] if len(selected_rows) else None,
                                       include_competition=False)
        if detail is not None:
            from service.notice_requirements import poll_detail_evidence
            show_detail(detail, today, dict(zip(STATUS_OPTIONS, STATUS_COLORS)).get(detail["status"], "gray"),
                        evidence_checker=fetch_evidence,
                        evidence_reader=poll_detail_evidence,
                        detail_updater=lambda value, result: queries.update_detail_evidence(value, profile, result),
                        competition_loader=queries.notice_competition,
                        on_evidence_updated=lambda: st.session_state.update(open_notice=detail["notice"]["notice_id"]))


render_notice_list(f, profile, today, refresh_deadline(f, list_loaded_at),
                   dict(st.session_state.get("nt_sort") or {}), st.session_state._notice_list_cache.key[-1])

# ---- 내보내기 ----
conditions_text = [f"공고일 {dates[0]}~{dates[-1]}" if dates else "공고일 전체", f"유형 {', '.join(st.session_state.nt_types or data.TYPES)}"]
if kw:
    conditions_text.append(f"검색어 '{kw}'")
export = f[["procurement_type", "notice_name", "notice_date", "bid_close_date", "demand_agency_name",
            "category_value", "license_values", "region_values", "notice_url"]].copy()
# 목록과 동일하게 미확인/문서 검토 값은 CSV에도 노출하지 않는다. 원본 행은 보존한다.
for kind in ('license', 'region'):
    available = f[kind + '_state'].isin(['제한있음', '조건없음'])
    if kind + '_requires_review' in f:
        available &= ~f[kind + '_requires_review'].fillna(True).astype(bool)
    export.loc[~available, kind + '_values'] = ''
    export[kind + '_values'] = export[kind + '_values'].map(lambda value: ' | '.join(usable_values(value)))


def build_list_pdf() -> bytes:
    rep = Report("국방 공고 검색 결과", " · ".join(conditions_text) + f" · 기준 {now:%Y-%m-%d %H:%M}",
                 footer="Frontline Data · 국방 조달 탐색")
    rep.kv([("찾은 공고", f"{found_n:,}건"), ("마감 7일 안", f"{urgent_n:,}건")])
    rep.para("회사 조건에 맞는 진행 중 공고를 먼저 표시합니다. 일치 표시는 등록된 면허·지역과 입력한 항목의 비교이며 최종 참가 자격은 원문 기준입니다.")
    t = pd.DataFrame({"마감": f["dday"].map(dday_text), "공고명": f["notice_name"], "수요기관": f["demand_agency_name"],
                      "면허·지역 요건": f.head(200).apply(
                          lambda r: registered_requirement_summary(r.get("license_state"), r.get("license_values"),
                              r.get("region_state"), r.get("region_values"),
                              license_requires_review=r.get("license_requires_review", False),
                              region_requires_review=r.get("region_requires_review", False),
                              license_review_status=r.get("license_review_status", ""),
                              region_review_status=r.get("region_review_status", "")).replace(" | ", "\n"), axis=1)}).head(200)
    rep.table(t, max_rows=200)
    return rep.build()


with export_slot:
    from view.notice_export import notice_csv
    st.download_button("CSV", notice_csv(export), "국방공고_검색결과.csv",
                       mime="text/csv", icon=":material/download:", on_click="ignore", type="tertiary",
                       disabled=export.empty, help="검색 결과가 없어 다운로드할 수 없습니다." if export.empty else "CSV 내보내기")
    pdf_button("PDF", "국방공고_검색결과.pdf", build_list_pdf, key="nt_pdf", disabled=export.empty,
               help="검색 결과가 없어 다운로드할 수 없습니다." if export.empty else "PDF 내보내기 · 최대 200건", type="tertiary")
