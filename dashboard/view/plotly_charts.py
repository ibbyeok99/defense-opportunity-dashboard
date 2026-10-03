"""Codex, 2026-09-30: 기존 데이터·축·높이를 유지하는 Plotly 표시 규칙."""

from __future__ import annotations

import math
import html
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from view.charts import CHART_H, PROCUREMENT_TYPES, empty_chart

GRADIENT = [[0, "rgba(0,102,255,0)"], [1, "rgba(0,102,255,0.16)"]]
CONFIG = {"displayModeBar": False, "scrollZoom": False, "responsive": True}
GRID_COLOR = "rgba(128,132,149,0.25)"  # 두 모드 모두에서 보이는 반투명 중성 격자
DASHES = ["solid", "dash", "dot", "dashdot"]
BAR_GRADIENT_OPACITY = [0.35, 0.95]
DONUT_LABEL_FONT_SIZE = 18
DONUT_VALUE_FONT_SIZE = 26


def license_tick_label(value: str) -> str:
    """괄호는 의미 단위로 분리한다. 축의 축약 내용은 hover·전체 이름 표에서 확인한다."""
    value = str(value)
    def short(text):
        return html.escape(text if len(text) <= 18 else text[:17] + "…")
    if "(" in value:
        name, detail = value.split("(", 1)
        return short(name) + "<br>" + short("(" + detail)
    if "/" in value:
        name, code = value.rsplit("/", 1)
        return short(name) + "<br>" + short("/" + code)
    return short(value)


def _palette():
    mode = "dark" if st.context.theme.type == "dark" else "light"
    dark = mode == "dark"
    colors = st.get_option(f"theme.{mode}.chartCategoricalColors") or (
        ["#3694FF", "#FF9500", "#BB57FF", "#00DBA5"] if dark else
        ["#0066FF", "#FF6800", "#8B20FF", "#00A884"])
    return colors


def integer_step(maximum: float) -> int:
    """실제 데이터를 반올림하지 않고 정수 눈금 간격만 선택한다. 중복 라벨을 방지한다."""
    target = max(1.0, maximum / 5)
    power = 10 ** math.floor(math.log10(target))
    return max(1, next(n * power for n in (1, 2, 5, 10) if n * power >= target))


def _axis(title, values=(), *, category=False, integer=False, percent=False, log=False, ticks=None):
    options = dict(title=dict(text=title, font=dict(size=15), standoff=10),
                   tickfont=dict(size=14), automargin=True, showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
                   zeroline=False, fixedrange=True, type="category" if category else "linear")
    if category:
        options.update(categoryorder="array", categoryarray=list(dict.fromkeys(values)))
    if percent:
        options["tickformat"] = ".1~%"
    if integer and not category:
        numbers = pd.to_numeric(pd.Series(list(values), dtype="object"), errors="coerce").dropna()
        options.update(tickformat=",d", tick0=0, dtick=integer_step(float(numbers.max()) if len(numbers) else 0))
    if log:
        options.update(type="log", tickmode="array", tickvals=ticks, ticktext=[f"{n:,}" for n in ticks])
        options.pop("dtick", None)
    elif not category:
        options["rangemode"] = "tozero"
    return options


def _layout(fig, *, xaxis, yaxis, height, legend):
    colors = _palette()
    fig.update_layout(
        height=height, autosize=True, template="none",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans KR, sans-serif", size=14), colorway=colors,
        margin=dict(l=10, r=14, t=48 if legend else 12, b=40),
        xaxis=xaxis, yaxis=yaxis, showlegend=legend,
        legend=dict(orientation="h", y=1.08, yanchor="bottom", x=0, font=dict(size=14)),
        hovermode="closest", hoverlabel=dict(font=dict(family="IBM Plex Sans KR, sans-serif", size=14)),
        dragmode=False, barmode="stack")
    return fig


def _groups(frame, series, order):
    if series is None:
        return [("", frame, 0)]
    domain = order or (PROCUREMENT_TYPES if series == "procurement_type" else list(frame[series].drop_duplicates()))
    return [(name, frame[frame[series] == name], i) for i, name in enumerate(domain)
            if (frame[series] == name).any()]


