"""DB와 독립적인 영상 홈. 미디어는 Streamlit이 제공하며 대시보드로 기본 라우팅한다."""

import streamlit as st

from view.home import HERO_VIDEO, apply_home_style, home_copy


apply_home_style()
with st.container(key="home_screen", gap="small"):
    if HERO_VIDEO.is_file():
        with st.container(key="home_video"):
            st.video(HERO_VIDEO, format="video/mp4", autoplay=True, muted=True,
                     loop=True, width="stretch")
    with st.container(key="home_content", gap="medium"):
        st.html(home_copy())
        if st.button("대시보드 바로 가기 →", key="home_enter", width="content"):
            st.switch_page("app_pages/notices.py")
