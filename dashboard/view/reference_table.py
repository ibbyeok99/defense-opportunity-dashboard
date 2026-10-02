"""승인된 기관 표 시안의 읽기 전용 공통 표. 데이터·정렬 값과 표시 값은 분리한다."""

import json
import unicodedata

import pandas as pd
import streamlit as st

_HTML = '\n<div class="reference-scroll" tabindex="0"><table><colgroup></colgroup><thead></thead><tbody></tbody></table></div>\n'
_CSS = """
.reference-scroll {overflow:auto;border:1px solid var(--st-dataframe-border-color);border-radius:8px;color:var(--st-text-color);font-family:var(--st-font);font-size:14px;max-width:100%;}
table {width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;}
tr {height:42px;}
th,td {padding:8px 12px;box-sizing:border-box;text-align:left;vertical-align:middle;border-bottom:1px solid var(--st-border-color);line-height:1.6;word-break:keep-all;overflow-wrap:anywhere;}
th {font-weight:700;background:var(--st-dataframe-header-background-color);position:sticky;top:0;z-index:1;}
td {background:var(--st-secondary-background-color);font-weight:400;}
tbody tr:last-child td {border-bottom:0;}
tbody tr:hover td {background:color-mix(in srgb,var(--st-primary-color) 4%,var(--st-secondary-background-color));}
button {font:inherit;font-weight:700;color:inherit;border:0;background:transparent;padding:0;text-align:left;cursor:pointer;}
button:focus-visible {outline:2px solid var(--st-primary-color);outline-offset:3px;}
.progress {display:flex;align-items:center;gap:8px;}
.track {height:6px;flex:1;min-width:36px;background:var(--st-border-color);border-radius:3px;overflow:hidden;}
.fill {display:block;height:100%;background:var(--st-primary-color);}
.status {display:inline-block;padding:2px 9px;border-radius:6px;font-weight:600;}
.status.green {color:var(--st-green-text-color);background:var(--st-green-background-color);}
.status.red {color:var(--st-red-text-color);background:var(--st-red-background-color);}
.status.orange {color:var(--st-orange-text-color);background:var(--st-orange-background-color);}
.status.blue {color:var(--st-blue-text-color);background:var(--st-blue-background-color);}
"""
_JS = """
export default function({parentElement,data}) {
  const root=parentElement.querySelector('.reference-scroll'),table=root.querySelector('table');
  const head=table.querySelector('thead'),body=table.querySelector('tbody'),cols=table.querySelector('colgroup');
  root.setAttribute('aria-label',data.label+' 표, 헤더를 눌러 정렬');
  if(data.max_height)root.style.maxHeight=data.max_height+'px';else root.style.removeProperty('max-height');
  table.style.minWidth=data.min_width+'px';
  cols.replaceChildren();head.replaceChildren();body.replaceChildren();
  const totalWidth=Object.values(data.widths).reduce((sum,width)=>sum+width,0);
  data.labels.forEach(label=>{const col=document.createElement('col');col.style.width=data.fit_container?(data.widths[label]/totalWidth*100)+'%':data.widths[label]+'px';cols.append(col);});
  let column=root.dataset.sortColumn??'',ascending=root.dataset.ascending!=='false';
  if(!data.labels.includes(column))column='';
  function numeric(value) {
    if(value===null||value==='')return null;
    const number=typeof value==='number'?value:Number(String(value).replaceAll(',',''));
    return Number.isFinite(number)?number:null;
  }
  function content(td,label,value) {
    if(value===null||value===''){td.textContent='—';return;}
    const badge=typeof value==='string'?value.match(/^(.*?)\\s*:(green|red|orange|blue)-badge\\[([^\\]]+)\\]$/):null;
    if(data.badges.includes(label)&&badge){
      td.textContent=badge[1]?(badge[1]+' '):'';
      const span=document.createElement('span');span.className='status '+badge[2];span.textContent=badge[3];td.append(span);return;
    }
    const number=numeric(value),format=data.formats[label];
    let text=String(value);
    if(format==='percent'&&number!==null)text=(number*100).toFixed(1)+'%';
    else if(format==='integer'&&number!==null)text=number.toLocaleString('en-US',{maximumFractionDigits:0});
    else if(format==='plain_integer'&&number!==null)text=String(Math.trunc(number));
    if(data.progress.includes(label)&&number!==null){
      const group=document.createElement('span'),track=document.createElement('span'),fill=document.createElement('span'),caption=document.createElement('span');
      group.className='progress';track.className='track';fill.className='fill';fill.style.width=Math.max(0,Math.min(1,number))*100+'%';
      caption.textContent=text;track.setAttribute('aria-hidden','true');track.append(fill);group.append(track,caption);td.append(group);
    }else td.textContent=text;
  }
  function render(){
    const rows=data.rows.map((row,index)=>({row,index}));
    if(column)rows.sort((a,b)=>{
      let left=a.row[column],right=b.row[column];
      if(data.numeric.includes(column)){left=numeric(left);right=numeric(right);}
      const lEmpty=left===null||left==='',rEmpty=right===null||right==='';
      if(lEmpty||rEmpty)return lEmpty===rEmpty?a.index-b.index:lEmpty?1:-1;
      const comparison=data.numeric.includes(column)?left-right:String(left).localeCompare(String(right),'ko');
      return comparison?(ascending?comparison:-comparison):a.index-b.index;
    });
    const fragment=document.createDocumentFragment();
    rows.forEach(({row})=>{const tr=document.createElement('tr');data.labels.forEach(label=>{const td=document.createElement('td');content(td,label,row[label]);tr.append(td);});fragment.append(tr);});
    body.replaceChildren(fragment);
    head.querySelectorAll('th').forEach(th=>{const active=th.dataset.label===column;
      th.setAttribute('aria-sort',active?(ascending?'ascending':'descending'):'none');
      th.querySelector('button').textContent=th.dataset.label+(active?(ascending?' ↑':' ↓'):'');
    });
    root.dataset.sortColumn=column;root.dataset.ascending=String(ascending);
  }
  const header=document.createElement('tr');
  data.labels.forEach(label=>{const th=document.createElement('th'),button=document.createElement('button');
    th.scope='col';th.dataset.label=label;button.type='button';button.setAttribute('aria-label',label+' 정렬');
    button.onclick=()=>{ascending=column===label?!ascending:true;column=label;render();};th.append(button);header.append(th);
  });head.append(header);render();
}
"""