def line_figure(frame, x, y, *, x_title="연도", y_title, series=None, order=None,
                integer=False, percent=False, log=False, ticks=None, height=CHART_H, annual=False):
    fig = go.Figure()
    colors = _palette()
    maximum = pd.to_numeric(frame[y], errors="coerce").max()
    maximum = float(maximum) if pd.notna(maximum) and maximum > 0 else 1
    gradient_start = 0
    if log:
        # 로그 축의 0은 화면 밖 무한대다. 보이는 양수 범위에서 투명해지도록 한다.
        positive = pd.to_numeric(frame[y], errors="coerce")
        positive = positive[positive > 0]
        gradient_start = float(positive.min()) if len(positive) else maximum / 10
        if gradient_start >= maximum:
            gradient_start = maximum / 10
    groups = _groups(frame, series, order)
    fill_alpha = 0.16 / max(1, len(groups))  # 겹친 계열도 전체 채움이 탁해지지 않도록 보정
    for name, subset, index in groups:
        plot_x, plot_y = subset[x].tolist(), subset[y].tolist()
        if annual and len(subset):
            years = [_year_number(value) for value in plot_x]
            if len(set(years)) != len(years):
                raise ValueError("동일 계열의 연도가 중복됩니다. 집계 기준을 확인하세요.")
            points = dict(zip(years, plot_y))
            plot_x = list(range(min(years), max(years) + 1))
            # 결측 연도는 0이 아니다. 선도 누락 구간을 가로질러 연결하지 않는다.
            plot_y = [points.get(year) for year in plot_x]
        # fill은 표시층뿐이다. 선·툴팁의 실제 중앙값/평균값은 반올림하지 않는다.
        fig.add_trace(go.Scatter(
            x=plot_x, y=plot_y, name=str(name), mode="lines+markers", connectgaps=False,
            line=dict(color=colors[index % len(colors)], width=2.5, dash=DASHES[index % len(DASHES)] if series else "solid"),
            marker=dict(size=7), fill="tozeroy",
            fillgradient=dict(type="vertical", start=gradient_start, stop=maximum,
                              colorscale=[[0, GRADIENT[0][1]], [1, f"rgba(0,102,255,{fill_alpha:g})"]]),
            hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y:{'.1%' if percent else ',.1~f' if integer else ',.2f'}}}<extra>{name}</extra>"))
    year_axis = _axis(x_title, frame[x], category=True)
    if annual:
        numbers = [_year_number(value) for value in frame[x]]
        year_axis = _axis(x_title)
        year_axis.pop("rangemode", None)
        year_axis.update(dtick=1, tickformat="d")
        if numbers:
            labels = dict(zip(numbers, frame[x].astype(str)))
            years = list(range(min(numbers), max(numbers) + 1))
            year_axis.update(tickmode="array", tickvals=years,
                             ticktext=[labels.get(year, str(year)) for year in years])
            if len(years) == 1:
                year_axis.update(range=[years[0] - .5, years[0] + .5])
    return _layout(fig,
                   xaxis=year_axis,
                   yaxis=_axis(y_title, frame[y], integer=integer, percent=percent, log=log, ticks=ticks),
                   height=height, legend=series is not None)


def _year_number(value):
    match = re.fullmatch(r"((?:19|20)\d{2})(?:\s*\([^)]*\))?", str(value))
    if not match:
        raise ValueError("연도 그래프에는 4자리 연도 또는 부분 기간 표시만 사용할 수 있습니다.")
    return int(match.group(1))


