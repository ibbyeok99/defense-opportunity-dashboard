"""브라우저별 즐겨찾기와 최대 4개 공고 비교. DB·대장에는 쓰지 않는다."""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

from service import data, queries
from view.comparison import render_comparison
from service.filters import Profile
from service.eligibility import STATUS_OPTIONS
from view import store
from view.navigation import page_header
from view.notice_detail import show_detail
from view.fmt import STATUS_COLORS

page_header("favorites")
regions = st.session_state.get("pf_region") or []
regions = [regions] if isinstance(regions, str) else regions
profile = Profile(tuple(regions), tuple(st.session_state.get("pf_licenses") or []))
ids = store.favorites()
st.caption(f"즐겨찾기 {len(ids)}/10개 · 같은 접속 주소·브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.")
if not ids:
    st.info("공고 목록이나 상세 화면의 ☆ 버튼으로 공고를 저장하세요.", icon=":material/star:")
    st.page_link("app_pages/notices.py", label="국방 입찰공고 찾기", icon=":material/campaign:")
    st.stop()

notices = data.notices().drop_duplicates("notice_id").set_index("notice_id")
available = [i for i in ids if i in notices.index]
for notice_id in ids:
    n = notices.loc[notice_id] if notice_id in notices.index else None
    with st.container(border=True, key=f"card_favorite_{ids.index(notice_id)}"):
        with st.container(horizontal=True, vertical_alignment="center"):
            with st.container(width="stretch"):
                st.markdown(f"**{n['notice_name']}**" if n is not None else "현재 데이터에서 찾을 수 없는 공고")
                st.caption(f"{n['procurement_type']} · {n['demand_agency_name']}" if n is not None else notice_id)
            st.button("해제", icon=":material/star:", key=f"fav_remove_{notice_id}",
                      on_click=store.toggle_favorite, args=(notice_id,))
            if n is not None:
                st.button("상세 보기", icon=":material/open_in_new:", key=f"fav_detail_{notice_id}",
                          on_click=lambda value: st.session_state.update(favorite_detail=value), args=(notice_id,))

if st.session_state.get("favorite_detail"):
    detail = queries.notice_detail(st.session_state.pop("favorite_detail"), profile)
    if detail is not None:
        show_detail(detail, datetime.now(ZoneInfo("Asia/Seoul")).date(),
                    dict(zip(STATUS_OPTIONS, STATUS_COLORS)).get(detail["status"], "gray"))

st.subheader("공고 비교", anchor=False)
old = st.session_state.get("fav_compare", [])
if any(i not in available for i in old):
    st.session_state.fav_compare = [i for i in old if i in available][:4]
selected = st.multiselect("비교할 공고 (최대 4개)", available, key="fav_compare", max_selections=4,
                          format_func=lambda i: f"{notices.loc[i, 'notice_name']} · {i}", placeholder="공고를 선택하세요")
if len(selected) < 2:
    st.caption("2~4개를 선택하면 마감·기관·면허·지역 조건과 분류 과거 경쟁 지표를 비교합니다.")
else:
    details = [queries.notice_detail(i, profile) for i in selected]
    render_comparison([d for d in details if d is not None], datetime.now(ZoneInfo("Asia/Seoul")).date(),
                      on_detail=lambda value: st.session_state.update(favorite_detail=value))
