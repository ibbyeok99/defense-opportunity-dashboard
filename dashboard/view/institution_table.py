"""읽기 전용 기관 표. 헤더 강조·긴 근거 줄바꿈·클라이언트 정렬. Codex 2026-10-01."""

import streamlit as st

ROW_HEIGHT_PX = 42  # 기존 기본 행 35px의 1.2배; 긴 문장은 잘리지 않도록 자동 확장.
_HTML = '<div class="institution-scroll" tabindex="0" aria-label="국방 기관 목록, 좌우로 이동 가능"><table><thead></thead><tbody></tbody></table></div>'
_CSS = """
.institution-scroll {overflow-x:auto;border:1px solid var(--st-dataframe-border-color);border-radius:8px;color:var(--st-text-color);font-family:var(--st-font);font-size:14px;}
table {width:100%;min-width:1120px;border-collapse:separate;border-spacing:0;table-layout:fixed;}
tr {height:42px;}
th,td {padding:8px 12px;box-sizing:border-box;text-align:left;vertical-align:middle;border-bottom:1px solid var(--st-border-color);line-height:1.6;overflow-wrap:anywhere;}
th {font-weight:700;background:var(--st-dataframe-header-background-color);}
td {background:var(--st-secondary-background-color);}
th:nth-child(1) {width:112px;} th:nth-child(2) {width:220px;}
th:nth-child(3) {width:100px;} th:nth-child(4) {width:110px;}
th:nth-child(5) {width:190px;} th:nth-child(6) {width:388px;}
tbody tr:last-child td {border-bottom:0;}
tbody tr:hover td {background:color-mix(in srgb,var(--st-primary-color) 4%,var(--st-secondary-background-color));}
button {font:inherit;font-weight:700;color:inherit;border:0;background:transparent;padding:0;text-align:left;cursor:pointer;}
button:focus-visible {outline:2px solid var(--st-primary-color);outline-offset:3px;}
"""
_JS = """
export default function({parentElement,data}) {
  const head=parentElement.querySelector('thead'),body=parentElement.querySelector('tbody');
  let column='기관코드',ascending=true;
  const labels=data.labels,header=document.createElement('tr');
  head.replaceChildren();body.replaceChildren();
  function render() {
    const rows=[...data.rows].sort((a,b)=>{
      const left=String(a[column]??''),right=String(b[column]??'');
      const comparison=column==='기관코드'?(left<right?-1:left>right?1:0):left.localeCompare(right,'ko');
      return (ascending?1:-1)*comparison;
    });
    const fragment=document.createDocumentFragment();
    rows.forEach(row=>{const tr=document.createElement('tr');labels.forEach(label=>{
      const td=document.createElement('td');td.textContent=row[label]??'';tr.append(td);
    });fragment.append(tr);});body.replaceChildren(fragment);
    head.querySelectorAll('th').forEach(th=>{
      const active=th.dataset.label===column;
      th.setAttribute('aria-sort',active?(ascending?'ascending':'descending'):'none');
      th.querySelector('button').textContent=th.dataset.label+(active?(ascending?' ↑':' ↓'):'');
    });
  }
  labels.forEach(label=>{const th=document.createElement('th');th.scope='col';th.dataset.label=label;
    const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',label+' 정렬');
    button.onclick=()=>{ascending=column===label?!ascending:true;column=label;render();};th.append(button);header.append(th);
  });head.append(header);render();
}
"""
def institution_table(frame):
    # 실제 앱 runtime에 등록한다. bare-mode 시험 import의 registry를 재사용하지 않는다.
    component = st.components.v2.component("frontline_institution_table", html=_HTML, css=_CSS, js=_JS)
    component(key="institution_table", data={"labels": list(frame.columns), "rows": frame.to_dict("records")})