def bar_figure(frame, category, value, *, category_title="연도", value_title,
               horizontal=False, series=None, order=None, sort_desc=False, integer=False,
               height=CHART_H, show_legend=None, wrap_labels=False, max_category_ticks=None):
    fig = go.Figure()
    colors = _palette()
    categories = frame[category].drop_duplicates().tolist()
    if sort_desc:
        categories = frame.groupby(category, sort=False)[value].sum().sort_values(ascending=False, kind="stable").index.tolist()
    for name, subset, index in _groups(frame, series, order):
        kwargs = dict(x=subset[value].tolist(), y=subset[category].tolist(), orientation="h") if horizontal else dict(
            x=subset[category].tolist(), y=subset[value].tolist())
        fig.add_trace(go.Bar(**kwargs, name=str(name), marker_color=colors[index % len(colors)],
                             hovertemplate=f"{category_title or '분류'}: %{{{'y' if horizontal else 'x'}}}<br>{value_title}: %{{{'x' if horizontal else 'y'}:{',.0f' if integer else ',.1f'}}}<extra>{name}</extra>"))
    categorical = _axis(category_title, categories, category=True)
    if len(categories) == 1:
        # 범주 1개는 중앙의 17.5% 폭으로 표시한다. 가짜 범주/데이터를 추가하지 않는다.
        for trace in fig.data:
            trace.width = 0.35
        categorical.update(range=[-1, 1], autorange=False)
    if horizontal:
        if len(categories) != 1:
            categorical["autorange"] = "reversed"
        categorical.update(tickmode="array", tickvals=categories,
                           ticktext=[str(c) if len(str(c)) <= 18 else str(c)[:17] + "…" for c in categories])
        if wrap_labels:
            categorical["ticktext"] = [license_tick_label(c) for c in categories]
    elif max_category_ticks and len(categories) > max_category_ticks:
        indexes = np.linspace(0, len(categories) - 1, max_category_ticks).round().astype(int)
        categorical.update(tickmode="array", tickvals=[categories[i] for i in indexes], tickangle=0)
    quantitative = _axis(value_title, frame[value], integer=integer)
    if not integer:
        quantitative["tickformat"] = ",.6~f"  # k 축약 대신 단위와 쉼표를 명시, 값 자체는 보존
    return _layout(fig, xaxis=quantitative if horizontal else categorical,
                   yaxis=categorical if horizontal else quantitative, height=height,
                   legend=series is not None if show_legend is None else show_legend)


def histogram_figure(values, *, x_title, y_title="건수 (건)", height=CHART_H):
    fig = go.Figure(go.Histogram(x=list(values), nbinsx=25, marker_color=_palette()[0],
                                hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y:,d}}<extra></extra>"))
    # 원본 일수는 그대로 Plotly에 전달한다. 예상 구간 빈도는 정수 눈금 간격에만 사용한다.
    counts, _ = np.histogram(values, bins=25) if len(values) else (np.array([0]), [])
    return _layout(fig, xaxis=_axis(x_title, values, integer=True),
                   yaxis=_axis(y_title, [counts.max()], integer=True), height=height, legend=False)


def has_chart_values(fig):
    """지원 그래프의 수치 축만 검사한다. 범주명 또는 0을 결측으로 취급하지 않는다."""
    for trace in fig.data:
        axis = "x" if trace.type == "histogram" or getattr(trace, "orientation", None) == "h" else "y"
        values = getattr(trace, axis, None)
        if values is not None and any(value is not None and pd.notna(value) for value in values):
            return True
    return False


def show(fig, *, key: str):
    if not has_chart_values(fig):
        empty_chart(height=fig.layout.height or CHART_H, key=f"empty_{key}")
        return
    # 문자 색은 모드 전환 즉시 native theme가 보정한다. 격자는 반투명 중성색이다.
    st.plotly_chart(fig, width="stretch", theme="streamlit", key=key, config=CONFIG)


