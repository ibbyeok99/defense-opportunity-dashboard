"""Native 표의 컬럼 설정 메뉴 접근만 차단한다.

Streamlit 1.64에는 컬럼 메뉴 비활성화 공개 옵션이 없다.
canvas 헤더/본문은 건드리지 않고 메뉴만 숨기고 inert로 만든다.
Streamlit 업그레이드 시 test-id와 실제 메뉴 접근을 브라우저에서 재검증한다.
"""

import streamlit as st


MENU_SELECTOR = '[data-testid="stDataFrameColumnMenu"]'
_JS = """
export default function ({parentElement}) {
  // 앱 전체 표와 dialog 안 표를 함께 보호하는 의도적인 document 범위 보정.
  const doc = parentElement.ownerDocument;
  const selector = '[data-testid="stDataFrameColumnMenu"]';
  const saved = new Map();
  const lock = menu => {
    if (saved.has(menu)) return;
    saved.set(menu, {inert: menu.inert, hidden: menu.getAttribute('aria-hidden')});
    menu.inert = true;
    menu.setAttribute('aria-hidden', 'true');
    if (menu.contains(doc.activeElement)) doc.activeElement.blur();
  };
  const scan = node => {
    if (!(node instanceof Element)) return;
    if (node.matches(selector)) lock(node);
    node.querySelectorAll(selector).forEach(lock);
  };
  scan(doc.body);
  const observer = new MutationObserver(records => {
    records.forEach(record => record.addedNodes.forEach(scan));
    for (const menu of saved.keys()) if (!menu.isConnected) saved.delete(menu);
  });
  observer.observe(doc.body, {childList: true, subtree: true});
  return () => {
    observer.disconnect();
    for (const [menu, original] of saved) {
      menu.inert = original.inert;
      if (original.hidden === null) menu.removeAttribute('aria-hidden');
      else menu.setAttribute('aria-hidden', original.hidden);
    }
  };
}
"""


def mount():
    # AppTest가 실행마다 등록부를 초기화하므로 기존 앱 보정 component와 같은 등록 방식.
    guard = st.components.v2.component(
        "frontline_table_menu_guard", html="<span></span>", js=_JS,
    )
    guard(key="table_menu_guard", height=0)
