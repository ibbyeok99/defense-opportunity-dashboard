"""공고 목록·즐겨찾기에서 공유하는 상세 창. 계산 결과만 전달받는다."""

import pandas as pd
import streamlit as st
from view import store
from view.charts import info_cards
from view.fmt import num, pct, region_display, notice_status_label, notice_identifier, dday_text
from view.pdf import Report
from view.widgets import emphasized_table, pdf_button, safe_name


@st.dialog("공고 상세", width="large")
def show_detail(det: dict, today, color: str = "gray"):
    n, status, conditions = det["notice"], det["status"], det["conditions"]
    c, days, cat_name = det["competition"], det["contract_days"], det["category"]
    d = (n["bid_close_date"].normalize() - pd.Timestamp(today)).days if pd.notna(n["bid_close_date"]) else None
    urgent = "orange" if d is not None and 0 <= d <= 7 else "gray"
    with st.container(key="notice_detail_title"):
        st.markdown(f"## {n['notice_name']}")
    st.button("즐겨찾기 해제" if n["notice_id"] in store.favorites() else "즐겨찾기 추가",
              icon=":material/star:" if n["notice_id"] in store.favorites() else ":material/star_border:",
              key=f"detail_star_{n['notice_id']}", on_click=store.toggle_favorite, args=(n["notice_id"],))
    st.markdown(f":{urgent}-badge[{dday_text(d)}] :{color}-badge[{notice_status_label(status)}] "
                f":gray-badge[{n['procurement_type']}] :gray-badge[{cat_name}]")
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption(f"공고번호·차수: {notice_identifier(n)}", width="stretch")
        st.link_button("나라장터 원문", n["notice_url"], icon=":material/open_in_new:", type="primary",
                       disabled=pd.isna(n["notice_url"]))
    st.subheader("공고 기본 정보", anchor=False)
    basics = [("마감", n["bid_close_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(n["bid_close_date"]) else "–"),
              ("공고일", n["notice_date"].strftime("%Y-%m-%d") if pd.notna(n["notice_date"]) else "–"),
              ("수요기관", n["demand_agency_name"]), ("공고기관", n["notice_agency_name"])]
    codes = ["", ""] + [f"({n[col]})" if pd.notna(n.get(col)) and str(n[col]).strip() else ""
                          for col in ("demand_agency_code", "notice_agency_code")]
    info_cards(basics, columns=2, secondary_values=codes,
               descriptions=["입찰서 제출을 마치는 시각", "공고가 게시된 날짜",
                             "물품·용역을 실제로 필요로 하는 기관", "공고를 게시하고 입찰을 진행하는 기관"])

    st.subheader("참여 조건", anchor=False)
    display_conditions = conditions.copy()
    display_conditions["판단"] = display_conditions["판단"].map(notice_status_label)
    for column in ("요구 조건", "내 조건"):
        mask = display_conditions["구분"] == "지역"
        display_conditions.loc[mask, column] = display_conditions.loc[mask, column].map(
            lambda v: ", ".join(region_display(part) for part in v.split(", ")))
    emphasized_table(display_conditions.set_index("구분"), highlight_columns=("요구 조건",))
    st.caption("요구 조건: 공고의 제한 · 내 조건: 입력한 소재지·면허  \n판단: 조건 비교 결과 · 이유: 판단 근거. 최종 자격은 공고 원문 기준입니다.")

    if c is not None:
        st.subheader("분류 기준의 과거 경쟁", anchor=False)
        st.markdown(f":gray-badge[경쟁 {c['level'] or '–'} · 분류 전체 기준] "
                    f":gray-badge[{int(c['year'])}년 · 개찰 {num(c['event_count'])}건]")
        with st.expander("경쟁 등급 산정 기준", expanded=False):
            st.caption("같은 조달 유형의 분류별 최근 연도 참가업체 수 중앙값 순위를 3등분합니다. "
                       "하위 1/3은 낮음, 중간 1/3은 보통, 상위 1/3은 높음입니다. "
                       "동률은 원본 분류 순서로 나누며, 절대적인 진입 난이도가 아닙니다.")
        stats = [("참가업체 수 (중앙값)", f"{num(c['median_bidders'], 1)}곳"), ("단독입찰 비율", pct(c["single_bid_rate"])),
                 ("상위 3개 업체 점유", pct(c["top3_share_count"])),
                 ("계약까지 걸린 날 (중앙값)", f"{days:.0f}일" if days is not None else "–")]
        info_cards(stats, prefix="comp", columns=2,
                   descriptions=["과거 개찰의 참가업체 수를 작은 순으로 정렬한 가운데 값",
                                 "참여가 있었던 개찰 중 업체가 1곳인 비율",
                                 "상위 3개 업체가 차지한 낙찰 건수 비중",
                                 "이 분류에서 공고일부터 첫 계약일까지 걸린 기간의 가운데 값"])

    def build() -> bytes:
        rep = Report(n["notice_name"], f"{n['procurement_type']} · {cat_name} · {dday_text(d)}",
                     footer="Frontline Data · 국방 조달 탐색")
        rep.kv([("마감", n["bid_close_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(n["bid_close_date"]) else "–"),
                ("수요기관", n["demand_agency_name"]), ("종합 판단", notice_status_label(status))])
        rep.heading("참여 조건").table(display_conditions)
        if c is not None:
            rep.heading(f"이 분류의 과거 경쟁 ({int(c['year'])}년 · 개찰 {num(c['event_count'])}건 기준)").kv([
                ("참가업체 중앙값", f"{num(c['median_bidders'], 1)}곳"), ("단독입찰", pct(c["single_bid_rate"])),
                ("상위 3개 업체 점유", pct(c["top3_share_count"])),
                ("계약까지 걸린 날(중앙값)", f"{days:.0f}일" if days is not None else "–")])
        rep.heading("원문").para(str(n["notice_url"]), size=7)
        return rep.build()

    with st.container(horizontal=True):
        if st.button("분야별 입찰 분석 보기", icon=":material/insights:", disabled=c is None):
            st.session_state.sel_item = n["item_code"]
            st.switch_page("app_pages/item.py")
        pdf_button("이 공고 PDF", f"공고_{safe_name(n['notice_name'])[:40]}.pdf", build, key="nt_one_pdf")
