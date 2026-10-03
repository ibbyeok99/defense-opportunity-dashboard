"""Codex, 2026-09-30: 공통 제목·메뉴와 화면 설명. 데이터 연결과 독립적이다."""

import streamlit as st

APP_TITLE = "국방조달 기회 찾기"
APP_SUBTITLE = "데이터로 보는 국방 조달 시장"
PAGE_LABELS = {
    "notices": "국방 입찰공고 찾기",
    "item": "분야별 입찰 분석",
    "overview": "국방 조달 시장 동향",
    "favorites": "즐겨찾기",
}
PAGE_DESCRIPTIONS = {
    "notices": "나라장터에서 수집한 국방 관련 입찰공고를 검색하고 참가 조건을 확인합니다.",
    "item": "물품·공사·용역·외자 분야별 계약 추이, 경쟁 수준, 참가 조건을 확인합니다.",
    "overview": "국방 관련 공고·계약 추이와 주요 수요기관·조달 분야를 살펴봅니다.",
    "favorites": "저장한 공고 최대 10개를 관리하고, 최대 4개를 나란히 비교합니다.",
}


def app_header(pages, current_page):
    """기본 라우터를 유지하고 제목 아래 웹페이지형 링크 메뉴를 배치한다."""
    with st.container(key="app_sticky_header"):
        with st.container(horizontal=True, vertical_alignment="top", key="page_heading_app"):
            with st.container(width="stretch", gap="xxsmall", key="app_title_block"):
                with st.container(key="app_title_link"):
                    st.page_link("app_pages/notices.py", label=APP_TITLE, icon="", width="content")
                with st.container(key="app_subtitle"):
                    st.markdown(APP_SUBTITLE)
            st.session_state._export_slot = st.container(
                horizontal=True, horizontal_alignment="right", width="content", key="exports_app", gap="xsmall")
        public_pages = [page for page in pages if page.url_path not in {"admin", "quality"}]
        management_pages = [page for page in pages if page.url_path in {"admin", "quality"}]
        with st.container(horizontal=True, wrap=True, gap="small", horizontal_alignment="distribute", key="page_menu"):
            for group, key in ((public_pages, "page_menu_public"), (management_pages, "page_menu_management")):
                if not group:
                    continue
                with st.container(horizontal=True, wrap=True, gap="small", width="content", key=key):
                    for page in group:
                        selected = page.url_path == current_page.url_path
                        with st.container(width="content", key=f"nav_{'active' if selected else 'link'}_{page.url_path or 'notices'}"):
                            st.page_link(page, label=f":blue[**{page.title}**]" if selected else page.title,
                                         icon=page.icon, width="content")


def page_header(name: str):
    with st.container(key="page_content_heading", gap="xxsmall"):
        if name not in ("notices", "item", "overview", "favorites"):
            st.header(PAGE_LABELS[name], anchor=False)
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            with st.container(width="stretch"):
                st.caption(PAGE_DESCRIPTIONS[name])
            if name == "notices":
                st.page_link("app_pages/institutions.py", label="국방 기관·선정 기준", icon=":material/policy:", width="content")
                st.page_link("app_pages/category_criteria.py", label="분류명 매칭 기준", icon=":material/rule:", width="content")
