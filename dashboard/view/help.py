"""포인터가 벗어나면 닫히고 화면에서 하나만 열리는 설명 아이콘."""

import streamlit as st

_CSS = """
button {font:inherit;font-weight:600;font-size:.85rem;color:var(--st-text-color);background:transparent;border:1px solid var(--st-border-color);border-radius:50%;width:22px;height:22px;cursor:help;padding:0;}
button:focus-visible {outline:2px solid var(--st-primary-color);outline-offset:2px;}
aside {position:fixed;inset:auto;margin:0;z-index:999999;box-sizing:border-box;max-width:calc(100vw - 24px);max-height:calc(100dvh - 24px);overflow:auto;padding:.65rem .8rem;border:1px solid var(--st-border-color);border-radius:var(--st-base-radius);background:var(--st-secondary-background-color);color:var(--st-text-color);font:14px/1.5 var(--st-font);box-shadow:0 3px 10px #0002;pointer-events:none;white-space:pre-line;word-break:keep-all;overflow-wrap:anywhere;}
[hidden] {display:none!important;}
"""
_JS = """
export default function ({parentElement,data}) {
  const button=parentElement.querySelector('button'),tip=parentElement.querySelector('aside');
  button.setAttribute('aria-label',data.label+' 설명');tip.textContent=data.text;
  button.textContent=data.symbol??'?';
  const floating=typeof tip.showPopover==='function' && typeof tip.hidePopover==='function';
  // CCv2의 containing block 밖에 띄워 viewport 좌표와 실제 위치를 일치시킨다.
  if(!floating)button.title=data.text;
  function close(){
    if(floating && tip.matches(':popover-open'))tip.hidePopover();
    tip.hidden=true;button.removeAttribute('aria-describedby');
  }
  function open(){
    if(!floating)return;
    window.dispatchEvent(new CustomEvent('frontline-help-open',{detail:data.id}));
    tip.hidden=false;tip.id='help-'+data.id;button.setAttribute('aria-describedby',tip.id);
    const r=button.getBoundingClientRect(),width=Math.max(1,Math.min(300,window.innerWidth-24));
    tip.style.width=width+'px';tip.style.left=Math.max(12,Math.min(r.left,window.innerWidth-width-12))+'px';
    if(!tip.matches(':popover-open'))tip.showPopover();
    const height=tip.getBoundingClientRect().height;
    const preferred=r.bottom+8+height<=window.innerHeight-12 ? r.bottom+8 : r.top-height-8;
    tip.style.top=Math.max(12,Math.min(preferred,window.innerHeight-height-12))+'px';
  }
  const other=e=>{if(e.detail!==data.id)close();};
  const escape=e=>{if(e.key==='Escape')close();};
  button.onpointerenter=open;button.onpointerleave=close;button.onfocus=open;button.onblur=close;
  button.onclick=open;button.onkeydown=escape;
  window.addEventListener('frontline-help-open',other);document.addEventListener('scroll',close,true);
  window.addEventListener('resize',close);
  return ()=>{close();window.removeEventListener('frontline-help-open',other);document.removeEventListener('scroll',close,true);window.removeEventListener('resize',close);};
}
"""

_HELP_COMPONENT = None
_HELP_RUNTIME = None


def _component():
    """등록은 runtime당 한 번. AppTest가 새 runtime을 만드는 경우도 분리한다."""
    from streamlit.runtime import Runtime
    global _HELP_COMPONENT, _HELP_RUNTIME
    runtime = Runtime.instance() if Runtime.exists() else None
    if _HELP_COMPONENT is None or runtime is not _HELP_RUNTIME:
        _HELP_COMPONENT = st.components.v2.component(
            "frontline_help",
            html="<button type='button'>?</button><aside role='tooltip' popover='manual' hidden></aside>",
            css=_CSS, js=_JS,
        )
        _HELP_RUNTIME = runtime
    return _HELP_COMPONENT


def help_label(label: str, text: str, *, key: str, color: str | None = None):
    with st.container(horizontal=True, gap="xxsmall", vertical_alignment="center", key=f"label_{key}"):
        st.markdown(f":{color}[{label}]" if color else label, width="stretch")
        help_icon(label, text, key=key)


def help_icon(label: str, text: str, *, key: str, symbol: str = "?"):
    """단독 설명 아이콘. hover·포커스·탭 지원, 동시에 하나만 표시한다."""
    _component()(key=key, data={"label": label, "text": text, "id": key, "symbol": symbol}, width=28, height=28)
