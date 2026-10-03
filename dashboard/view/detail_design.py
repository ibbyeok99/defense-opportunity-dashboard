"""공고 상세의 표시 도우미. 원천 값·참여 판정·통계 기간을 변경하지 않는다."""

from html import escape

import pandas as pd
import streamlit as st

from view.fmt import region_display
from view.copy import condition_text, judgement_reason
from view.help import help_icon


VERDICTS = {
    "● 참여 가능": ("적합", "ok", "확인된 조건을 충족합니다."),
    "▲ 원문 확인": ("원문 확인 필요", "check", "원문 확인이 필요합니다."),
    "■ 참여 불가": ("불충족", "no", "입력한 회사 조건과 맞지 않습니다."),
    "○ 내 조건 미입력": ("내 조건 미입력", "input", "회사 조건을 입력해 주세요."),
}

SCOPE_NOTE = (
    "수집된 면허·지역 조건과 입력한 회사 조건을 비교한 보조 판단입니다. "
    "미확인은 제한 없음이 아닙니다. 업체 유형·실적·인증·기타 자격은 이 판단에 포함하지 않으며, "
    "최종 참가 자격은 공고 원문에서 확인해야 합니다."
)


def verdict(status):
    return VERDICTS.get(status, (str(status), "check", "원문 확인이 필요합니다."))


def display_conditions(conditions):
    frame = conditions.copy(deep=True)
    frame['요구 조건'] = frame['요구 조건'].map(condition_text)
    if '이유' in frame:
        frame['이유'] = frame['이유'].map(judgement_reason)
    mask = frame["구분"].eq("지역")
    for column in ("요구 조건", "내 조건"):
        frame.loc[mask, column] = frame.loc[mask, column].map(
            lambda value: ", ".join(region_display(part) for part in str(value).split(", ")))
    return frame


def _text(value):
    return "–" if value is None or pd.isna(value) else str(value)


def agency_value(notice, stem):
    name = _text(notice.get(f"{stem}_agency_name"))
    code = _text(notice.get(f"{stem}_agency_code"))
    return name, code if code not in ("–", "", name) else ""


def hint_html(label, description):
    """정적 표의 셀 설명. hover와 키보드 focus에서 동일한 내용을 표시한다."""
    return (f'<span class="detail-tip"><button type="button" aria-label="{escape(label, quote=True)} 설명">?</button>'
            f'<span role="tooltip">{escape(str(description))}</span></span>')


def requirements_html(conditions):
    """작은 정적 표. 셀별 도움말·판정 배지를 함께 표현하기 위한 표시 전용 HTML."""
    columns = ["구분", "요구 조건", "내 조건", "판단"]
    parts = ['<div class="detail-table-scroll" tabindex="0" aria-label="요구 조건 상세 표, 좌우로 이동 가능">',
             '<table class="detail-requirements"><colgroup><col style="width:8%"><col style="width:47%">'
             '<col style="width:25%"><col style="width:20%"></colgroup><thead><tr>']
    parts.extend(f'<th scope="col">{label}</th>' for label in columns)
    parts.append('</tr></thead><tbody>')
    for row in conditions.to_dict("records"):
        label, tone, _ = verdict(row["판단"])
        parts.append('<tr>')
        parts.append(f'<th scope="row">{escape(_text(row["구분"]))}</th>')
        parts.extend(f'<td>{escape(_text(row[column]))}</td>' for column in ("요구 조건", "내 조건"))
        parts.append(f'<td><div class="detail-table-judgement"><span class="detail-verdict {tone}">{escape(label)}</span>'
                     f'{hint_html(str(row["구분"]) + " 판단 이유", _text(row["이유"]))}</div></td></tr>')
    parts.append('</tbody></table></div>')
    return "".join(parts)


def section_heading(title, description, *, key):
    with st.container(horizontal=True, wrap=False, vertical_alignment="center", gap="small",
                      key=f"detail_heading_{key}"):
        st.subheader(title, anchor=False, width="stretch")
        help_icon(title, description, key=f"detail_help_{key}")


def basic_row(label, value, *, key, code="", tone=""):
    with st.container(horizontal=True, wrap=False, vertical_alignment="center", gap="small",
                      key=f"detail_basic_row_{key}"):
        st.html(f'<div class="detail-basic-label">{escape(label)}</div>', width=100)
        text = escape(_text(value))
        if code:
            text += f' <span class="detail-agency-code">({escape(code)})</span>'
        accent = f' detail-accent {tone}' if tone in {'red', 'blue'} else ''
        st.html(f'<div class="detail-basic-value{accent}">{text}</div>', width="stretch")


