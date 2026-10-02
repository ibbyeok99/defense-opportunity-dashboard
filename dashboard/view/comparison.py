"""공고 비교 표시: 공고 자체 조건과 분류 과거 지표를 구분하며, 누락 값을 0으로 바꾸지 않는다."""

import pandas as pd
import streamlit as st

from view.fmt import notice_identifier, notice_status_label, num, pct, region_display, dday_text
from view.help import help_icon
from view.reference_table import reference_table


def compare_notices(details: list[dict]) -> pd.DataFrame:
    if len(details) > 4:
        raise ValueError("공고 비교는 최대 4개입니다.")
    columns = {}
    for i, det in enumerate(details, 1):
        n = det["notice"]
        def date_value(key):
            value = n.get(key)
            return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M") if pd.notna(value) else "미확인"
        entries = {
            "공고명": n["notice_name"], "공고번호·차수": notice_identifier(n),
            "조달 유형": n["procurement_type"], "분류": det["category"],
            "수요기관": n["demand_agency_name"], "공고기관": n["notice_agency_name"],
            "공고일": date_value("notice_date"), "마감": date_value("bid_close_date"),
            "금액 확인": "원문에서 배정예산·추정가격 확인 (비교 화면 미연결)",
            "내 회사 조건 비교": notice_status_label(det["status"]),
        }
        for _, condition in det["conditions"].iterrows():
            required = condition["요구 조건"]
            if condition["구분"] == "지역":
                required = ", ".join(region_display(p) for p in required.split(", "))
            entries[f"{condition['구분']} 요구 조건"] = required
        c = det.get("competition")
        entries["과거 경쟁 기준"] = f"{int(c['year'])}년 · 분류 전체" if c is not None else "자료 없음"
        entries["과거 개찰 표본 수 (분류)"] = f"{num(c['event_count'])}건" if c is not None and pd.notna(c.get('event_count')) else "자료 없음"
        entries["참가업체 중앙값 (분류)"] = f"{num(c['median_bidders'], 1)}곳" if c is not None else "자료 없음"
        entries["단독입찰 비율 (분류)"] = pct(c["single_bid_rate"]) if c is not None else "자료 없음"
        entries["상위 3개 업체 점유 (분류)"] = pct(c["top3_share_count"]) if c is not None else "자료 없음"
        days = det.get("contract_days")
        entries["계약 소요일 중앙값 (분류)"] = f"{days:.0f}일" if days is not None else "자료 없음"
        columns[f"공고 {i}"] = entries
    return pd.DataFrame(columns).fillna("미확인")


def comparison_sections(details):
    """같은 원본 비교 결과를 업무 요건·기본 정보·분류 참고로 분리한다."""
    frame = compare_notices(details)
    key_rows = [r for r in frame.index if r in ("마감", "내 회사 조건 비교") or r.endswith("요구 조건")]
    reference_rows = [r for r in frame.index if r.startswith("과거 ") or "(분류)" in r]
    basics = [r for r in frame.index if r not in key_rows + reference_rows]
    return frame.loc[key_rows].copy(), frame.loc[basics].copy(), frame.loc[reference_rows].copy()


def difference_rows(frame):
    """다른 값이 있는 행만 식별한다. 값의 우열·충족 여부는 새로 판정하지 않는다."""
    return frame.nunique(axis=1, dropna=False).gt(1)


def render_comparison(details, today, *, on_detail=None):
    if len(details) < 2:
        st.info("비교 가능한 공고를 2개 이상 선택하세요.")
        return
    key, basics, reference = comparison_sections(details)
    st.caption("마감과 요구 조건을 대조해 먼저 검토할 공고를 고르세요. 공고 순서는 선택 순서이며 추천 순위가 아닙니다.")
    for i, (col, detail) in enumerate(zip(st.columns(len(details)), details), 1):
        n = detail["notice"]
        deadline = n.get("bid_close_date")
        days = (pd.Timestamp(deadline).normalize() - pd.Timestamp(today)).days if pd.notna(deadline) else None
        with col.container(border=True, height="stretch", key=f"card_compare_{i}"):
            with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
                st.badge(f"공고 {i}", color="blue")
                if on_detail is not None:
                    st.button("", icon=":material/open_in_new:", help=f"공고 {i} 상세 보기",
                              key=f"fav_compare_detail_{n['notice_id']}", on_click=on_detail,
                              args=(n["notice_id"],))
            st.metric("마감까지", dday_text(days))
            st.caption(pd.Timestamp(deadline).strftime("%Y-%m-%d %H:%M") if pd.notna(deadline) else "마감일 미확인")
            tone = {"● 참여 가능": "green", "▲ 원문 확인": "orange", "■ 참여 불가": "red"}.get(detail["status"], "gray")
            st.badge(notice_status_label(detail["status"]), color=tone)
            # 긴 공고명 때문에 비교의 핵심인 마감 수치·판단 위치가 어긋나지 않게 한다.
            st.markdown(f"**{n['notice_name']}**")
            st.caption(f"{n['procurement_type']} · {n['demand_agency_name']}")

    with st.container(horizontal=True, vertical_alignment="center"):
        st.subheader("요건 차이 비교", anchor=False, width="stretch")
        help_icon("요건 비교", "‘차이’ 표시는 값이 다르다는 의미일 뿐 우열을 뜻하지 않습니다. 미확인은 제한 없음이 아닙니다. 최종 참가 자격은 원문으로 확인하세요.", key="fav_compare_help")
    only_different = st.toggle("차이가 있는 항목만 보기", key="fav_compare_differences")
    differences = difference_rows(key)
    visible = key.loc[differences].copy() if only_different else key.copy()
    if visible.empty:
        st.caption("현재 비교 항목의 표시값이 같습니다. 공고 전체 조건이 같다는 뜻은 아닙니다.")
    else:
        visible.index = [f"{r} :blue-badge[차이]" if differences.loc[r] else r for r in visible.index]
        reference_table(visible.rename_axis("항목"), key="fav_compare_conditions_table", label="요건 차이 비교",
                        badge_columns=("항목",), widths={"항목": 180})
    with st.expander("기본 정보·금액 확인", expanded=False):
        reference_table(basics.rename_axis("항목"), key="fav_compare_basics_table", label="기본 정보·금액 확인",
                        widths={"항목": 180})
    with st.expander("분류별 과거 통계 참고", expanded=False):
        st.caption("개별 공고의 경쟁 예측이 아닙니다. 유형·분류·연도·표본 수가 다르면 동일한 경쟁 조건으로 해석할 수 없습니다. 같은 분류의 공고에는 같은 통계가 반복됩니다.")
        reference_table(pd.concat([basics.loc[["조달 유형", "분류"]], reference]).rename_axis("항목"),
                        key="fav_compare_reference_table", label="분류별 과거 통계 참고", widths={"항목": 180})