def _text_width(value):
    text = str(value)
    return sum(14 if unicodedata.east_asian_width(char) in {"W", "F"} else 7 for char in text) + 32


def table_payload(frame, *, label, formats=None, widths=None, numeric_columns=(), progress_columns=(), badge_columns=(), height="content", fit_container=False, width_scale=1.0):
    """빈 값·코드의 선행 0·행 순서 보존. 집계·이름 추정·CSV 변경은 하지 않는다."""
    display = frame.reset_index() if frame.index.name is not None else frame.copy()
    formats, widths = dict(formats or {}), dict(widths or {})
    rows = json.loads(display.to_json(orient="records", date_format="iso", double_precision=15))
    labels = list(display.columns)
    sizes = {column: widths.get(column, min(360, max(100, _text_width(column),
             max((_text_width(row[column]) for row in rows if row[column] is not None), default=0)))) for column in labels}
    sizes = {column: round(width * width_scale) for column, width in sizes.items()}
    numeric = set(numeric_columns) | set(formats) | set(progress_columns)
    numeric |= {column for column in labels if pd.api.types.is_numeric_dtype(display[column])
                and not pd.api.types.is_bool_dtype(display[column])}
    return {"label": label, "labels": labels, "rows": rows, "formats": formats, "widths": sizes,
            "numeric": sorted(numeric), "progress": list(progress_columns), "badges": list(badge_columns),
            "min_width": 0 if fit_container else sum(sizes.values()), "fit_container": fit_container,
            "max_height": height if isinstance(height, int) else None}


def reference_table(frame, *, key, label, compact=False, **options):
    payload = table_payload(frame, label=label, **options)
    # runtime마다 등록: bare-mode import/AppTest의 별도 registry를 재사용하지 않는다.
    component = st.components.v2.component(f"frontline_reference_{key}", html=_HTML, css=_CSS, js=_JS)
    component(key=key, data=payload, width=payload["min_width"] + 2 if compact else "stretch")
