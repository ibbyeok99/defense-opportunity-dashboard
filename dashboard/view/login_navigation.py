"""Codex, 2026-10-05: Google 로그인 전 페이지를 같은 탭에서 한 번만 복원한다."""

import re
import time
import uuid

import streamlit as st

RETURN_PAGES = {
    name: f'app_pages/{filename}.py'
    for name, filename in (
        ('notices', 'notices'), ('item', 'item'), ('overview', 'overview'),
        ('favorites', 'favorites'), ('institutions', 'institutions'),
        ('category-criteria', 'category_criteria'),
    )
}
STORAGE_KEY = 'frontline_login_return_v1'
MAX_AGE_MS = 15 * 60 * 1000

_JS = r"""
export default function(component) {
  const {data, setTriggerValue} = component;
  const sent = window.__frontlineLoginNavigation || (window.__frontlineLoginNavigation = {});
  const operation = data.mode + ':' + data.request;
  if (sent[operation]) return;
  sent[operation] = true;
  if (data.mode === 'save') {
    let saved = false;
    try {
      window.sessionStorage.setItem(data.storage_key, JSON.stringify(data.record));
      saved = true;
    } catch (error) {}
    setTriggerValue('ready', {request: data.request, saved});
    return;
  }
  let record = null;
  try {
    const raw = window.sessionStorage.getItem(data.storage_key);
    // 같은 탭에서 시작한 로그인 한 번에만 쓰고 일반 홈 접속 때는 남기지 않는다.
    window.sessionStorage.removeItem(data.storage_key);
    if (raw !== null) record = JSON.parse(raw);
  } catch (error) {}
  setTriggerValue('returned', {read: true, record});
}
"""


def _component(**kwargs):
    component = st.components.v2.component(
        'frontline_login_navigation', html='<span></span>', js=_JS)
    return component(height=0, **kwargs)


def request_login(page):
    """인증 시작 버튼을 누른 경우에만 복귀 표식을 준비한다. 권한 정보는 저장하지 않는다."""
    if page not in RETURN_PAGES:
        raise ValueError('로그인 복귀 대상 페이지가 아닙니다.')
    st.session_state['_login_navigation_request'] = {
        'page': page, 'request': uuid.uuid4().hex,
        'created_at': int(time.time() * 1000),
    }


def login_prepared():
    """브라우저 저장 완료를 확인한 뒤에만 OAuth를 시작해 이동 시점의 저장 경쟁을 막는다."""
    record = st.session_state.get('_login_navigation_request')
    if not record:
        return False
    result = _component(key='login_navigation_save', data={
        'mode': 'save', 'storage_key': STORAGE_KEY, 'request': record['request'], 'record': record,
    }, on_ready_change=lambda: None)
    ready = result.get('ready')
    if not isinstance(ready, dict) or ready.get('request') != record['request']:
        return False
    if not ready.get('saved'):
        st.info('브라우저 저장이 차단되어 로그인 후 홈으로 돌아갑니다.')
    st.session_state.pop('_login_navigation_request', None)
    return True


def return_page(record, *, now=None):
    """외부 URL·만료/미래 표식은 거부한다. 복귀 정보로 관리자 권한을 부여하지 않는다."""
    if (not isinstance(record, dict) or not isinstance(record.get('page'), str)
            or record['page'] not in RETURN_PAGES):
        return None
    created = record.get('created_at')
    request = record.get('request')
    if (type(created) is not int or not isinstance(request, str)
            or re.fullmatch(r'[0-9a-f]{32}', request) is None):
        return None
    now_ms = int(time.time() * 1000) if now is None else now
    if not 0 <= now_ms - created <= MAX_AGE_MS:
        return None
    return RETURN_PAGES[record['page']]


def restore_login_page(authorized):
    """실제 로그인 복귀 표식을 한 번 소비한다. 일반 홈 접속은 이동하지 않는다."""
    if st.session_state.get('_login_navigation_checked'):
        return
    request = st.session_state.setdefault('_login_navigation_read', uuid.uuid4().hex)
    result = _component(key='login_navigation_return', data={
        'mode': 'consume', 'storage_key': STORAGE_KEY, 'request': request,
    }, on_returned_change=lambda: None)
    returned = result.get('returned')
    if not isinstance(returned, dict) or returned.get('read') is not True:
        return
    st.session_state['_login_navigation_checked'] = True
    destination = return_page(returned.get('record'))
    if authorized and destination:
        st.switch_page(destination)