# Bar/Histogram에는 fillgradient가 없다. native SVG의 채움만 보정한다.
# Plotly SVG 구조 변경 시 아래 selectors와 브라우저 검사를 함께 확인해야 한다.
_BAR_GRADIENT_JS = """
export default function ({data}) {
  const ns='http://www.w3.org/2000/svg', entries=new Map();
  const prefix='frontline-bar-'+Date.now().toString(36)+'-';
  let pending=0;
  function paint(graph, entry) {
    const horizontal=graph.data?.find(t=>t.type==='bar' || t.type==='histogram')?.orientation==='h';
    graph.querySelectorAll('.barlayer .trace.bars').forEach((trace,index)=>{
      trace.querySelectorAll('.point path').forEach(path=>{
        const raw=path.style.fill || getComputedStyle(path).fill;
        const color=raw.startsWith('url(') ? entry.paths.get(path) : raw;
        if(!color || color==='none') return;
        entry.paths.set(path,color);
        // Mは基点、最初のH/Vは終点。負の値でも基点側を薄くする。
        const d=path.getAttribute('d') || '';
        const origin=d.match(/^M([\\d.eE+-]+),([\\d.eE+-]+)/);
        const end=d.match(horizontal ? /H([\\d.eE+-]+)/ : /V([\\d.eE+-]+)/);
        const negative=origin && end && (horizontal ? Number(end[1])<Number(origin[1]) : Number(end[1])>Number(origin[2]));
        const id=entry.prefix+'-'+index+'-'+(negative?'negative':'positive');
        const svg=path.ownerSVGElement;
        let gradient=svg.querySelector('#'+id);
        if(!gradient){
          let defs=svg.querySelector('defs');
          if(!defs){defs=document.createElementNS(ns,'defs');svg.prepend(defs);}
          gradient=document.createElementNS(ns,'linearGradient');gradient.id=id;
          gradient.setAttribute('gradientUnits','objectBoundingBox');
          gradient.setAttribute('x1',horizontal?(negative?'100%':'0%'):'0%');
          gradient.setAttribute('x2',horizontal?(negative?'0%':'100%'):'0%');
          gradient.setAttribute('y1',horizontal?'0%':(negative?'0%':'100%'));
          gradient.setAttribute('y2',horizontal?'0%':(negative?'100%':'0%'));
          data.opacity.forEach((opacity,i)=>{
            const stop=document.createElementNS(ns,'stop');
            stop.setAttribute('offset',i?'100%':'0%');stop.setAttribute('stop-opacity',opacity);
            gradient.append(stop);
          });
          defs.append(gradient);entry.gradients.add(gradient);
        }
        gradient.querySelectorAll('stop').forEach(stop=>stop.setAttribute('stop-color',color));
        path.style.fill='url(#'+id+')';
      });
    });
    for(const path of entry.paths.keys()) if(!path.isConnected) entry.paths.delete(path);
  }
  function scan() {
    pending=0;
    document.querySelectorAll('[data-testid="stMainBlockContainer"] [data-testid="stPlotlyChart"] .js-plotly-plot').forEach(graph=>{
      if(entries.has(graph) || typeof graph.on!=='function') return;
      const entry={prefix:prefix+entries.size,paths:new Map(),gradients:new Set()};
      entry.listener=()=>paint(graph,entry);entries.set(graph,entry);
      graph.on('plotly_afterplot',entry.listener);paint(graph,entry);
    });
  }
  function schedule(){if(!pending) pending=requestAnimationFrame(scan);}
  const observer=new MutationObserver(schedule);
  observer.observe(document.body,{childList:true,subtree:true});scan();
  return ()=>{
    observer.disconnect();if(pending) cancelAnimationFrame(pending);
    for(const [graph,entry] of entries){
      graph.removeListener('plotly_afterplot',entry.listener);
      for(const [path,color] of entry.paths) if(path.style.fill.includes(entry.prefix)) path.style.fill=color;
      for(const gradient of entry.gradients) gradient.remove();
    }
  };
}
"""


def mount_bar_gradients():
    """페이지 실행마다 한 번 등록·장착. 데이터·축·툴팁은 native Plotly가 담당한다."""
    binder = st.components.v2.component("frontline_plotly_bar_gradients", html="<span></span>", js=_BAR_GRADIENT_JS)
    binder(key="plotly_bar_gradient_guard", height=0, data={"opacity": BAR_GRADIENT_OPACITY})


