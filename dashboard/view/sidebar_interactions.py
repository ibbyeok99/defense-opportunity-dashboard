"""사이드바 선택칸의 '열린 화살표를 다시 누르면 닫기' 보정.

설치된 Streamlit multiselect의 Open 버튼은 열기만 호출한다.
선택값을 수정하지 않고 native Escape 닫기를 전달한다. 버전 변경 시 브라우저 재검증 필요.
"""

import streamlit as st


_JS = """
export default function ({parentElement}) {
  // Native 위젯의 이벤트 보정만 필요하므로 document capture를 의도적으로 사용한다.
  const doc = parentElement.ownerDocument;
  const slot = '__frontlineSidebarDropdownGuard';
  doc[slot]?.dispose();
  let closingButton = null;
  const arrow = target => target instanceof Element
    ? target.closest('[data-testid="stSidebar"] [data-testid="stMultiSelect"] button[aria-label="Open"]')
    : null;
  const close = (event, button) => {
    const box = button?.closest('[data-testid="stMultiSelect"]');
    const input = box?.querySelector('input[role="combobox"]');
    if (!input || input.getAttribute('aria-expanded') !== 'true') return false;
    event.preventDefault();
    event.stopImmediatePropagation();
    input.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Escape', code: 'Escape', bubbles: true, cancelable: true
    }));
    return true;
  };
  const down = event => {
    closingButton = null;
    const button = arrow(event.target);
    if (button && close(event, button)) closingButton = button;
  };
  const finish = event => {
    if (!closingButton) return;
    // 뒤이어 오는 pointerup/click에서 native 열기 콜백이 재실행되지 않도록 한다.
    if (arrow(event.target) === closingButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
    if (event.type === 'click' || event.type === 'pointercancel') closingButton = null;
  };
  const keyboard = event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const button = arrow(event.target);
    if (button) close(event, button);
  };
  doc.addEventListener('pointerdown', down, true);
  doc.addEventListener('pointerup', finish, true);
  doc.addEventListener('pointercancel', finish, true);
  doc.addEventListener('click', finish, true);
  doc.addEventListener('keydown', keyboard, true);
  const dispose = () => {
    doc.removeEventListener('pointerdown', down, true);
    doc.removeEventListener('pointerup', finish, true);
    doc.removeEventListener('pointercancel', finish, true);
    doc.removeEventListener('click', finish, true);
    doc.removeEventListener('keydown', keyboard, true);
  };
  const installed = {dispose};
  doc[slot] = installed;
  return () => {
    // 필터 선택으로 rerun할 때도 기존 위젯을 누를 수 있어 보정을 끊지 않는다.
    // 실제 unmount이면 정리하고, 새 render는 위에서 기존 등록을 먼저 교체한다.
    queueMicrotask(() => {
      if (!parentElement.isConnected && doc[slot] === installed) {
        dispose();
        delete doc[slot];
      }
    });
  };
}
"""


def mount():
    # AppTest는 실행 사이 component 등록부를 초기화하므로 기존 store와 같은 등록 방식.
    guard = st.components.v2.component("frontline_sidebar_dropdown_guard", html="<span></span>", js=_JS)
    guard(key="sidebar_dropdown_guard", height=0)
