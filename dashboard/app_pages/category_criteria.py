"""사용자가 확인하는 분류명 매칭 근거·공식 사본 대조 결과. DB에는 쓰지 않는다."""

import streamlit as st

from service import data

st.header("분류명 매칭 기준", anchor=False)
st.caption("어떤 자료로 분류 이름을 표시하는지, 공식 품명과 어떤 차이가 있는지 확인합니다.")
st.page_link("app_pages/item.py", label="분야별 입찰 분석으로", icon=":material/chevron_left:")
with st.container(border=True):
    st.subheader("이름은 이렇게 연결합니다", anchor=False)
    st.markdown("1. **물품·외자의 8자리 물품분류번호**를 조달청 공식 물품 목록과 정확히 대조합니다.\n"
                "2. 코드가 같고 현재 사용 중인 공식 품명이 하나 확인된 경우, 기존 확정·충돌 여부와 관계없이 현재 공식 품명으로 표시합니다.\n"
                "3. 공고 제목·최빈 후보·유사 이름으로 품명을 추정하지 않습니다. 10자리 세부물품분류번호와도 섞지 않습니다.\n"
                "4. 이름이 미확정이면 **물품분류번호 + 코드**로 표시합니다. 공식 목록에 없는 코드를 다른 코드로 바꾸거나 합치지 않습니다.")
    st.caption("현재 공식 품명 기준이며, 과거 공고 당시의 이름과 다를 수 있습니다. 공사·용역의 공공조달분류번호·공종명은 별도 기준입니다. 외자도 8자리 물품분류번호가 정확히 일치할 때만 이름을 연결합니다. 분류번호와 통계값은 바꾸지 않습니다.")

audit = data.category_name_audit()
goods = audit.loc[audit["유형"].isin(["물품", "외자"]) & audit["분류 방식"].eq("product8")]
st.caption(f"공식 목록 확인일: {audit.attrs['checked_at']} · 이 날짜에 확인한 공식 품명을 표시합니다.")
st.link_button("조달청 공식 서비스·명세", audit.attrs["source"], icon=":material/open_in_new:", type="tertiary")
for col, (label, value) in zip(st.columns(4), [
    ("물품·외자 분류", len(goods)), ("공식 목록 대응", goods["공식 품명"].ne("–").sum()),
    ("기존 명칭과 차이", goods["대조 결과"].eq("명칭 차이").sum()),
    ("공식 목록 미대응", goods["대조 결과"].eq("공식 목록 미대응").sum()),
]):
    col.metric(label, f"{value:,}개")
st.caption("명칭 차이는 기존 카탈로그와 현재 공식 품명의 차이입니다. 미대응은 과거·폐지·별도 코드 가능성 등을 추가 확인해야 하며, 코드 오류로 단정하지 않습니다.")
st.caption("이 화면은 분석 대상 분류만 대조한 결과입니다. 공식 품명이 확인되지 않았다는 이유만으로 코드 오류를 뜻하지는 않습니다. "
           "외자 49141510은 현재 공식 품명을 확인하지 못해 기존 이름을 표시합니다. 과거 분류 이력은 추가 확인이 필요합니다.")
with st.expander("코드·분류 연결 검사", expanded=False):
    st.caption(f"유형·분류번호 중복: {audit.attrs['duplicate_keys']:,}개")
    st.caption(f"분류 목록에 없는 분석 분류: {audit.attrs['missing_catalog_keys']:,}개")
    st.caption(f"분류 목록에는 있지만 현재 분석 자료에는 없는 분류: {audit.attrs['catalog_only_count']:,}개")

with st.container(horizontal=True):
    selected_types = st.multiselect("조달 유형", ["물품", "외자"], key="category_audit_types")
    keyword = st.text_input("분류명·번호 검색", placeholder="예: 군복, 49121511", key="category_audit_search")
    statuses = st.multiselect("대조 결과", goods["대조 결과"].drop_duplicates().tolist(), key="category_audit_status")
shown = goods
if selected_types:
    shown = shown[shown["유형"].isin(selected_types)]
if keyword.strip():
    term = keyword.strip()
    shown = shown[shown[["분류번호", "기존 품명", "공식 품명", "화면 표시"]].astype(str).apply(
        lambda column: column.str.contains(term, case=False, regex=False)).any(axis=1)]
if statuses:
    shown = shown[shown["대조 결과"].isin(statuses)]
st.caption(f"검색 결과 {len(shown):,}개 · 원본 명칭과 화면 표시명을 함께 확인할 수 있습니다.")
st.dataframe(shown[["유형", "분류번호", "기존 품명", "공식 품명", "대조 결과", "화면 표시", "공식 변경일"]],
             hide_index=True, width="stretch")
