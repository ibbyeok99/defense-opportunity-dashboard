"""공고 목록 전용 읽기 표: native dataframe은 줄바꿈을 공백으로 치환하므로 CCv2 사용."""

from collections.abc import Mapping

import streamlit as st
from view import store

def normalize_sort(value):
    """클라이언트 정렬 이벤트를 허용된 화면 열에 한정한다."""
    labels = ("마감", "공고명", "수요기관", "유형", "참여 판단", "면허·지역 요건")
    if not isinstance(value, dict) or value.get("label") not in labels or value.get("direction") not in (0, 1, 2):
        return {"label": None, "direction": 0}
    return {"label": value["label"], "direction": value["direction"]}

_HTML = '<div class="notice-table-scroll" tabindex="0" aria-label="공고 목록, 좌우로 이동 가능"><table><thead></thead><tbody></tbody></table></div>'
_CSS = """
.notice-table-scroll {overflow-x:auto;border:1px solid var(--st-border-color);border-radius:8px;font-family:var(--st-font);color:var(--st-text-color);font-size:15.4px;}
table {width:100%;min-width:960px;border-collapse:separate;border-spacing:0;table-layout:fixed;}
th,td {padding:13.2px 10px;text-align:left;vertical-align:middle;border-bottom:1px solid var(--st-border-color);word-break:keep-all;overflow-wrap:break-word;text-wrap:pretty;}
th {font-weight:700;color:var(--st-gray-text-color);background:color-mix(in srgb,var(--st-blue-color) 5%,var(--st-background-color));}
td {background:var(--st-secondary-background-color);}
tbody tr:hover td {background:color-mix(in srgb,var(--st-blue-color) 3%,var(--st-secondary-background-color));}
tbody tr:last-child td {border-bottom:0;}
th[data-label="상세"],td[data-label="상세"] {width:52px;padding:8px 4px;border-left:1px solid var(--st-border-color);text-align:center;}
th[data-label="즐겨찾기"],td[data-label="즐겨찾기"],
th[data-label="마감"],td[data-label="마감"],
th[data-label="유형"],td[data-label="유형"] {padding-left:4px;padding-right:4px;}
th[data-label="즐겨찾기"] {width:36px;}
th[data-label="즐겨찾기"],td[data-label="즐겨찾기"] {text-align:center;}
th[data-label="마감"] {width:52px;}
th[data-label="공고명"] {width:350px;}
th[data-label="수요기관"] {width:125px;}
th[data-label="유형"] {width:44px;}
th.requirements {width:275px;}
th.status {width:145px;}
.notice-number {font-size:13.2px;color:color-mix(in srgb,var(--st-text-color) 60%,transparent);margin-top:5.5px;}
.requirement-line + .requirement-line {margin-top:8.8px;}
.requirement-line {line-height:1.55;display:grid;grid-template-columns:max-content minmax(0,1fr);gap:6px;}
.requirement-label {font-weight:700;white-space:nowrap;}
.requirement-values {min-width:0;display:flex;flex-wrap:wrap;gap:3px 8px;}
.requirement-item {max-width:100%;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.requirement-unknown {grid-column:1 / -1;font-weight:400;white-space:nowrap;}
button {font:inherit;background:transparent;color:var(--st-text-color);border:1px solid var(--st-border-color);border-radius:6px;cursor:pointer;min-width:39.6px;min-height:39.6px;}
button:hover,button:focus-visible {border-color:var(--st-primary-color);color:var(--st-primary-color);}
.sort-button {border:0;min-width:0;min-height:26.4px;padding:0;text-align:left;font-weight:700;}
.favorite-button {color:var(--st-orange-text-color);font-size:22px;display:block;position:relative;left:50%;transform:translateX(-50%);}
.notice-title {color:var(--st-blue-text-color);font-size:16.5px;font-weight:600;line-height:1.55;}
.status-pill,.type-pill,.deadline-pill {display:inline-block;border-radius:999px;padding:3.3px 9px;font-size:14.3px;font-weight:600;line-height:1.5;white-space:nowrap;}
.type-pill {color:var(--st-orange-text-color);background:var(--st-orange-background-color);}
.deadline-pill {color:var(--st-blue-text-color);background:var(--st-blue-background-color);}
.deadline-pill.urgent {color:var(--st-red-text-color);background:var(--st-red-background-color);}
.status-pill {background:var(--st-gray-background-color);color:var(--st-gray-text-color);}
"""
_JS = """
export default function({parentElement,data,setTriggerValue}) {
  const table=parentElement.querySelector('table');
  const head=table.querySelector('thead'),body=table.querySelector('tbody');
  head.replaceChildren();body.replaceChildren();
  const sort=data.sort??{label:null,direction:0};
  const labels=data.labels;
  const hr=document.createElement('tr');
  labels.forEach(label=>{const th=document.createElement('th');th.scope='col';th.dataset.label=label;
    if(label==='상세'||label==='즐겨찾기'){th.textContent=label==='즐겨찾기'?'☆':label;th.title=label;}else{
      const button=document.createElement('button');button.type='button';button.className='sort-button';
      button.textContent=label;button.setAttribute('aria-label',label+' 정렬');
      button.onclick=()=>setTriggerValue('sort',{label,direction:sort.label===label?(sort.direction+1)%3:1});th.append(button);
    }
    if(label==='면허·지역 요건') th.className='requirements';
    if(label==='참여 판단') th.className='status';hr.append(th);});head.append(hr);
  function renderRows(){
  body.replaceChildren();
  head.querySelectorAll('th').forEach(th=>{const active=th.dataset.label===sort.label&&sort.direction;
    th.setAttribute('aria-sort',active?(sort.direction===1?'ascending':'descending'):'none');
    const button=th.querySelector('button');if(button)button.textContent=th.dataset.label+(active?(sort.direction===1?' ↑':' ↓'):' ↕');});
  const rows=[...data.rows];
  rows.forEach(row=>{
    const tr=document.createElement('tr');
    labels.forEach(label=>{
      const td=document.createElement('td');td.dataset.label=label;
      if(label==='상세'){const b=document.createElement('button');b.type='button';b.textContent='↗';
        b.setAttribute('aria-label',row['공고명']+' 상세 보기');b.title='공고 상세 열기';
        b.onclick=()=>setTriggerValue('selected',row.id);td.append(b);
      }else if(label==='즐겨찾기'){
        const saved=data.favorites.includes(row.id),b=document.createElement('button');b.type='button';b.className='favorite-button';
        b.textContent=saved?'★':'☆';b.setAttribute('aria-label',row['공고명']+(saved?' 즐겨찾기 해제':' 즐겨찾기 추가'));
        b.setAttribute('aria-pressed',String(saved));b.title=saved?'즐겨찾기 해제':'즐겨찾기 추가';
        b.disabled=!saved&&data.favorites.length>=10;
        if(b.disabled)b.title='최대 10개: 기존 공고를 해제한 뒤 추가하세요';
        b.onclick=()=>setTriggerValue('favorite',row.id);td.append(b);
      }else if(label==='공고명'){
        const title=document.createElement('div');title.className='notice-title';title.textContent=row[label];td.append(title);
        const number=document.createElement('div');number.className='notice-number';number.textContent=row['공고번호·차수'];td.append(number);
      }else if(label==='유형'){
        const badge=document.createElement('span');badge.className='type-pill';badge.textContent=row[label];td.append(badge);
      }else if(label==='마감'&&row.upcoming){
        const badge=document.createElement('span');badge.className='deadline-pill'+(row.urgent?' urgent':'');badge.textContent=row[label];td.append(badge);
      }else if(label==='면허·지역 요건'){
        row.requirement_lines.forEach(line=>{
          const div=document.createElement('div');div.className='requirement-line';div.title=line.full;
          if(line.label){
            const title=document.createElement('strong');title.className='requirement-label';title.textContent=line.label;div.append(title);
            const values=document.createElement('div');values.className='requirement-values';
            line.items.forEach(item=>{const value=document.createElement('span');value.className='requirement-item';value.textContent=item;value.title=item;values.append(value);});div.append(values);
          }else{const text=document.createElement('span');text.className='requirement-unknown';text.textContent=line.full;div.append(text);}
          td.append(div);
        });
      }else if(label==='참여 판단'){
        const badge=document.createElement('span');badge.className='status-pill';badge.textContent=row['참여'].join(' ');
        const tone={'●':'green','▲':'orange','■':'red'}[badge.textContent[0]];
        if(tone){badge.style.color='var(--st-'+tone+'-text-color)';badge.style.background='var(--st-'+tone+'-background-color)';}
        td.append(badge);
      }else{td.textContent=row[label]??'';}
      tr.append(td);
    });body.append(tr);
  });
  if(!data.rows.length){const row=document.createElement('tr'),cell=document.createElement('td');
    cell.colSpan=labels.length;cell.textContent='표시할 공고가 없습니다.';row.append(cell);body.append(row);}
  }
  renderRows();
}
"""


