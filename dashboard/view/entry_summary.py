"""Codex, 2026-10-01: 진입 요약의 표시만 재배치한다. 집계·PDF 원본은 보존한다."""

import pandas as pd
import streamlit as st
from view.help import help_icon


def summary_tables(checks: pd.DataFrame, level, level_year):
    """기존 관측값과 기준을 읽어 좌우 3행·기관 1행으로 구성한다."""
    source = checks.set_index("확인 항목")
    descriptions = {
        "단독입찰": "개찰 중 단독입찰 비율",
        "업체 쏠림": "낙찰 건수 기준 상위 3개 업체 점유율",
        "면허 제한": "공고 중 면허 제한이 있는 비율",
        "지역 제한": "공고 중 지역 제한이 있는 비율",
        "계약까지 걸린 날": "공고부터 첫 계약까지 걸린 기간의 중앙값",
    }

    def row(name):
        item = source.loc[name]
        label = "계약기간(중앙값)" if name == "계약까지 걸린 날" else name
        value = str(item["관측값"])
        if name in ("면허 제한", "지역 제한"):
            value = value.removeprefix("공고의 ")
        elif name == "업체 쏠림" and value.startswith("상위 3개 업체가 낙찰의 "):
            value = value.replace("상위 3개 업체가 낙찰의 ", "상위 3개 업체 ", 1)
        elif name == "계약까지 걸린 날":
            value = value.removesuffix(" (중앙값)")
        detail = descriptions.get(name, value)
        if name == "경쟁 수준" and level:
            value = f":blue-badge[경쟁 {level}]" if level != "표본 적음" else ":gray-badge[표본 적음]"
            if level_year is not None:
                detail += f"\n등급: {int(level_year)}년 분류 전체 기준"
            detail += "\n경쟁 등급은 선택 기간·기관·금액 조건으로 다시 평가한 값이 아닙니다. 같은 유형의 분류별 최근 연도 참가업체 중앙값 순위를 3등분한 상대 비교이며, 절대 진입 난이도가 아닙니다."
        elif name == "경쟁 수준":
            detail = "개찰 1건당 참가업체 수 (중앙값)"
        detail += f"\n\n기준: {item['기준']}"
        return [f"**{label}**", f"**{value}**" if name != "경쟁 수준" else value, detail]

    columns = ["확인 항목", "관측값", "설명·기준"]
    left = pd.DataFrame([row(n) for n in ("경쟁 수준", "단독입찰", "업체 쏠림")], columns=columns)
    right = pd.DataFrame([row(n) for n in ("면허 제한", "지역 제한", "계약까지 걸린 날")], columns=columns)
    agencies = source.loc["주요 수요기관"]
    bottom = pd.DataFrame([["**주요 수요기관**", str(agencies["관측값"]),
                           f"공고 수가 많은 순입니다.\n기준: {agencies['기준']}"]], columns=columns)
    return left, right, bottom


def entry_summary(checks, *, level=None, level_year=None):
    left, right, agencies = summary_tables(checks, level, level_year)

    def render_row(row, key):
        label, value, detail = row
        with st.container(horizontal=True, wrap=False, vertical_alignment="center", gap="small",
                          key=f"entry_row_{key}"):
            with st.container(width=190, horizontal=True, wrap=False,
                              vertical_alignment="center", gap="xxsmall", key=f"entry_label_{key}"):
                st.markdown(label.strip("*"), width="content")
                help_icon(label.strip("*"), detail, key=f"entry_help_{key}", symbol="i")
            with st.container(width="stretch", key=f"entry_value_{key}"):
                st.markdown(value)

    with st.container(border=True, key="entry_summary", gap="xsmall"):
        st.subheader("진입 조건 요약", icon=":material/description:", anchor=False)
        with st.container(key="entry_summary_grid", gap=None):
            cols = st.columns(2, gap=None)
            for index, frame in enumerate((left, right)):
                with cols[index], st.container(key=f"entry_summary_half_{index}", gap=None):
                    for number, row in enumerate(frame.itertuples(index=False, name=None)):
                        render_row(row, f"{index}_{number}")
        with st.container(key="entry_summary_agencies", gap=None):
            render_row(agencies.iloc[0], "agencies")
