"""본문 native 토글의 제목 위치 보존. 데이터/열림 상태/키보드 동작은 변경하지 않는다.

바닥 근처에서 접으면 스크롤 범위가 줄어 위치가 강제 보정된다.
현재 화면의 바닥까지만 임시 최소 높이를 예약하고, 위로 스크롤하면 회수한다.
Streamlit DOM 구조 변경 시 실행 화면을 재검증해야 한다.
"""

import streamlit as st


_JS = """
export default function ({parentElement, data}) {
  // Native 본문 토글을 보정하므로 ownerDocument 사용. sidebar/dialog는 대상 밖이다.
  const doc = parentElement.ownerDocument;
  const win = doc.defaultView;
  const slot = '__frontlineBodyScrollGuard';
  const previous = doc[slot];
  previous?.dispose(previous.page !== data.page);
  const main = doc.querySelector('[data-testid="stMain"]');
  if (!main) return;
  let body = null;
  let lastTop = main.scrollTop;
  let reserved = false;
  const property = '--frontline-body-scroll-floor';
  const locateBody = () => main.querySelector('.st-key-dashboard_page_content');
  const reserve = () => {
    body = locateBody();
    if (!body) return;
    // 본문 위 콘텐츠/헤더의 길이를 제외한 현재 viewport 바닥까지만 예약한다.
    const bodyTop = body.getBoundingClientRect().top - main.getBoundingClientRect().top;
    const floor = Math.max(0, Math.ceil(main.clientHeight - bodyTop));
    body.style.setProperty(property, `${floor}px`);
    reserved = true;
  };
  const beforeToggle = event => {
    const summary = event.target instanceof win.Element
      ? event.target.closest('.st-key-dashboard_page_content [data-testid="stExpander"] summary')
      : null;
    if (!summary || !main.contains(summary)) return;
    // 기본 click/Enter/Space 열기·접기를 막거나 강제 scrollTo하지 않는다.
    reserve();
    lastTop = main.scrollTop;
  };
  const scroll = () => {
    const next = main.scrollTop;
    if (reserved && next < lastTop) reserve();
    lastTop = next;
  };
  const resize = () => { if (reserved) reserve(); };
  main.addEventListener('click', beforeToggle, true);
  main.addEventListener('scroll', scroll, {passive: true});
  win.addEventListener('resize', resize);
  const dispose = (clear = true) => {
    main.removeEventListener('click', beforeToggle, true);
    main.removeEventListener('scroll', scroll);
    win.removeEventListener('resize', resize);
    if (clear) (body || locateBody())?.style.removeProperty(property);
  };
  // 같은 페이지 rerun은 높이 보정을 유지하고, 페이지 이동/unmount는 회수한다.
  body = locateBody();
  reserved = !!body?.style.getPropertyValue(property);
  const installed = {dispose, page: data.page};
  doc[slot] = installed;
  return () => queueMicrotask(() => {
    if (!parentElement.isConnected && doc[slot] === installed) {
      dispose();
      delete doc[slot];
    }
  });
}
"""


def mount(page: str):
    # AppTest의 실행별 component 등록부 초기화에 맞춰 기존 guard와 같은 방식으로 등록한다.
    guard = st.components.v2.component("frontline_body_scroll_guard", html="<span></span>", js=_JS)
    guard(key="body_scroll_guard", data={"page": page}, height=0)