def header_labels(requirements: bool, participation: bool = True) -> list[str]:
    return ["즐겨찾기", "마감", "유형", "공고명", "수요기관", *(["면허·지역 요건"] if requirements else []),
            *(["참여 판단"] if participation else []), "상세"]


def requirement_lines(value: str) -> list[dict]:
    """확인된 제한의 제목만 강조. 전체 요건은 tooltip용으로 보존한다."""
    lines = []
    for full in value.split("\n"):
        label, body = "", full
        for prefix in ("면허 제한", "지역 제한"):
            if full.startswith(prefix):
                label = prefix + (":" if full[len(prefix):].startswith(":") else "")
                body = full[len(label):].strip()
                break
        lines.append({"label": label, "items": body.split(" · "), "full": full})
    return lines


def notice_rows(frame, ids) -> list[dict]:
    rows = frame.to_dict("records")
    for row, notice_id in zip(rows, ids):
        row["id"] = notice_id
        # D-day 문자열 표시만 꾸민다. 원본 날짜·정렬·판정은 변경하지 않는다.
        deadline = str(row.get("마감", ""))
        row["urgent"] = deadline == "D-day" or (deadline.startswith("D-") and deadline[2:].isdigit() and 0 <= int(deadline[2:]) <= 7)
        row["upcoming"] = deadline == "D-day" or (deadline.startswith("D-") and deadline[2:].isdigit())
        if "면허·지역 요건" in row:
            row["requirement_lines"] = requirement_lines(row["면허·지역 요건"])
    return rows


