"""검색 조건 요약 공통 UI. 실제 적용 조건만 전달한다."""
import streamlit as st


def search_summary(conditions: list[str], key: str):
    with st.container(border=True, gap="xsmall", key=key):
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"filter_summary_heading_{key}"):
            with st.container(width=48, key=f"filter_summary_icon_{key}"):
                st.markdown(":blue[:material/manage_search:]")
            with st.container(width="stretch", gap="xxsmall", key=f"filter_summary_text_{key}"):
                st.markdown("**현재 검색 조건**")
                st.caption("  |  ".join(conditions))