def donut_figure(frame, *, height=CHART_H):
    colors = _palette()
    by_type = frame.set_index("procurement_type")
    labels = [name for name in PROCUREMENT_TYPES if name in by_type.index]
    values = [int(by_type.loc[name, "notice_count"]) for name in labels]
    total = sum(values)
    focus = max(range(len(values)), key=values.__getitem__)
    span = min(1, 250 / max(1, height - 68))  # 기존 도넛 최대 반지름 125px 유지
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=.62, sort=False, textinfo="none", direction="clockwise",
        domain=dict(x=[0, 1], y=[(1 - span) / 2, (1 + span) / 2]),
        marker=dict(colors=[colors[PROCUREMENT_TYPES.index(name) % len(colors)] for name in labels]),
        customdata=[[name, value, value / total] for name, value in zip(labels, values)],
        hovertemplate="%{label}<br>공고 수: %{value:,d}건<br>공고 비중: %{percent:.1%}<extra></extra>"))
    fig.update_layout(height=height, template="none", autosize=True,
                      font=dict(family="IBM Plex Sans KR, sans-serif", size=14),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=14, t=56, b=12),
                      legend=dict(orientation="h", y=1.08, yanchor="bottom", x=0, xanchor="left"),
                      annotations=[dict(x=.5, y=.5, xref="paper", yref="paper", showarrow=False, align="center",
                                        # 큰 수치 기준으로 Plotly의 주석 영역도 확보한다.
                                        font=dict(size=DONUT_VALUE_FONT_SIZE,
                                                  color="#F0F2F5" if st.context.theme.type == "dark" else "#000000"),
                                        text=f"{labels[focus]}<br><b>{values[focus]:,}건</b><br>{values[focus] / total:.1%}")])
    return fig


_DONUT_JS = """
export default function ({data}) {
  let graph, shown=data.initial;
  function render() {
    const lines=graph?.querySelectorAll('.annotation-text tspan.line');
    if (!lines || lines.length!==3) return;
    lines[0].textContent=shown[0];
    lines[1].textContent=Number(shown[1]).toLocaleString('ko-KR')+'건';
    lines[2].textContent=(Number(shown[2])*100).toFixed(1)+'%';
    lines[1].setAttribute('font-weight','bold');
    lines.forEach((line,i)=>line.setAttribute('font-size',String(i===1?data.valueFontSize:data.labelFontSize)));
    // em은 줄별 글씨 크기에 따라 달라져 겹친다. 같은 px 간격으로 고정한다.
    lines.forEach((line,i)=>line.setAttribute('dy',String((i*1.4-.1)*data.valueFontSize)+'px'));
    // color-scheme에 따라 재실행 없이 전환. 조각·범례·툴팁 색은 변경하지 않는다.
    lines.forEach(line=>line.style.fill='light-dark(#000000, #F0F2F5)');
  }
  function select(event) {
    const point=event.points?.[0];
    const row=data.rows.find(row=>row[0]===point?.label);
    if(row){shown=row;render();}
  }
  function bind() {
    const next=document.querySelector('.st-key-'+data.chartKey+' .js-plotly-plot');
    if (!next || typeof next.on!=='function' || !next.querySelector('.annotation-text')) return;
    graph=next;
    graph.on('plotly_hover',select);graph.on('plotly_click',select);graph.on('plotly_afterplot',render);
    render();observer.disconnect();
  }
  // 네이티브 Plotly 형제 요소에만 연결한다. 선택·필터·데이터를 변경하지 않는다.
  const observer=new MutationObserver(bind);
  observer.observe(document.body,{childList:true,subtree:true});bind();
  return ()=>{
    observer.disconnect();
    if(graph){graph.removeListener('plotly_hover',select);graph.removeListener('plotly_click',select);graph.removeListener('plotly_afterplot',render);}
  };
}
"""

def show_donut(frame):
    if frame.empty or pd.to_numeric(frame.notice_count, errors="coerce").fillna(0).sum() <= 0:
        empty_chart(key="empty_overview_type_donut")
        return
    fig = donut_figure(frame)
    st.plotly_chart(fig, width="stretch", theme="streamlit", key="overview_type_donut", config=CONFIG)
    row = frame.loc[frame.notice_count.idxmax()]
    # 실제 실행 컨텍스트에서 한 번 등록한다. AppTest의 별도 Runtime에도 등록을 보장한다.
    binder = st.components.v2.component("frontline_plotly_donut_center", html="<span></span>", js=_DONUT_JS)
    binder(key="plotly_donut_guard", height=0,
           data={"chartKey": "overview_type_donut",
                 "labelFontSize": DONUT_LABEL_FONT_SIZE, "valueFontSize": DONUT_VALUE_FONT_SIZE,
                 "rows": [list(row) for row in fig.data[0].customdata],
                 "initial": [row.procurement_type, int(row.notice_count), float(row["비중"])]})