def notice_table(frame, ids):
    def open_detail():
        state = st.session_state.get("nt_notice_table")
        selected = state.get("selected") if isinstance(state, Mapping) else getattr(state, "selected", None)
        if selected in ids:
            st.session_state.open_notice = selected

    def update_sort():
        state = st.session_state.get("nt_notice_table")
        value = state.get("sort") if isinstance(state, Mapping) else getattr(state, "sort", None)
        st.session_state.nt_sort = normalize_sort(value)
        st.session_state.nt_page = 1

    def update_favorite():
        state = st.session_state.get("nt_notice_table")
        value = state.get("favorite") if isinstance(state, Mapping) else getattr(state, "favorite", None)
        if value in ids:
            store.toggle_favorite(value)

    component = st.components.v2.component("frontline_notice_table", html=_HTML, css=_CSS, js=_JS)
    component(key="nt_notice_table", data={"rows": notice_rows(frame, ids),
                                          "labels": header_labels("면허·지역 요건" in frame.columns, "참여" in frame.columns),
                                          "requirements": "면허·지역 요건" in frame.columns,
                                          "sort": normalize_sort(st.session_state.get("nt_sort")),
                                          "favorites": store.favorites()},
              on_selected_change=open_detail, on_sort_change=update_sort, on_favorite_change=update_favorite)
