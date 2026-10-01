"""포인터가 벗어나면 닫히고 화면에서 하나만 열리는 설명 아이콘."""

import streamlit as st

_CSS = """
button {font:inherit;font-weight:600;font-size:.85rem;color:var(--st-text-color);background:transparent;border:1px solid var(--st-border-color);border-radius:50%;width:22px;height:22px;cursor:help;padding:0;}
button:focus-visible {outline:2px solid var(--st-primary-color);outline-offset:2px;}
aside {position:fixed;z-index:999999;box-sizing:border-box;padding:.65rem .8rem;border:1px solid var(--st-border-color);border-radius:var(--st-base-radius);background:var(--st-secondary-background-color);color:var(--st-text-color);font:14px/1.5 var(--st-font);box-shadow:0 3px 10px #0002;pointer-events:none;white-space:pre-line;word-break:keep-all;overflow-wrap:anywhere;}
[hidden] {display:none!important;}
"""
_JS = """
export default function ({parentElement,data}) {
  const button=parentElement.querySelector('button'),tip=parentElement.querySelector('aside');
  button.setAttribute('aria-label',data.label+' 설명');tip.textContent=data.text;
  button.textContent=data.symbol??'?';
  function close(){tip.hidden=true;button.removeAttribute('aria-describedby');}
  function open(){
    window.dispatchEvent(new CustomEvent('frontline-help-open',{detail:data.id}));
    tip.hidden=false;tip.id='help-'+data.id;button.setAttribute('aria-describedby',tip.id);
    const r=button.getBoundingClientRect(),width=Math.min(300,window.innerWidth-24);
    tip.style.width=width+'px';tip.style.left=Math.max(12,Math.min(r.left,window.innerWidth-width-12))+'px';
    tip.style.top=Math.min(r.bottom+8,window.innerHeight-tip.offsetHeight-12)+'px';
  }
  const other=e=>{if(e.detail!==data.id)close();};
  const escape=e=>{if(e.key==='Escape')close();};
  button.onpointerenter=open;button.onpointerleave=close;button.onfocus=open;button.onblur=close;
  button.onclick=open;button.onkeydown=escape;
  window.addEventListener('frontline-help-open',other);document.addEventListener('scroll',close,true);
  return ()=>{window.removeEventListener('frontline-help-open',other);document.removeEventListener('scroll',close,true);};
}
"""


def help_label(label: str, text: str, *, key: str, color: str | None = None):
    with st.container(horizontal=True, gap="xxsmall", vertical_alignment="center", key=f"label_{key}"):
        st.markdown(f":{color}[{label}]" if color else label, width="stretch")
        help_icon(label, text, key=key)


def help_icon(label: str, text: str, *, key: str, symbol: str = "?"):
    """단독 설명 아이콘. hover·포커스·탭 지원, 동시에 하나만 표시한다."""
    component = st.components.v2.component("frontline_help", html="<button type='button'>?</button><aside role='tooltip' hidden></aside>",
                                          css=_CSS, js=_JS)
    component(key=key, data={"label": label, "text": text, "id": key, "symbol": symbol}, width=28, height=28)
