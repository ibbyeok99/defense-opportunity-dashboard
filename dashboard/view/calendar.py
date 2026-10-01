"""한글 기간 달력. 공개 CCv2 API로 날짜 선택만 전달하며 공고일 검색 의미는 유지한다."""

from datetime import date
from collections.abc import Mapping

import streamlit as st

_HTML = """
<section class="date-picker">
  <label id="period-label">공고 기간 (공고일 기준)</label>
  <button id="period-toggle" type="button" aria-expanded="false" aria-controls="calendar-panel"><span id="period-value"></span><span id="period-arrow" aria-hidden="true"></span></button>
  <div id="calendar-panel" popover="manual" hidden>
    <div class="calendar-actions"><strong>기간 선택</strong><button id="calendar-close" type="button" aria-label="달력 닫기">×</button></div>
    <div class="month-nav">
      <button id="previous-month" type="button" aria-label="이전 달">‹</button>
      <select id="calendar-year" aria-label="연도"></select>
      <select id="calendar-month" aria-label="월"></select>
      <button id="next-month" type="button" aria-label="다음 달">›</button>
    </div>
    <div class="weekdays" aria-hidden="true"><span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span></div>
    <div id="calendar-days" role="group" aria-label="날짜 선택"></div>
    <p id="calendar-status" aria-live="polite"></p>
    <button id="all-dates" type="button">전체 기간</button>
  </div>
</section>
"""

_CSS = """
.date-picker {font-family:var(--st-font);color:var(--st-text-color);font-size:.9rem;width:100%;min-width:0;box-sizing:border-box;}
*,*::before,*::after {box-sizing:border-box;}
label {display:block;margin-bottom:.5rem;}
button,select {font:inherit;color:inherit;border:1px solid var(--st-border-color);border-radius:var(--st-base-radius);background:var(--st-secondary-background-color);cursor:pointer;}
button {min-height:32px;}
button:focus-visible,select:focus-visible {outline:2px solid var(--st-primary-color);outline-offset:2px;}
#period-toggle {display:flex;align-items:center;justify-content:space-between;gap:4px;width:100%;text-align:left;padding:.5rem .45rem;min-height:40px;}
#period-value {font-size:.78rem;font-variant-numeric:tabular-nums;white-space:nowrap;}
#period-arrow {color:var(--st-primary-color);flex:0 0 auto;}
#calendar-panel {margin-top:.65rem;padding:.5rem 0 0;border:0;border-top:1px solid var(--st-border-color);}
#calendar-panel.floating {position:fixed;inset:auto;margin:0;width:min(280px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:auto;padding:14px;border:1px solid var(--st-border-color);border-radius:12px;background:var(--st-secondary-background-color);color:var(--st-text-color);box-shadow:0 12px 32px #0004;}
#calendar-panel.floating #calendar-days button {min-height:34px;}
[hidden] {display:none!important;}
.calendar-actions,.month-nav {display:flex;align-items:center;justify-content:space-between;gap:.25rem;margin-bottom:.5rem;}
.calendar-actions button {padding:0;width:28px;min-height:28px;border:0;background:transparent;font-size:1.15rem;}
.month-nav button {width:26px;flex-shrink:0;}
.month-nav select {min-width:0;padding:.25rem .1rem;font-size:.82rem;}
.weekdays,#calendar-days {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2px;text-align:center;}
.weekdays {font-size:.8rem;margin-bottom:.25rem;}
#calendar-days button {border-color:transparent;background:transparent;padding:0;min-width:0;min-height:30px;font-size:.85rem;border-radius:7px;}
#calendar-days button:hover:not(:disabled) {border-color:var(--st-primary-color);}
#calendar-days button.range {background:color-mix(in srgb,var(--st-primary-color) 18%,transparent);}
#calendar-days button.selected {border-color:var(--st-primary-color);color:var(--st-primary-color);font-weight:700;}
#calendar-days button:disabled {opacity:.3;cursor:default;}
#calendar-status {font-size:.78rem;line-height:1.4;margin:.6rem 0;}
#all-dates {width:100%;}
"""

