"""즐겨찾기 목록/비교의 독립 갱신. 조회는 전달받은 callback으로만 요청한다."""
from datetime import datetime
from time import monotonic
from zoneinfo import ZoneInfo

import streamlit as st
from view import store
from view.comparison import render_comparison
from view.fmt import notice_identifier
from view.favorite_conditions import deadline_text, requirement_lines


def saved_preview():
    """DB를 기다리기 전에 브라우저 표시 사본을 보여준다. 회사 판단에는 사용하지 않는다."""
    records = store.favorite_snapshots()
    if not records:
        return
    st.caption('저장된 공고를 먼저 표시합니다. 최신 공고·조건은 확인 중…')
    for notice_id, record in records.items():
        row = record['row']
        with st.container(border=True):
            st.text(row.get('notice_name') or notice_id)
            st.caption(f"{row.get('procurement_type', '')} · {row.get('demand_agency_name', '')}")
            st.caption(deadline_text(row))
            for line in requirement_lines(row):
                st.caption(line)  # 브라우저 표시 사본만으로 충족을 판단하지 않는다.


@st.fragment(run_every='2s')
def maintain_favorites(requirement_reader, comparison_reader=None):
    """어느 탭에 있어도 추가 시 제출한 작업을 확인하고 완료 사본을 브라우저에 반영한다."""
    import pandas as pd
    ids = store.favorites()
    sources = st.session_state.get('_favorite_request_sources', {})
    current = [sources[i] for i in ids if i in sources]
    if current:
        updated, snapshots = requirement_reader(pd.DataFrame(current))
        for row in updated.to_dict('records'):
            if snapshots.get(row['notice_id'], {}).get('phase') == 'done' or row['notice_id'] not in store.favorite_snapshots():
                store.remember_favorite(row)
        st.session_state['_favorite_save_progress'] = snapshots
        if comparison_reader:
            st.session_state['_favorite_company_comparisons'] = comparison_reader(updated)
    # 메인 mount 뒤에 완료 결과가 바뀌어도 fragment만으로 localStorage에 전달한다.
    store.mount({}, key='_browser_store_updates')


def _needs(row, kind):
    return row[kind + '_state'] == '미확인' or row.get(kind + '_requires_review', False)


@st.fragment(run_every='2s')
def render_favorites(base_rows, *, requirement_reader, detail_builder, competition_loader=None):
    ids = store.favorites()
    # 해제 callback은 이 fragment만 실행한다. 빈 목록도 타이머를 기다리지 않고 저장한다.
    store.mount({}, key='_favorite_page_updates')
    st.caption(f"즐겨찾기 {len(ids)}/10개 · 같은 접속 주소·브라우저에 저장됩니다. 다른 기기와 동기화되지 않습니다.")
    if not ids:
        st.info("공고 목록이나 상세 화면의 ☆ 버튼으로 공고를 저장하세요.", icon=':material/star:')
        st.page_link('app_pages/notices.py', label='국방 입찰공고 찾기', icon=':material/campaign:')
        return
    selected_rows = base_rows[base_rows.notice_id.isin(ids)]
    request_rows = selected_rows.copy(deep=True)
    # 저장값과 회사 비교를 먼저 그린다. 느린 확인 요청은 아래에서 시작하고 다음 fragment 갱신에 반영한다.
    saved_snapshots = st.session_state.setdefault('_favorite_requirement_snapshots', {})
    result_key = '_favorite_requirement_rows'
    cached_rows = st.session_state.get(result_key)
    cached_base = st.session_state.get('_favorite_base_rows')
    valid_ids = []
    if cached_rows is not None and cached_base is not None:
        from pandas import concat
        old_base = cached_base.set_index('notice_id')
        valid_ids = [r.notice_id for _, r in selected_rows.iterrows()
                     if r.notice_id in old_base.index and r.drop('notice_id').equals(old_base.loc[r.notice_id])]
        cached_rows = cached_rows[cached_rows.notice_id.isin(valid_ids)]
        fresh_ids = selected_rows.notice_id[~selected_rows.notice_id.isin(cached_rows.notice_id)]
        selected_rows = concat([cached_rows, selected_rows[selected_rows.notice_id.isin(fresh_ids)]], ignore_index=True)
    def initial_snapshot(notice_id):
        matches = request_rows[request_rows.notice_id.eq(notice_id)]
        evidence = matches.iloc[0].get('requirement_evidence') if len(matches) else None
        if isinstance(evidence, dict) and not evidence.get('api_only'):
            return {'phase': 'done', 'message': '저장된 확인 결과'}
        return {'phase': 'running', 'message': '확인 요청 준비 중…'}
    snapshots = {i: saved_snapshots.get(i, initial_snapshot(i)) if i in valid_ids else initial_snapshot(i) for i in ids}
    rows = selected_rows
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
                det = detail_builder(n)
                st.caption(deadline_text(n))
                for line in requirement_lines(n, det):
                    st.caption(line)
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
        if competition_loader:
            stats_cache = st.session_state.setdefault('_favorite_competition', {})
            for det in details:
                code = det['notice']['item_code']
                cached = stats_cache.get(code, {})
                if not cached or monotonic() - cached['checked_at'] >= 3600:
                    stats_cache[code] = {'checked_at': monotonic(), 'result': competition_loader(code)}
                    while len(stats_cache) > 32:
                        oldest = min(stats_cache, key=lambda value: stats_cache[value]['checked_at'])
                        del stats_cache[oldest]
                det.update(stats_cache[code]['result'])
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
    if available:
        # 화면 캐시에 덧붙인 조건값으로 원본 식별 해시를 바꾸지 않는다.
        updated, current_snapshots = requirement_reader(request_rows)
        st.session_state[result_key] = updated
        st.session_state['_favorite_base_rows'] = request_rows
        st.session_state['_favorite_requirement_snapshots'] = current_snapshots
        for row in updated.to_dict('records'):
            if current_snapshots.get(row['notice_id'], {}).get('phase') == 'done' or row['notice_id'] not in store.favorite_snapshots():
                store.remember_favorite(row)
