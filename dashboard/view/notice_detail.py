"""공고 목록·즐겨찾기에서 공유하는 상세 창. 원본 판정과 분류 통계 범위를 보존한다."""

from html import escape
from time import monotonic

import pandas as pd
import streamlit as st
from view import store
from view.detail_design import (SCOPE_NOTE, agency_value, apply_detail_style, basic_row,
                                condition_verdict, display_conditions, judgement_banner,
                                judgement_review_note, requirements_html, section_heading, verdict)
from view.fmt import num, pct, notice_status_label, notice_identifier, dday_text, deadline_tone
from view.pdf import Report
from view.widgets import pdf_button, safe_name
from view.requirement_evidence import evidence_panel
from view.notice_saved_details import saved_details_panel
from view.participation_requirements import participation_panel
from view.loading import read


@st.dialog("공고 상세", width="large", on_dismiss="rerun")
def show_detail(det: dict, today, color: str = "gray", evidence_checker=None, on_evidence_updated=None,
                evidence_reader=None, detail_updater=None, competition_loader=None):
    render = st.fragment(run_every='1s' if evidence_reader else None)(_render_detail)
    render(det, today, color, evidence_checker, on_evidence_updated, evidence_reader, detail_updater, competition_loader)


def _render_detail(det, today, color='gray', evidence_checker=None, on_evidence_updated=None,
                   evidence_reader=None, detail_updater=None, competition_loader=None):
    snapshot = evidence_reader(det['notice']) if evidence_reader else None
    if snapshot and snapshot.get('result') and detail_updater:
        det = detail_updater(det, snapshot['result'])
    n, status = det["notice"], det["status"]
    if n['notice_id'] in store.favorites():
        store.remember_favorite(n)
    if n['notice_id'] not in st.session_state.get('_favorite_available_sources', {}):
        store.remember_sources(pd.DataFrame([n]))
    conditions = display_conditions(det["conditions"])
    if snapshot and snapshot['phase'] == 'running':
        for index, kind in enumerate(('license', 'region')):
            if n[kind + '_state'] == '미확인' or n.get(kind + '_requires_review', False):
                conditions.at[index, '요구 조건'] = '찾는 중… · ' + str(conditions.at[index, '요구 조건'])
    c, days, cat_name = det["competition"], det["contract_days"], det["category"]
    d = (pd.Timestamp(n["bid_close_date"]).normalize() - pd.Timestamp(today)).days if pd.notna(n["bid_close_date"]) else None
    urgent = deadline_tone(d)
    apply_detail_style()
    with st.container(key="notice_detail_surface", gap="medium"):
        st.caption("국방 조달  ›  입찰 공고  ›  공고 상세")
        with st.container(key="notice_detail_header", gap=None):
            with st.container(key="notice_detail_title"):
                st.markdown(f"## {n['notice_name']}")
            with st.container(horizontal=True, vertical_alignment="center", gap="small",
                              key="notice_detail_metadata"):
                st.html(f'<div class="detail-meta"><span class="detail-deadline {urgent}">{escape(dday_text(d))}</span>'
                        f'<span class="detail-verdict {verdict(status)[1]}">{escape(notice_status_label(status))}</span>'
                        f'<span class="detail-meta-text">{escape(str(n["procurement_type"]))} · {escape(str(cat_name))}</span></div>', width="stretch")
                st.button("즐겨찾기 해제" if n["notice_id"] in store.favorites() else "즐겨찾기에 추가",
                          icon=":material/star:" if n["notice_id"] in store.favorites() else ":material/star_border:",
                          type="tertiary", key=f"detail_star_{n['notice_id']}",
                          on_click=store.toggle_favorite, args=(n["notice_id"],))
            st.caption(f"공고번호·차수: {notice_identifier(n)}")

        core, judgement = st.columns([1.15, 1])
        with core.container(border=True, key="detail_core", gap="xsmall", height="stretch"):
            section_heading("공고 핵심 정보", "공고일: 공고가 게시된 날짜\n마감일: 입찰서 제출을 마치는 시각\n"
                            "수요기관: 물품·용역을 실제로 필요로 하는 기관\n공고기관: 공고를 게시하고 입찰을 진행하는 기관\n"
                            "분류: 분석에 사용하는 분류이며 면허 조건과는 다른 정보\n"
                            "계약 방식: 개별 공고의 계약 방식\n계약 기간: 개별 공고의 이행 기간이며 아래 분류별 계약 소요일과는 다른 정보\n"
                            "알 수 없는 값은 추정해 채우지 않습니다. 값이 없으면 원문으로 확인하세요.", key="core")
            for label, value, row_key in [
                ("공고일", n["notice_date"].strftime("%Y-%m-%d") if pd.notna(n["notice_date"]) else "–", "notice_date"),
                ("마감일", n["bid_close_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(n["bid_close_date"]) else "–", "close_date"),
            ]:
                basic_row(label, value, key=row_key, tone=urgent if row_key == 'close_date' else '')
            for label, stem in [("수요기관", "demand"), ("공고기관", "notice")]:
                name, code = agency_value(n, stem)
                basic_row(label, name, key=stem, code=code)
            basic_row("분류", cat_name, key="category")
            basic_row("계약 방식", det.get("saved_details", {}).get("contract_method", n.get("contract_method")), key="method")
            basic_row("계약 기간", n.get("contract_period"), key="period")

        with judgement.container(border=True, key="detail_judgement", gap="xsmall", height="stretch"):
            section_heading("참여 조건 판단", SCOPE_NOTE, key="judgement")
            tone, message = judgement_banner(status, conditions)
            st.html(f'<div class="detail-banner {tone}">{escape(message)}</div>')
            if tone == 'input' and (review_note := judgement_review_note(conditions)):
                st.caption(review_note)
            # 엔진은 면허·지역만 비교한다. 이미지의 다른 자격을 적합으로 꾸미지 않는다.
            for index, row in enumerate(conditions.to_dict("records")):
                label, badge_tone, _ = condition_verdict(row)
                with st.container(horizontal=True, wrap=True, vertical_alignment="center",
                                  horizontal_alignment="distribute", gap="small",
                                  key=f"detail_condition_row_{index}"):
                    st.markdown(f"{row['구분']} 조건", width="content")
                    st.html(f'<span class="detail-verdict {badge_tone}">{escape(label)}</span>',
                            width="content")
        with st.container(border=True, key="detail_requirements", gap="small"):
            section_heading("요구 조건 상세", "공고의 요구 조건과 입력한 회사 조건을 비교합니다. 판단 이유는 판단 옆 ? 아이콘에서 확인합니다. 최종 자격은 공고 원문 기준입니다.", key="requirements")
            st.html(requirements_html(conditions))
            participation_panel(det.get('participation_requirements', []))

        evidence_panel(n, evidence_checker, on_updated=on_evidence_updated, async_status=snapshot,
                       retry=(lambda: evidence_reader(n, force=True)) if evidence_reader else None)

        saved_details_panel(det.get("saved_details", {}))

        with st.container(border=True, key="detail_competition", gap="small"):
            section_heading("분류 기준의 과거 경쟁", "개별 공고의 경쟁 예측이 아닙니다. 같은 유형·분류의 최근 연도 통계입니다.\n"
                            "경쟁 등급: 같은 조달 유형의 분류별 최근 연도 참가업체 수 중앙값 순위를 3등분합니다. "
                            "하위 1/3은 낮음, 중간 1/3은 보통, 상위 1/3은 높음입니다. 동률은 원본 분류 순서로 나누며, 절대적인 진입 난이도가 아닙니다.\n"
                            "참가업체 수: 과거 개찰의 참가업체 수를 작은 순으로 정렬한 가운데 값\n"
                            "단독입찰 비율: 참여가 있었던 개찰 중 업체가 1곳인 비율\n"
                            "상위 3개 업체 점유: 상위 3개 업체가 차지한 낙찰 건수 비중이며 계약금액 점유율과는 다릅니다.\n"
                            "계약까지 걸린 날: 해당 분류에서 공고일부터 첫 계약일까지 걸린 기간의 중앙값이며, 개별 공고의 이행 기간이 아닙니다.", key="competition")
            if competition_loader:
                cache_key = 'detail_competition_' + str(n['item_code'])
                cached_stats = st.session_state.get(cache_key, {})
                if not cached_stats or monotonic() - cached_stats.get('checked_at', 0) >= 3600:
                    # 저장 상세·요건 상태를 먼저 그린 뒤, 기존 통계 캐시를 읽는다.
                    st.caption('분류의 과거 경쟁 자료 찾는 중…')
                    st.session_state[cache_key] = {'checked_at': monotonic(),
                                                   'result': read('분류 과거 경쟁 자료를 불러오는 중…', competition_loader, n['item_code'])}
                stats = st.session_state[cache_key]['result']
                c, days = stats['competition'], stats['contract_days']
            if c is None:
                st.caption("이 분류의 과거 경쟁 자료가 없습니다.")
            else:
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(f":gray-badge[경쟁 {c['level'] or '–'} · 분류 전체 기준] "
                                f":gray-badge[{int(c['year'])}년 · 개찰 {num(c['event_count'])}건]", width="stretch")
                stats = [("참가업체 수 (중앙값)", f"{num(c['median_bidders'], 1)}곳", "과거 개찰의 참가업체 수를 작은 순으로 정렬한 가운데 값"),
                         ("단독입찰 비율", pct(c["single_bid_rate"]), "참여가 있었던 개찰 중 업체가 1곳인 비율"),
                         ("상위 3개 업체 점유", pct(c["top3_share_count"]), "상위 3개 업체가 차지한 낙찰 건수 비중입니다. 계약금액 점유율과는 다릅니다."),
                         ("계약까지 걸린 날 (중앙값)", f"{days:.0f}일" if days is not None else "–", "이 분류에서 공고일부터 첫 계약일까지 걸린 기간의 가운데 값. 개별 공고의 이행 기간이 아닙니다.")]
                for i, (col, (label, value, description)) in enumerate(zip(st.columns(4), stats)):
                    with col.container(border=True, height="stretch", key=f"info_detail_comp_{i}", gap="small"):
                        st.markdown(f"#### {label}")
                        st.subheader(value, anchor=False)

        def build() -> bytes:
            rep = Report(n["notice_name"], f"{n['procurement_type']} · {cat_name} · {dday_text(d)}",
                         footer="Frontline Data · 국방 조달 탐색")
            rep.kv([("마감", n["bid_close_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(n["bid_close_date"]) else "–"),
                    ("수요기관", n["demand_agency_name"]), ("종합 판단", notice_status_label(status))])
            report_conditions = conditions.drop(columns=['입력 안내'], errors='ignore').copy()
            report_conditions["판단"] = [condition_verdict(row)[0] if row.get('입력 안내')
                                         else notice_status_label(row['판단'])
                                         for row in conditions.to_dict('records')]
            rep.heading("참여 조건").table(report_conditions)
            if det.get('participation_requirements'):
                rep.heading('기타 참가조건 · 원문 검토 필요').kv([
                    (item['category'], item['summary']) for item in det['participation_requirements']])
                rep.para('확인된 참가자격 발췌의 분류입니다. 모두/하나 충족·예외·기준일은 원문에서 확인해야 하며 회사 조건과 자동 비교하지 않습니다.')
            rep.para(SCOPE_NOTE)
            if c is not None:
                rep.heading(f"이 분류의 과거 경쟁 ({int(c['year'])}년 · 개찰 {num(c['event_count'])}건 기준)").kv([
                    ("참가업체 중앙값", f"{num(c['median_bidders'], 1)}곳"), ("단독입찰", pct(c["single_bid_rate"])),
                    ("상위 3개 업체 점유", pct(c["top3_share_count"])),
                    ("계약까지 걸린 날(중앙값)", f"{days:.0f}일" if days is not None else "–")])
            rep.heading("원문").para(str(n["notice_url"]), size=7)
            return rep.build()

        with st.container(horizontal=True, key="detail_footer_actions"):
            url = n.get("notice_url")
            st.link_button("나라장터 원문 보기", url if pd.notna(url) else "", type="secondary",
                           icon=":material/open_in_new:", key="detail_original_link",
                           disabled=pd.isna(url) or not str(url).strip())
            if st.button("분야별 입찰 분석 보기", icon=":material/insights:", type="primary", disabled=c is None):
                st.session_state.sel_item = n["item_code"]
                st.switch_page("app_pages/item.py")
            pdf_button("이 공고 PDF", f"공고_{safe_name(n['notice_name'])[:40]}.pdf", build, key="nt_one_pdf")
