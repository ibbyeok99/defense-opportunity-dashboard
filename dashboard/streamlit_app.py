"""국방조달 기회 찾기(프로토타입).

실행: dashboard 폴더에서 `streamlit run streamlit_app.py`
(설정 `.streamlit/config.toml`·비밀값 `.streamlit/secrets.toml`을 이 폴더에서 읽는다)

사이드바: 화면별 필터(각 화면이 그림, 내 회사 조건은 공고 화면만). 관리자 버튼은 본문 맨 아래 아주 작게.
"""

import hmac

import streamlit as st

from service import data
from service import admin_access
from service.api_transport import DataAPIError
from service.eligibility import STATUS_OPTIONS
from view import body_interactions, sidebar_interactions, store, style, table_interactions
from view.navigation import APP_TITLE, PAGE_LABELS, app_header
from view.plotly_charts import mount_bar_gradients
from view.loading import loading
from view.favorites import maintain_favorites
from service import queries
from service.notice_requirements import poll_detail_evidence
from service.filters import Profile

st.set_page_config(page_title=APP_TITLE, page_icon=":material/shield:", layout="wide")

if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# API 모드는 서명된 계정의 권한을 매 실행 확인한다. 임의 세션 플래그로 승격하지 않는다.
if data.SOURCE == "api":
    verified_admin = admin_access.authorized()
    st.session_state.is_admin = verified_admin


def admin_password() -> str | None:
    try:
        return st.secrets["admin"]["password"]
    except (KeyError, FileNotFoundError):
        return None


def _close_login():
    st.session_state.show_login = False


@st.dialog("관리자 로그인", width="small", on_dismiss=_close_login)
def admin_login():
    if data.SOURCE == 'api':
        if not admin_access.login_ready():
            st.info('관리자 계정 로그인이 설정되지 않았습니다. 배포 설정의 OIDC와 관리자 계정 목록을 확인하세요.')
            return
        if st.user.is_logged_in:
            st.warning('이 계정에는 관리자 권한이 없습니다.')
            if st.button('다른 계정으로 로그인', key='admin_oidc_retry'):
                st.logout()
        elif st.button('관리자 계정으로 로그인', type='primary', key='admin_oidc_login'):
            provider = admin_access.config().get('provider')
            st.login(provider) if provider else st.login()
        return
    expected = admin_password()
    if expected is None:
        st.caption("`.streamlit/secrets.toml`에 `[admin] password`를 넣으면 켜집니다.")
        return
    with st.form("admin_login", border=False):
        pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("들어가기", type="primary", width="stretch"):
            if hmac.compare_digest(pw, expected):
                st.session_state.is_admin = True
                st.session_state.show_login = False
                st.rerun()
            st.error("비밀번호가 맞지 않습니다.")


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
# 데이터 기준·프로토타입 안내는 고객에게 필요 없는 정보라 관리자에게만 보인다(사용자 피드백 2026-09-28).
if st.session_state.is_admin:
    pages["관리"] = [st.Page("app_pages/admin.py", title="관리자", icon=":material/admin_panel_settings:"),
                   st.Page("app_pages/quality.py", title="데이터 기준", icon=":material/verified:")]
page = st.navigation(pages, position="hidden")

# 홈은 DB 조회·검색 위젯·관리자 진입·공통 헤더 없이 독립적으로 표시한다.
# 로그인 쿠키가 있는 새 세션도 홈 주소를 유지하며, 공고 진입은 홈 버튼으로 선택한다.
if page.url_path == "":
    page.run()
    st.stop()

style.apply(page.title)  # 화면별 색 전환 없이 같은 브랜드·사이드바 구조를 유지한다.
sidebar_interactions.mount()
table_interactions.mount()
body_interactions.mount(page.url_path)
app_header(pages[""][1:] + pages.get("관리", []), page)
# 화면별 필터 자리(view.widgets.filter_area)와 관리자 버튼·브라우저 저장을 page.run() 전에 그린다.
# 그래야 화면이 st.stop()으로 멈춰도(예: 조달 유형 미선택) 빠지지 않는다.
st.session_state._filter_slot = st.sidebar.container(key="sidebar_filter_body")
st.session_state._sidebar_actions_slot = st.sidebar.container(key="sidebar_actions", gap="xsmall")

# 관리자 버튼: 고객 눈에 띄지 않게 본문 맨 아래 아주 작게(사용자 지시 2026-09-29).
# 먼저 그리지만 CSS(order)로 본문 맨 끝에 놓인다(view/style.py `admin_foot`).
with st.container(key="admin_foot"):
    if st.session_state.is_admin:
        if st.button("관리자 나가기", type="tertiary", key="admin_out"):
            st.session_state.is_admin = False
            st.session_state.show_login = False
            if data.SOURCE == 'api':
                st.logout()
            st.rerun()
    else:
        if st.button("관리", type="tertiary", key="admin_in"):
            st.session_state.show_login = True
        if st.session_state.get("show_login"):
            admin_login()

with st.session_state._filter_slot:
    # 회사 선택지는 해당 화면에서 읽는다. 환경 복원 때문에 전체 공고 조회를 선행하지 않는다.
    store.mount({"nt_when": store.WHEN_OPTIONS,
                 "nt_types": data.TYPES, "nt_agency_role": ["수요기관", "공고기관"],
                 "nt_scope": store.SCOPE_OPTIONS})

# ☆ 저장 시 잡아 둔 원본 행만 확인한다. 저장하지 않은 목록 전체는 조회하지 않는다.
if store.favorites():
    maintain_favorites(lambda rows: queries.favorite_requirement_rows(rows, poll_detail_evidence),
                       comparison_reader=lambda rows: queries.favorite_company_statuses(rows, Profile(
                           tuple(st.session_state.get('pf_region') or ()),
                           tuple(st.session_state.get('pf_licenses') or ()))))

if page.url_path in {"item", "overview"}:
    mount_bar_gradients()
with st.container(key="dashboard_page_content"):
    # st.stop()/빈 결과에서도 본문 최소 길이와 하단 관리자 위치를 유지한다.
    try:
        with loading('화면 자료를 불러오는 중…'):
            page.run()
    except DataAPIError as exc:
        st.error(str(exc))
