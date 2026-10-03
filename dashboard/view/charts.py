"""차트·카드·요약 타일 공통 규칙.

사용자 피드백(2026-09-28): 축이 없어 뜻을 모르겠다 / 한 줄 카드 높이가 제각각 / 글자가 작다 / 참고 이미지처럼.
- 차트마다 **질문형 제목**(카드 제목) + **축 제목과 단위**. 축 글자 14px, 축 제목 15px, 범례 위쪽.
- 한 줄 최대 2개, 같은 줄 카드는 부모 열에 맞춰 늘어나며 차트 전체 높이를 통일한다.
- 카드 모양은 Streamlit 테마를 따른다. 요약 지표와 차트 계열은 테마 팔레트 색을 쓴다.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager

import altair as alt
import streamlit as st
from view.help import help_label
from view.assets import CARD_SYMBOLS, card_icon_html

CHART_H = 420      # 축·범례를 포함한 차트 전체 높이
ITEM_CHART_H = 252  # 품목 시장·경쟁: 기존 높이의 60%, 축·범례 포함
PROCUREMENT_TYPES = ["공사", "물품", "외자", "용역"]


def procurement_color(title: str | None = "조달 유형", legend: alt.Legend | None = None) -> alt.Color:
    """필터로 유형이 빠져도 색 매핑이 변하지 않는다. 실제 색은 라이트·다크 테마를 따른다."""
    options = {"legend": legend} if legend is not None else {}
    return alt.Color("procurement_type:N", title=title, scale=alt.Scale(domain=PROCUREMENT_TYPES), **options)


def procurement_dash() -> alt.StrokeDash:
    """색만으로 구분하기 어려운 겹친 선에 보조 식별자를 제공한다."""
    return alt.StrokeDash("procurement_type:N", title="조달 유형",
                          scale=alt.Scale(domain=PROCUREMENT_TYPES, range=[[1, 0], [8, 3], [2, 3], [8, 3, 2, 3]]))
# 카드·타일은 높이를 픽셀로 고정하지 않는다(고정하면 내용이 넘칠 때 카드 안에 스크롤이 생김 — 사용자 지시:
# 페이지 본문 말고는 어디에도 스크롤이 없어야 한다). 대신 "stretch"로 같은 줄에서 가장 긴 칸 높이에 맞춘다.
STRETCH = "stretch"


def _key(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:10]}"


def finish(chart: alt.Chart, height: int = CHART_H) -> alt.Chart:
    # 축별 설정이 공통 config보다 우선한다. 기존 라벨·단위 설정을 유지하며 격자만 보정한다.
    chart = chart.copy(deep=True)

    def grid_axes(node):
        encoding = getattr(node, "encoding", alt.Undefined)
        if encoding is not alt.Undefined:
            for channel in ("x", "y"):
                field = getattr(encoding, channel, alt.Undefined)
                if field is alt.Undefined:
                    continue
                axis = field.to_dict().get("axis", {})
                if axis is None:
                    continue
                field.axis = alt.Axis(**{**axis, "grid": True})
        layers = getattr(node, "layer", alt.Undefined)
        if layers is not alt.Undefined:
            for layer in layers:
                grid_axes(layer)

    grid_axes(chart)
    # 전체 캔버스 높이를 맞춘다. 도넛은 실제 width/height에 맞춰 반지름을 줄여 잘림을 막는다.
    return (chart.properties(height=height, autosize=alt.AutoSizeParams(type="fit", contains="padding", resize=True),
                             padding={"left": 10, "right": 14, "top": 8, "bottom": 6})
            .configure_axis(labelFontSize=14, titleFontSize=15, labelColor="currentColor", titleColor="currentColor",
                            titlePadding=10, labelLimit=280, labelAngle=0,
                            grid=True, gridColor="currentColor", gridOpacity=0.16, gridWidth=1, domain=False)
            .configure_legend(orient="top", labelFontSize=14, titleFontSize=14,
                              labelColor="currentColor", titleColor="currentColor", symbolSize=120, labelLimit=260,
                              columnPadding=4)
            .configure_text(color="currentColor")
            .configure_view(stroke=None))


@contextmanager
def card(title: str, note: str = "", caution: str = ""):
    """테두리 카드: 큰 제목 + 작은 설명 + 내용 + 맨 아래 주의(작은 글자).
    같은 줄 카드는 가장 긴 카드 높이에 맞춰 늘어난다.
    글자 크기 원칙(사용자 지시): 핵심 값·제목은 크게, 주의·각주는 작게(caption)."""
    with st.container(border=True, height=STRETCH, key=_key("card", title)):
        with st.container(key=_key("chart_header", title), gap="xsmall"):
            st.subheader(title, anchor=False)
            if note:
                st.caption(note)
        yield
        if caution:
            st.caption(caution)


def empty_chart(*, height=CHART_H, key=None):
    """데이터 없음은 제목 밑이 아닌 실제 그래프 높이의 정중앙에 표시한다."""
    with st.container(height=height, border=False, key=key,
                      horizontal_alignment="center", vertical_alignment="center"):
        st.markdown("표시할 항목이 없습니다.", width="content")


def show(chart: alt.Chart, height: int = CHART_H):
    st.altair_chart(finish(chart, height))


def kpi_tiles(items: list[dict], prefix: str):
    """색 요약 타일 한 줄. item: label, value, (delta, delta_description, color, note, help).

    작은 추세선(sparkline)은 넣지 않는다 — 축이 없어 무엇을 뜻하는지 알 수 없다는 사용자 피드백(2026-09-28).
    대신 `note`에 기준(예: "2025년 기준")을 글로 적는다.
    """
    for i, (col, it) in enumerate(zip(st.columns(len(items)), items)):
        color = it.get("color", "blue")
        with col, st.container(border=True, height=STRETCH, key=f"kpi_{color}_{prefix}_{i}"):
            delta = it.get("delta") if it.get('show_delta', True) else None
            known_delta = delta not in (None, "", "–", "−", "-")
            with st.container(horizontal=True, vertical_alignment="center", gap="small",
                              key=f"kpi_heading_{prefix}_{i}"):
                icon_html = card_icon_html(it["label"], prefix=prefix)
                if icon_html:
                    st.html(icon_html, width=38)
                elif it["label"] in CARD_SYMBOLS:
                    with st.container(width=48, key=f"kpi_symbol_{color}_{prefix}_{i}"):
                        st.markdown(f":{color}[:material/{CARD_SYMBOLS[it['label']]}:]")
                if it.get("help"):
                    help_label(it["label"], it["help"], key=f"help_{prefix}_{i}", color=color)
                else:
                    st.markdown(f"**:{color}[{it['label']}]**", width="stretch")
            if it.get("instruction"):
                st.caption(it["instruction"])
                continue
            st.metric(f":{color}[{it['label']}]", it["value"], delta,
                      delta_description=it.get("delta_description", "전년 대비" if delta else None),
                      label_visibility="collapsed",
                      delta_color=("blue" if str(delta).startswith("-") else "red") if known_delta else "off",
                      delta_arrow="auto" if known_delta else "off")
            if it.get('sample_badge'):
                st.badge(it['sample_badge'], color=it.get('sample_badge_color', 'gray'),
                         help='관측 계약 건수에 대한 표시 안내입니다. 1~5건은 매우 적음, 6~29건은 제한적입니다. 비교 양쪽 연도가 모두 6건 이상일 때 증감을 표시하며, 30건 이상도 데이터의 완전성을 보장하지 않습니다.')
            if it.get('sample_caption') and it['label'] != '계약 건수':
                st.caption(it['sample_caption'])
            if it.get("note"):
                st.markdown(it["note"])


def info_cards(items: list[tuple[str, str]], prefix: str = "info", descriptions: list[str] | None = None,
               columns: int | None = None, secondary_values: list[str] | None = None):
    """라벨 + 값 카드. 긴 값은 말줄임하지 않고, columns로 한 줄의 카드 수를 정한다."""
    if not items:
        return
    column_count = max(1, min(columns or len(items), len(items)))
    for row_start in range(0, len(items), column_count):
        row_items = items[row_start:row_start + column_count]
        for offset, (col, (label, value)) in enumerate(zip(st.columns(len(row_items)), row_items)):
            i = row_start + offset
            with col, st.container(border=True, height="stretch", gap="xxsmall", key=_key("info", f"{prefix}{i}{label}")):
                st.markdown(f"#### :gray[{label}]")
                st.subheader(str(value), anchor=False)
                if secondary_values and i < len(secondary_values) and secondary_values[i]:
                    st.caption(secondary_values[i])
                if descriptions and i < len(descriptions):
                    st.caption(descriptions[i])