def apply_detail_style():
    """사용자 승인 범위: 상세 창 내부만, 라이트·다크와 좁은 화면을 함께 처리한다."""
    scheme = "dark" if st.context.theme.type == "dark" else "light"
    st.html('''<style>
[data-testid="stDialog"]:has(.st-key-notice_detail_surface) {
  scrollbar-gutter: stable both-edges;
}
[data-testid="stDialog"] > div:has(> [role="dialog"] .st-key-notice_detail_surface) {
  width: min(1240px, calc(100vw - 32px)); max-width: calc(100% - 32px);
  margin-inline: 0;
}
[role="dialog"]:has(.st-key-notice_detail_surface) {
  width: 100%; max-width: 100%;
}
.st-key-notice_detail_surface {
  gap: .6rem; color-scheme: __DETAIL_SCHEME__; width: 100%; max-width: 1120px;
  margin-inline: auto; text-align: left;
}
/* 기존 .6rem 간격의 75%. 제목/번호의 음수 마진을 제거해 양쪽을 동일하게 유지한다. */
.st-key-notice_detail_header { gap: .45rem; }
.st-key-notice_detail_header :is([data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"]) {
  margin-block: 0;
}
.st-key-notice_detail_header [data-testid="stCaptionContainer"] p { margin-block: 0; }
[role="dialog"] [data-testid="stLayoutWrapper"]:has(> .st-key-notice_detail_surface) {
  display: flex; justify-content: center; width: 100%;
}
.st-key-notice_detail_surface [class*="st-key-detail_heading_"] h3 {
  font-size: 1.3rem; font-weight: 700; line-height: 1.4; padding-block: 0; margin: 0;
}
.st-key-notice_detail_surface [class*="st-key-detail_basic_row_"] {
  border-bottom: 1px solid var(--st-border-color); padding-block: .4rem;
}
.st-key-notice_detail_surface .detail-basic-label {
  padding-inline: .5rem; color: light-dark(#53647B, #BBC7D6);
  font-weight: 400; margin: 0; line-height: 1.65;
}
.st-key-notice_detail_surface .detail-basic-value {
  font-weight: 400; line-height: 1.65; word-break: keep-all; overflow-wrap: anywhere;
}
.st-key-notice_detail_surface .detail-accent { font-weight: 600; }
.st-key-notice_detail_surface .detail-accent.red { color: light-dark(#B42318, #FFA3A3); }
.st-key-notice_detail_surface .detail-accent.blue { color: light-dark(#005BDB, #93BEFF); }
.st-key-notice_detail_surface .detail-meta { display: flex; align-items: center; gap: .65rem; flex-wrap: wrap; }
.st-key-notice_detail_surface .detail-meta-text { font-weight: 400; color: light-dark(#53647B, #BBC7D6); }
.st-key-notice_detail_surface .detail-deadline { display: inline-block; border-radius: 6px; padding: .2rem .65rem; font-weight: 600; }
.st-key-notice_detail_surface .detail-deadline.red { color: light-dark(#B42318, #FFA3A3); background: light-dark(#FFE4E5, #512E36); }
.st-key-notice_detail_surface .detail-deadline.blue { color: light-dark(#005BDB, #93BEFF); background: light-dark(#E9F1FF, #273B59); }
.st-key-notice_detail_surface .detail-deadline.gray { color: light-dark(#53647B, #BBC7D6); background: light-dark(#F0F3F8, #303945); }
.st-key-notice_detail_surface :is(.st-key-detail_core, .st-key-detail_judgement) {
  gap: .5rem;
}
.st-key-notice_detail_surface .detail-agency-code {
  font-size: .85em; font-weight: 400; color: light-dark(#64748B, #B7C4D7);
}
.st-key-notice_detail_surface :is(.st-key-detail_core, .st-key-detail_judgement,
  .st-key-detail_requirements, .st-key-detail_competition) {
  background: light-dark(#FFFFFF, #292E36); padding: 1.35rem; border-radius: 12px;
}
.st-key-notice_detail_surface .detail-banner {
  padding: .6rem 1rem; border-radius: 8px; margin-block: .15rem .5rem;
  background: light-dark(#EDF4FF, #273B59); font-size: 1.05rem; font-weight: 600;
  color: light-dark(#005BFF, #93BEFF); line-height: 1.5;
}
.st-key-notice_detail_surface .detail-banner.no { background: light-dark(#FFF0F0, #4A2B32); color: light-dark(#B42318, #FFA3A3); }
.st-key-notice_detail_surface .detail-banner.check { background: light-dark(#FFF7E8, #493D29); color: light-dark(#9A5400, #FFD18B); }
.st-key-notice_detail_surface .detail-banner.input { background: light-dark(#F0F3F8, #303945); color: var(--st-text-color); }
.st-key-notice_detail_surface [class*="st-key-detail_condition_row_"] {
  min-height: 32px; padding-block: .375rem;
  border-bottom: 1px solid var(--st-border-color);
}
.st-key-notice_detail_surface [class*="st-key-detail_condition_row_"] p {
  margin: 0; line-height: 1.6; white-space: nowrap; font-weight: 400;
}
.st-key-notice_detail_surface .detail-table-scroll { overflow-x: auto; overflow-y: visible; padding-block: .2rem; }
.st-key-notice_detail_surface .detail-requirements { border-collapse: separate; border-spacing: 0; table-layout: fixed; width: 100%; min-width: 700px; line-height: 1.65; }
.st-key-notice_detail_surface .detail-requirements th,
.st-key-notice_detail_surface .detail-requirements td { border: 0; border-bottom: 1px solid var(--st-border-color); padding: .65rem 1rem; text-align: left; vertical-align: top; font-weight: 400; background: light-dark(#FFFFFF, #292E36); }
.st-key-notice_detail_surface .detail-requirements thead th { background: light-dark(#C4D0DE, #40516A); color: light-dark(#0D1930, #F1F5FC); font-weight: 700; white-space: nowrap; }
.st-key-notice_detail_surface .detail-requirements tbody th { font-weight: 600; white-space: nowrap; }
.st-key-notice_detail_surface .detail-table-scroll { border: 1px solid var(--st-border-color); border-radius: 8px; padding-block: 0; }
.st-key-notice_detail_surface .detail-requirements :is(td, th) { padding-inline: .7rem; }
.st-key-notice_detail_surface .detail-requirements td:nth-child(2),
.st-key-notice_detail_surface .detail-requirements td:nth-child(3) { word-break: keep-all; overflow-wrap: anywhere; }
.st-key-notice_detail_surface .detail-table-judgement { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap; }
.st-key-notice_detail_surface .detail-table-judgement > .detail-tip { margin-inline-start: auto; flex-shrink: 0; }
.st-key-notice_detail_surface .detail-verdict { display: inline-block; padding: .2rem .65rem; border-radius: 10px; white-space: nowrap; font-size: .9rem; font-weight: 600; }
.st-key-notice_detail_surface .detail-verdict.ok { background: light-dark(#DCF9EC, #1E493C); color: light-dark(#087A4B, #8CE9B5); }
.st-key-notice_detail_surface .detail-verdict.no { background: light-dark(#FFE4E5, #512E36); color: light-dark(#B42318, #FFA3A3); }
.st-key-notice_detail_surface .detail-verdict.check { background: light-dark(#FFF3DC, #493D29); color: light-dark(#8A4A00, #FFD18B); }
.st-key-notice_detail_surface .detail-verdict.input { background: transparent; color: light-dark(#64748B, #BBC7D6); font-weight: 400; }
.st-key-notice_detail_surface .detail-tip { display: inline-flex; position: relative; }
.st-key-notice_detail_surface .detail-tip button { width: 24px; height: 24px; padding: 0; border: 1px solid var(--st-border-color); border-radius: 50%; background: transparent; color: var(--st-text-color); cursor: help; }
.st-key-notice_detail_surface .detail-tip [role="tooltip"] { display: none; position: absolute; z-index: 10; right: 0; bottom: calc(100% + 8px); width: min(300px, 65vw); padding: .65rem; border-radius: 8px; background: light-dark(#F4F7FB, #344252); border: 1px solid var(--st-border-color); color: var(--st-text-color); font-size: .85rem; box-shadow: 0 4px 14px #0002; white-space: normal; }
.st-key-notice_detail_surface .detail-tip:hover [role="tooltip"],
.st-key-notice_detail_surface .detail-tip:focus-within [role="tooltip"] { display: block; }
@media (max-width: 640px) {
  [data-testid="stDialog"] > div:has(> [role="dialog"] .st-key-notice_detail_surface) { width: calc(100vw - 16px); max-width: calc(100% - 16px); }
  .st-key-notice_detail_surface :is(.st-key-detail_core, .st-key-detail_judgement,
    .st-key-detail_requirements, .st-key-detail_competition) { padding: .8rem; }
}
</style>'''.replace("__DETAIL_SCHEME__", scheme))
