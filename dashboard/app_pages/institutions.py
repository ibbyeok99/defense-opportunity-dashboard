"""Codex, 2026-09-30: 국방 관련 공고의 선정 기준·기관 판정 목록(읽기 전용)."""

import streamlit as st

from service import data
from view.loading import read
from view.pdf import Report
from view.institution_table import institution_table
from view.widgets import filter_area, pdf_button

with st.container(key="guidance_title"):
    st.header("국방 기관·선정 기준")
st.caption("나라장터 공고 중 국방 조달 분석 대상에 포함하는 기준과 기관 목록입니다.")
with st.container(border=True, gap="small"):
    st.subheader("어떤 공고를 포함하나요?")
    st.markdown("**공고기관 또는 수요기관 중 하나 이상**이 국방 조달 분석 대상 기관이면 검색 결과에 포함합니다.")
    st.caption("조달청이 대신 게시한 공고도 수요기관이 대상 기관이면 포함합니다. 나라장터의 모든 공고나 비공개 국방 조달 전체를 다루지는 않습니다.")
    st.markdown("**기관 확인 기준**: 기관코드 대조, 상위 국방기관·소속 확인, 군부대 코드와 기관명 규칙, 개별 검토 결과를 함께 사용합니다.")
    st.caption("키워드가 있다는 이유만으로 포함하지 않습니다. 확정 근거가 부족한 기관은 검토 대기로 분리하고, 기관 정보가 없는 자료에는 국방 여부를 추정해 붙이지 않습니다.")

try:
    institutions = read('국방 기관 목록을 불러오는 중…', data.defense_institutions)
except (FileNotFoundError, KeyError, ValueError):
    st.error("기관 목록을 불러올 수 없습니다. 잠시 후 다시 확인해 주세요.")
    st.stop()

with filter_area():
    st.markdown("**국방 기관 검색**")
    keyword = st.text_input("기관명·기관코드", key="inst_keyword", placeholder="예: 국방부, 육군, 1290000")
shown = institutions
if keyword.strip():
    term = keyword.strip()
    mask = institutions.astype(str).apply(lambda col: col.str.contains(term, case=False, regex=False)).any(axis=1)
    shown = institutions[mask]
st.subheader(f"국방 조달 분석 대상 기관 {len(institutions):,}곳")
st.caption(f"기관 목록 갱신: {institutions.attrs.get('modified_at', '확인 필요')} · 검색 결과 {len(shown):,}곳")
st.caption("기관별 포함 근거는 아래 표에 표시합니다. 기관 목록 갱신 시각과 공고 데이터 기준 시각은 다릅니다.")
with st.container(key="table_scroll_hint"):
    st.caption(":material/swipe: 표를 좌우로 이동하면 기관별 포함 근거를 볼 수 있습니다.")
institution_table(shown)


def make_pdf():
    report = Report("국방 기관·선정 기준", "공고기관 또는 수요기관 중 하나 이상이 국방 조달 분석 대상 기관이면 검색 결과에 포함합니다.")
    report.para("기관 목록 갱신: " + institutions.attrs.get("modified_at", "확인 필요"))
    report.table(shown[["기관코드", "기관명", "소속 분류", "포함 근거"]], max_rows=len(shown))
    return report.build()


with st.session_state._export_slot:
    st.download_button("CSV", shown.to_csv(index=False).encode("utf-8-sig"), "국방기관_선정기준.csv",
                       "text/csv", icon=":material/download:", type="tertiary", key="inst_csv", on_click="ignore")
    pdf_button("PDF", "국방기관_선정기준.pdf", make_pdf, "inst_pdf", type="tertiary")
