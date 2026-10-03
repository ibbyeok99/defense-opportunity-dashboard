"""즐겨찾기 목록/비교의 독립 갱신. 조회는 전달받은 callback으로만 요청한다."""
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from view import store
from view.comparison import render_comparison
from view.fmt import notice_requirement_summary, notice_identifier


def _needs(row, kind):
    return row[kind + '_state'] == '미확인' or row.get(kind + '_requires_review', False)


@st.fragment(run_every='2s')
def render_favorites(base_rows, *, requirement_reader, detail_builder):
    ids = store.favorites()
    st.caption(f"즐겨찾기 {len(ids)}/10개 · 같은 접속 주소·브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.")
    if not ids:
        st.info("공고 목록이나 상세 화면의 ☆ 버튼으로 공고를 저장하세요.", icon=':material/star:')
        st.page_link('app_pages/notices.py', label='국방 입찰공고 찾기', icon=':material/campaign:')
        return
    selected_rows = base_rows[base_rows.notice_id.isin(ids)]
    rows, snapshots = requirement_reader(selected_rows)
    notices = rows.set_index('notice_id', drop=False)
    available = [i for i in ids if i in notices.index]
    for notice_id in ids:
        n = notices.loc[notice_id] if notice_id in notices.index else None
        with st.container(border=True, key=f'card_favorite_{ids.index(notice_id)}'):
            with st.container(horizontal=True, vertical_alignment='center'):
                with st.container(width='stretch'):
                    st.markdown(f"**{n['notice_name']}**" if n is not None else '현재 데이터에서 찾을 수 없는 공고')
                    st.caption(f"{n['procurement_type']} · {n['demand_agency_name']} · {notice_identifier(n)}" if n is not None else notice_id)
                st.button('해제', icon=':material/star:', key=f'fav_remove_{notice_id}',
                          on_click=store.toggle_favorite, args=(notice_id,))
                if n is not None and st.button('상세 보기', icon=':material/open_in_new:', key=f'fav_detail_{notice_id}'):
                    st.session_state.favorite_detail = notice_id
                    st.rerun()
            if n is not None:
                snapshot = snapshots[notice_id]
                summary = notice_requirement_summary(n.license_state, n.license_values, n.region_state, n.region_values,
                    license_review=n.get('license_review_status', '미조회'), region_review=n.get('region_review_status', '미조회'))
                lines = summary.split(' | ')
                if snapshot['phase'] == 'running':
                    lines = [('찾는 중… · ' + line if _needs(n, kind) else line)
                             for kind, line in zip(('license', 'region'), lines)]
                for line in lines:
                    st.caption(line)
                if snapshot['phase'] in {'failed', 'unavailable', 'busy'}:
                    st.caption(snapshot['message'])
    st.subheader('공고 비교', anchor=False)
    old = st.session_state.get('fav_compare', [])
    if any(i not in available for i in old):
        st.session_state.fav_compare = [i for i in old if i in available][:4]
    compared = st.multiselect('비교할 공고 (최대 4개)', available, key='fav_compare', max_selections=4,
        format_func=lambda i: f"{notices.loc[i, 'notice_name']} · {i}", placeholder='공고를 선택하세요')
    if len(compared) < 2:
        st.caption('2~4개를 선택하면 마감·기관·면허·지역 조건과 분류 과거 경쟁 지표를 비교합니다.')
    else:
        details = [detail_builder(notices.loc[i]) for i in compared]
        for det in details:
            n = det['notice']
            if snapshots[n.notice_id]['phase'] == 'running':
                for index, kind in enumerate(('license', 'region')):
                    if _needs(n, kind):
                        det['conditions'].at[index, '요구 조건'] = '찾는 중… · ' + det['conditions'].at[index, '요구 조건']
        render_comparison(details, datetime.now(ZoneInfo('Asia/Seoul')).date(),
                          on_detail=lambda value: st.session_state.update(favorite_detail=value))
    # 비교 아이콘 callback은 fragment만 다시 그린다. 상세 요청은 전체 실행으로 전달한다.
    if st.session_state.get('favorite_detail'):
        st.rerun()
