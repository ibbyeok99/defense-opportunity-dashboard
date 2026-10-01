"""여러 화면이 함께 쓰는 사이드바 입력과 작은 UI 조각.

데이터를 직접 읽지 않는다(service를 import하지 않음). 선택지 목록은 화면이 service에서 받아 넘긴다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from view.fmt import region_display
from view.help import help_label


def filter_area():
    """화면별 필터를 넣을 사이드바 자리(내 회사 조건 바로 아래). streamlit_app.py가 매 실행 잡아 둔다."""
    return st.session_state.get("_filter_slot") or st.sidebar


def emphasized_table(frame: pd.DataFrame, *, highlight_columns: tuple[str, ...] = (), height="content"):
    """기본 표의 헤더 강조. 원본 값과 행·열 순서는 유지한다."""
    display = frame.copy()
    table_options = {} if height == "content" else {"height": height}
    if highlight_columns:
        dark_mode = st.context.theme.type == "dark"
        header_background = "#40516A" if dark_mode else "#C4D0DE"
        header_text = "#F0F2F5" if dark_mode else "#293241"
        highlight_header_background = "#70501F" if dark_mode else "#FFE1A6"
        highlight_cell_background = "#4B3B26" if dark_mode else "#FFF0CC"
        highlight_text = "#FFF4D6" if dark_mode else "#293241"
        highlight_border = "#FFB340" if dark_mode else "#D97706"
        styles = [
            {"selector": "thead th", "props": [
                ("font-weight", "700"),
                ("color", header_text),
                ("background-color", header_background),
                ("border-bottom", "2px solid var(--st-border-color)"),
            ]},
            {"selector": "tbody th", "props": [
                ("font-weight", "700"),
                ("color", "var(--st-text-color)"),
                ("background-color", "var(--st-secondary-background-color)"),
            ]},
        ]
        for column in highlight_columns:
            if column not in display.columns:
                continue
            column_index = display.columns.get_loc(column)
            styles.append({"selector": f"th.col_heading.col{column_index}", "props": [
                ("font-weight", "700"),
                ("color", highlight_text),
                ("background-color", highlight_header_background),
                ("border-bottom", f"2px solid {highlight_border}"),
            ]})
        styled = display.style.set_table_styles(styles)
        for column in highlight_columns:
            if column in display.columns:
                styled = styled.set_properties(subset=[column], **{
                    "font-weight": "400",
                    "color": highlight_text,
                    "background-color": highlight_cell_background,
                    "border-left": f"3px solid {highlight_border}",
                })
        st.table(styled, **table_options)
        return

    display.columns = [f"**{name}**" for name in display.columns]
    display.index.names = [f"**{name}**" if name is not None else None for name in display.index.names]
    st.table(display, **table_options)


def filter_expander(label: str, key: str, icon: str | None = None):
    """기본 접힘. 기본 expander가 펼침 상태를 유지하며 제목에 조작 방법을 표시한다."""
    return st.expander(f"{label} · 펼치기/접기", expanded=False, key=key, icon=icon)


def company_profile(provinces: list[str], licenses: list[str]) -> tuple[list[str], list[str]]:
    """공고 화면 사이드바의 '내 회사 조건'(참여 판단용). 고르는 즉시 판단에 반영된다(검색 버튼 없음).

    영역은 기본 접힘이며 사용자가 펼치거나 접을 수 있다. 값은 브라우저에 저장된다.
    """
    region, lic = st.session_state.get("pf_region"), st.session_state.get("pf_licenses") or []
    if isinstance(region, str):
        region = [region]
    region = region or []
    st.session_state.pf_region = region
    # 상세 조건과 동일한 고정 제목·아이콘. 열림 화살표는 CSS가 실제 상태로 표시한다.
    with st.expander(":material/business: 내 회사 조건", expanded=False, key="pf_box",
                     on_change="rerun"):
        help_label("소재지 (시·도)", "선택한 지역 중 하나라도 허용 지역이면 충족합니다. 지점 참가 요건은 공고 원문에서 확인하세요.", key="help_pf_region")
        st.multiselect("소재지 (시·도)", provinces, placeholder="여러 지역 선택", key="pf_region",
                       format_func=region_display,
                       persist_state="session", select_all=False, label_visibility="collapsed")
        st.multiselect("보유 면허", licenses, key="pf_licenses", placeholder="면허 이름 검색",
                       persist_state="session", select_all=False, wrap=True)
        summarize_tags(".st-key-pf_licenses", len(lic), visible=5)
        summarize_tags(".st-key-pf_region", len(region), visible=5)
    return st.session_state.get("pf_region") or [], st.session_state.get("pf_licenses") or []


def summarize_tags(scope: str, n: int, visible: int = 1):
    """visible개까지 태그를 표시하고 초과 선택은 '외 N개'로 표시한다.
    태그가 칸 높이를 넘어 칸 안에 스크롤이 생기거나 잘리는 것도 막는다. 빼기는 펼친 목록에서.
    scope: 그 칸을 가리키는 CSS 선택자(위젯 key 클래스 — 한글 key는 클래스에서 '-'로 바뀌므로 접두어로 찾는다)."""
    # 첫 선택 전부터 같은 태그 제한 규칙을 둬서 rerun 중 임시로 여러 줄이 생기지 않게 한다.
    tags = f'{scope} [data-testid="stMultiSelectTagsContainer"] > span'
    extra = max(0, n - visible)
    display = "inline-flex" if extra else "none"
    st.html(f"<style>{tags} > span:nth-child(n+{visible + 1}) {{ display: none !important; }}"
            f'{tags}::after {{ content: "외 {extra}개"; display: {display}; font-size: .95rem; font-weight: 600;'
            f" margin-left: .35rem; white-space: nowrap; align-self: center; }}"
            "</style>")


def detail_expander(prefix: str, applied: int):
    """'상세 조건 · N개 적용' 접는 칸(기본 접힘, 적용 개수는 제목에)."""
    # label도 native 위젯 ID에 포함된다. 첫 선택(0→1) 때 label을 바꾸면 펼침 상태가 초기화된다.
    # 적용 개수는 표시 전용 suffix로 분리하고 위젯 label·key·expanded는 고정한다.
    suffix = f" · {applied}개 적용" if applied else ""
    st.html(f'<style>.st-key-{prefix}_detail_box summary p::after {{ content: "{suffix}"; }}</style>')
    # 제목은 고정하고 실제 details[open] 상태에 따른 ▲/▼는 style.py에서 표시한다.
    # 아이콘을 제목에 넣으면 native expander의 hover 화살표로 교체되지 않는다.
    # 사용자의 펼치기·접기 동작을 상태에 반영한다.
    # expanded는 초기값이자 위젯 ID 입력이므로 고정한다. 실제 열림은 key 상태로 제어한다.
    return st.expander(":material/tune: 상세 조건", expanded=False,
                       key=f"{prefix}_detail_box", on_change="rerun")


def _short_label(row) -> str:
    """공식 표시명과 본문 제목을 일치시킨다. 공고 예시는 별도 설명으로만 표시한다."""
    return str(row.get("display", row["category_value"]))


def pick_category(key_prefix: str, cats: pd.DataFrame, all_types: list[str], *,
                  event_counts: dict[str, int] | None = None) -> pd.Series | None:
    """사이드바의 유형·분류 선택. 선택은 화면 사이에서 공유한다(session_state 'sel_item').
    cats: service.data.categories() 표. 선택칸은 짧게, 대표 공고·개찰 수는 아래 설명 줄에(글자 잘림 방지)."""
    types = [t for t in all_types if t in set(cats["procurement_type"])]
    current = st.session_state.get("sel_item")
    known = set(cats["item_code"])
    cur_type = cats.loc[cats["item_code"] == current, "procurement_type"].iloc[0] if current in known else types[0]

    with filter_area():
        ptype = st.pills("조달 유형", types, default=cur_type, required=True, key=f"{key_prefix}_type")
        sub = cats[cats["procurement_type"] == ptype]
        codes = sub["item_code"].tolist()
        labels = dict(zip(sub["item_code"], sub.apply(_short_label, axis=1)))
        index = codes.index(current) if current in codes else 0
        code = st.selectbox("분야·분류 (이름·번호로 검색)", codes, index=index, format_func=labels.get,
                            key=f"{key_prefix}_item")
        if code is not None:
            row = sub[sub["item_code"] == code].iloc[0]
            example = f"대표 공고: {row['example']} · " if row["example"] and str(row["category_value"]).isdigit() else ""
            count = int(row["events"]) if event_counts is None else event_counts.get(code, 0)
            basis = "" if event_counts is None else "현재 조건 · "
            st.caption(f":gray[{example}{basis}개찰 {count:,}건]")
    if code is None:
        return None
    st.session_state.sel_item = code
    return sub[sub["item_code"] == code].iloc[0]


# ---- 공통 필터 위젯(사용자 지정 목록 2026-09-28). 모두 filter_area() 안에서 부른다. 빈 선택 = 전체. ----
def sidebar_toolbar(prefix: str, defaults: dict, extra=None):
    """스크롤과 독립적인 사이드바 하단: 초기화·저장한 검색.

    공고에서는 목록 범위를 유지하고 검색·회사 조건을 모두 초기화한다.
    """
    def _reset():
        for k, v in defaults.items():
            if k != "nt_scope":
                st.session_state[k] = v
        if prefix == "nt":
            st.session_state.pf_region = []
            st.session_state.pf_licenses = []
    with st.session_state.get("_sidebar_actions_slot") or st.sidebar:
        st.divider()
        with st.container(horizontal=True, gap="xsmall", key=f"sbtool_{prefix}"):
            st.button("필터 초기화", icon=":material/restart_alt:", type="tertiary", on_click=_reset, key=f"{prefix}_reset")
            if extra:
                extra()


def period_filter(prefix: str, year_range: tuple[int, int]) -> tuple[int, int]:
    st.session_state.setdefault(f"{prefix}_years", year_range)
    return st.slider("분석 기간 (개찰 연도)", year_range[0], year_range[1], key=f"{prefix}_years",
                     persist_state="session")


def agency_filter(prefix: str, names_by_role: dict[str, list[str]], *,
                  labels_by_role: dict[str, dict[str, str]] | None = None) -> tuple[str, list[str]]:
    """기관 역할(수요기관/공고기관) + 기관 여러 개. 계약기관은 공고·개찰 자료에 없어 공고기관으로 대신한다."""
    st.session_state.setdefault(f"{prefix}_agency_role", "수요기관")
    role = st.segmented_control("기관 기준", list(names_by_role), required=True, key=f"{prefix}_agency_role",
                                persist_state="session")
    key = f"{prefix}_agency_{role}"
    options = list(dict.fromkeys(names_by_role[role] + list(st.session_state.get(key) or [])))
    labels = (labels_by_role or {}).get(role, {})
    summarize_tags(f'[class*="st-key-{prefix}_agency_"]', len(st.session_state.get(key) or []))
    picked = st.multiselect(f"{role} (여러 개 선택)", options, key=key, placeholder="전체 기관",
                            format_func=lambda value: labels.get(value, value), persist_state="session", wrap=False)
    return role, picked


def amount_filter(prefix: str, bins: list[str], note: str) -> list[str]:
    help_label("낙찰금액 범위", note, key=f"help_{prefix}_amount")
    return st.pills("낙찰금액 범위", bins, selection_mode="multi", key=f"{prefix}_amount", persist_state="session",
                    label_visibility="collapsed")


def safe_name(s: str) -> str:
    """파일 이름에 쓸 수 없는 글자를 밑줄로."""
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(s)).strip("_")[:60] or "report"


def pdf_button(label: str, file_name: str, build, key: str, **kw):
    """PDF는 버튼을 누를 때만 만든다(data에 함수 전달)."""
    selftest_dir = os.environ.get("FRONTLINE_PDF_SELFTEST_DIR")  # 테스트 전용: 버튼 없이 바로 파일로 저장
    if selftest_dir:
        Path(selftest_dir, file_name).write_bytes(build())
    st.download_button(label, data=build, file_name=file_name, mime="application/pdf",
                       icon=":material/picture_as_pdf:", key=key, on_click="ignore", **kw)
