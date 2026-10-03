"""국방조달 기회 찾기(프로토타입).

실행: dashboard 폴더에서 `streamlit run streamlit_app.py`
(설정 `.streamlit/config.toml`·비밀값 `.streamlit/secrets.toml`을 이 폴더에서 읽는다)

사이드바: 화면별 필터(각 화면이 그림, 내 회사 조건은 공고 화면만). 관리자 버튼은 본문 맨 아래 아주 작게.
"""

import streamlit as st

from service import data
from service.api_transport import DataAPIError
from service.eligibility import STATUS_OPTIONS
from view import body_interactions, sidebar_interactions, store, style, table_interactions
from view.navigation import APP_TITLE, PAGE_LABELS, app_header
from view.plotly_charts import mount_bar_gradients

st.set_page_config(page_title=APP_TITLE, page_icon=":material/shield:", layout="wide")

st.session_state.is_admin = False  # 배포 사본은 고객 조회 전용. 로컬 관리자 코드는 포함하지 않는다.


pages = {
    "": [
        st.Page("app_pages/home.py", title="FRONTLINE DATA", icon=":material/home:", default=True),
        st.Page("app_pages/notices.py", title=PAGE_LABELS["notices"], icon=":material/campaign:", url_path="notices"),
        st.Page("app_pages/item.py", title=PAGE_LABELS["item"], icon=":material/insights:", url_path="item"),
        st.Page("app_pages/overview.py", title=PAGE_LABELS["overview"], icon=":material/dashboard:", url_path="overview"),
        st.Page("app_pages/favorites.py", title=PAGE_LABELS["favorites"], icon=":material/star:", url_path="favorites"),
    ],
    "안내": [st.Page("app_pages/institutions.py", title="국방 기관·선정 기준",
                    icon=":material/policy:", url_path="institutions"),
             st.Page("app_pages/category_criteria.py", title="분류명 매칭 기준",
                     icon=":material/rule:", url_path="category-criteria")],
}
page = st.navigation(pages, position="hidden")

# 홈은 DB 조회·검색 위젯·관리자 진입·공통 헤더 없이 독립적으로 표시한다.
if page.url_path == "":
    page.run()
    st.stop()

style.apply(page.title)  # 화면별 색 전환 없이 같은 브랜드·사이드바 구조를 유지한다.
sidebar_interactions.mount()
table_interactions.mount()
body_interactions.mount(page.url_path)
app_header(pages[""][1:], page)
# 화면별 필터 자리(view.widgets.filter_area)와 관리자 버튼·브라우저 저장을 page.run() 전에 그린다.
# 그래야 화면이 st.stop()으로 멈춰도(예: 조달 유형 미선택) 빠지지 않는다.
st.session_state._filter_slot = st.sidebar.container(key="sidebar_filter_body")
st.session_state._sidebar_actions_slot = st.sidebar.container(key="sidebar_actions", gap="xsmall")

with st.session_state._filter_slot:
    # 회사 선택지는 해당 화면에서 읽는다. 환경 복원 때문에 전체 공고 조회를 선행하지 않는다.
    store.mount({"nt_when": store.WHEN_OPTIONS,
                 "nt_types": data.TYPES, "nt_agency_role": ["수요기관", "공고기관"],
                 "nt_scope": store.SCOPE_OPTIONS})

if page.url_path in {"item", "overview"}:
    mount_bar_gradients()
with st.container(key="dashboard_page_content"):
    try:
        page.run()
    except DataAPIError as exc:
        st.error(str(exc))