_JS = """
export default function ({parentElement,data,setTriggerValue}) {
  const root=parentElement.querySelector('.date-picker');
  if(!root) return;
  const q=selector=>root.querySelector(selector);
  const toDate=s=>new Date(s+'T12:00:00');
  const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const incoming=JSON.stringify(data.dates);
  const state=root._calendarState??={signature:null,open:false,start:null,end:null,month:toDate(data.today)};
  if(state.signature!==incoming) {
    state.signature=incoming;
    state.start=data.dates[0]??null; state.end=data.dates[1]??null;
    state.month=toDate(state.end??state.start??data.today);
  }
  const panel=q('#calendar-panel'),toggle=q('#period-toggle'),years=q('#calendar-year'),months=q('#calendar-month');
  const floating=typeof panel.showPopover==='function';
  panel.classList.toggle('floating',floating);
  if(!floating)panel.removeAttribute('popover');
  q('#period-label').textContent=data.label;
  toggle.setAttribute('aria-label',data.label+' 달력 열기/닫기');
  years.replaceChildren(); months.replaceChildren();
  for(let y=Number(data.minimum.slice(0,4));y<=Number(data.maximum.slice(0,4));y++) {
    const opt=document.createElement('option');opt.value=y;opt.textContent=y+'년';years.append(opt);
  }
  for(let m=0;m<12;m++) {const opt=document.createElement('option');opt.value=m;opt.textContent=(m+1)+'월';months.append(opt);}
  function render() {
    panel.hidden=!state.open;toggle.setAttribute('aria-expanded',String(state.open));
    q('#period-value').textContent=data.dates.length?data.dates.map(d=>d.replaceAll('-','.')).join(' ~ '):'전체 기간';
    q('#period-arrow').textContent=state.open?'▴':'▾';
    years.value=state.month.getFullYear();months.value=state.month.getMonth();
    const y=state.month.getFullYear(),m=state.month.getMonth(),days=q('#calendar-days');days.replaceChildren();
    const first=new Date(y,m,1).getDay(),total=new Date(y,m+1,0).getDate();
    for(let i=0;i<first;i++) days.append(document.createElement('span'));
    for(let d=1;d<=total;d++) {
      const value=iso(new Date(y,m,d,12)),b=document.createElement('button');
      b.type='button';b.textContent=d;b.setAttribute('aria-label',`${y}년 ${m+1}월 ${d}일`);
      b.disabled=value<data.minimum||value>data.maximum;
      b.setAttribute('aria-pressed',String(value===state.start||value===state.end));
      if(value===state.start||value===state.end) b.classList.add('selected');
      if(state.start&&state.end&&state.start<=value&&value<=state.end) b.classList.add('range');
      b.onclick=()=>{
        if(!state.start||state.end) {state.start=value;state.end=null;render();return;}
        const ordered=[state.start,value].sort();state.start=ordered[0];state.end=ordered[1];state.open=false;
        render();toggle.focus();setTriggerValue('selected',ordered);
      };days.append(b);
    }
    q('#calendar-status').textContent=state.start&&!state.end?'시작일 '+state.start+' · 종료일을 선택하세요.':'시작일과 종료일을 차례로 선택하세요.';
    q('#previous-month').disabled=iso(new Date(y,m,1,12))<=data.minimum;
    q('#next-month').disabled=iso(new Date(y,m+1,1,12))>data.maximum;
    if(floating) {
      if(state.open&&!panel.matches(':popover-open'))panel.showPopover();
      if(!state.open&&panel.matches(':popover-open'))panel.hidePopover();
      if(state.open) {
        const r=toggle.getBoundingClientRect(),w=panel.offsetWidth,h=panel.offsetHeight;
        const below=r.bottom+8,above=r.top-h-8;
        const fitsBelow=below+h<=window.innerHeight-12,fitsAbove=above>=12;
        const beside=!fitsBelow&&!fitsAbove&&r.right+8+w<=window.innerWidth-12;
        const top=fitsBelow?below:fitsAbove?above:Math.max(12,Math.min(r.top,window.innerHeight-h-12));
        const left=beside?r.right+8:r.left;
        panel.style.left=Math.max(12,Math.min(left,window.innerWidth-w-12))+'px';
        panel.style.top=top+'px';
      }
    }
  }
  function close() {state.open=false;state.start=data.dates[0]??null;state.end=data.dates[1]??null;render();}
  toggle.onclick=()=>{if(state.open)close();else {state.open=true;render();}};
  q('#calendar-close').onclick=()=>{close();toggle.focus();};
  q('#previous-month').onclick=()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()-1,1,12);render();};
  q('#next-month').onclick=()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()+1,1,12);render();};
  years.onchange=()=>{state.month=new Date(Number(years.value),state.month.getMonth(),1,12);render();};
  months.onchange=()=>{state.month=new Date(state.month.getFullYear(),Number(months.value),1,12);render();};
  q('#all-dates').onclick=()=>{state.start=null;state.end=null;state.open=false;render();toggle.focus();setTriggerValue('selected',[]);};
  const outside=e=>{if(state.open&&!e.composedPath().includes(root))close();};
  const escape=e=>{if(e.key==='Escape'&&state.open){close();toggle.focus();}};
  const scroll=e=>{if(state.open&&!panel.contains(e.target))close();};
  const resize=()=>{if(state.open)close();};
  document.addEventListener('pointerdown',outside);root.addEventListener('keydown',escape);render();
  document.addEventListener('scroll',scroll,true);window.addEventListener('resize',resize);
  return ()=>{document.removeEventListener('pointerdown',outside);root.removeEventListener('keydown',escape);document.removeEventListener('scroll',scroll,true);window.removeEventListener('resize',resize);};
}
"""


def decode_period(values, minimum: date, maximum: date) -> tuple[date, ...] | None:
    """브라우저 입력을 서버에서 재검증한다. 미완성·역순·범위 밖 날짜는 적용하지 않는다."""
    if not isinstance(values, (list, tuple)) or len(values) not in (0, 2):
        return None
    try:
        dates = tuple(date.fromisoformat(v) for v in values)
    except (ValueError, TypeError):
        return None
    if dates and not minimum <= dates[0] <= dates[1] <= maximum:
        return None
    return dates


def period_calendar(label: str, *, key: str, today: date, minimum: date, maximum: date) -> tuple[date, ...]:
    component_key = f"_{key}_calendar"

    def apply_period():
        state = st.session_state.get(component_key)
        values = state.get("selected") if isinstance(state, Mapping) else getattr(state, "selected", None)
        dates = decode_period(values, minimum, maximum)
        if dates is not None:
            st.session_state[key] = dates

    # AppTest의 등록부 초기화에도 같은 정의로 렌더링한다.
    component = st.components.v2.component("frontline_period_calendar", html=_HTML, css=_CSS, js=_JS)
    dates = tuple(st.session_state.get(key) or ())
    component(key=component_key, data={"label": label, "dates": [d.isoformat() for d in dates],
              "today": today.isoformat(), "minimum": minimum.isoformat(), "maximum": maximum.isoformat()},
              on_selected_change=apply_period)
    return dates
