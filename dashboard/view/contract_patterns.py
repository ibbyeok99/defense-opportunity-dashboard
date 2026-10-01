"""게시 지표에서 확인되는 계약 규모·빈도만 제공한다. 계약방법·업체 선호는 추론하지 않는다."""
import pandas as pd
import streamlit as st
from view.charts import card
from view.plotly_charts import bar_figure, show
from view.widgets import emphasized_table
from view.fmt import num


def institution_contract_table(institutions: pd.DataFrame) -> pd.DataFrame:
    """기관명이 전부 누락되어도 null 인덱스를 만들지 않는다. 원본은 보존한다."""
    table = institutions[["agency_name", "agency_code", "contract_count"]].copy()
    table["agency_name"] = table["agency_name"].fillna("").astype(str).str.strip()
    missing = table["agency_name"].eq("")
    table.loc[missing, "agency_name"] = "기관명 미제공 (" + table.loc[missing, "agency_code"].astype(str) + ")"
    table = table.sort_values("contract_count", ascending=False)
    table["contract_count"] = table["contract_count"].map(num)
    return table.rename(columns={"agency_name": "계약기관", "agency_code": "기관코드", "contract_count": "계약 수 (건)"}).set_index("계약기관")


def show_contract_patterns(type_year: pd.DataFrame, supported: bool, institutions: pd.DataFrame):
    st.caption("계약 특성은 관측된 계약 건수·금액입니다. 계약방법·업체 선호·향후 발주를 뜻하지 않습니다.")
    with card("어느 조달 유형의 계약이 많나요?", "선택 연도·유형·분류의 계약일 기준 집계. 기관·지역·낙찰금액·낙찰/유찰 조건은 미지원입니다."):
        if not supported:
            st.info("상세 필터를 해제해야 계약일 기준 유형 비교를 볼 수 있습니다.")
        elif type_year.empty:
            st.info("선택 기간의 계약 집계가 없습니다.")
        else:
            table = type_year.groupby("procurement_type", as_index=False).agg(
                contract_count=("contract_count", lambda s: s.sum(min_count=1)),
                contract_amount=("contract_amount", lambda s: s.sum(min_count=1)))
            table["평균 계약금액 (억원)"] = (table["contract_amount"] / table["contract_count"].replace(0, float("nan"))) / 1e8
            table.loc[table.procurement_type == "외자", ["contract_amount", "평균 계약금액 (억원)"]] = float("nan")
            show(bar_figure(table, "procurement_type", "contract_count", value_title="계약 수 (건)", integer=True), key="contract_type_count")
            table["계약금액 (억원)"] = table.pop("contract_amount") / 1e8
            table["contract_count"] = table["contract_count"].map(num)
            for column in ("평균 계약금액 (억원)", "계약금액 (억원)"):
                table[column] = table[column].map(lambda value: num(value, 2) if pd.notna(value) else "—")
            emphasized_table(table.rename(columns={"procurement_type": "유형", "contract_count": "계약 수 (건)"}).set_index("유형"))
            st.caption("평균 금액은 총금액÷계약 수입니다. 외자 금액은 통화가 달라 원화 비교에서 제외합니다. 단가·총액 계약 구분이 없어 평균 규모 해석에 주의하세요.")
    with card("계약기관별 계약 규모는 어떤가요?", "기관 마트의 전체 게시 범위. 위 검색 기간·유형·상세 조건은 이 표에 적용되지 않습니다."):
        inst = institutions
        inst = inst[(inst.agency_role == "계약기관") & inst.contract_count.notna()].copy()
        if inst.empty:
            st.info("계약기관별 집계가 없어 기관 성향을 판단할 수 없습니다.")
            return
        labels = dict(zip(inst.agency_code, inst.agency_name.fillna("기관명 미제공")))
        selected = st.multiselect("계약기관 선택", inst.agency_code.drop_duplicates().tolist(),
                                  format_func=lambda i: f"{labels.get(i, i)} ({i})", key="contract_pattern_agencies")
        inst = inst[inst.agency_code.isin(selected)] if selected else inst
        emphasized_table(institution_contract_table(inst), height=400)
        st.caption("수요기관과 계약기관을 같은 기관으로 간주하지 않습니다. 통화·단가/총액 구분과 기관별 계약일 자료가 연결되기 전에는 기관 금액 비교·계약방법 성향을 표시하지 않습니다.")
