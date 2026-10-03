"""게시 지표에서 확인되는 계약 규모·빈도만 제공한다. 계약방법·업체 선호는 추론하지 않는다."""
import pandas as pd
import streamlit as st
from view.charts import card, empty_chart
from view.plotly_charts import bar_figure, show
from view.reference_table import reference_table
from view.fmt import num


def institution_contract_counts(institutions: pd.DataFrame, *, years=None, types=None,
                                names: pd.DataFrame | None = None) -> pd.DataFrame:
    """계약기관 코드별 합산. 기관명 명부의 정확한 코드 일치만 사용한다."""
    table = institutions.copy()
    if "agency_role" in table:
        table = table[table.agency_role.eq("계약기관")]
    if years is not None:
        table = table[pd.to_numeric(table.year, errors="coerce").between(*years)]
    if types is not None:
        table = table[table.procurement_type.isin(types)]
    table = table.loc[table.contract_count.notna(), ["agency_name", "agency_code", "contract_count"]].copy()
    table["agency_code"] = table.agency_code.fillna("").astype(str).str.strip()
    table["agency_name"] = table.agency_name.fillna("").astype(str).str.strip()
    table["contract_count"] = pd.to_numeric(table.contract_count, errors="coerce")

    def unique_name(values):
        values = values[values.ne("")].drop_duplicates()
        return values.iloc[0] if len(values) == 1 else ""

    # 코드가 없는 행을 동일 기관으로 합치지 않는다. 금액·기관명 유사도는 사용하지 않는다.
    table["_group"] = [("code", code) if code else ("missing", index)
                       for index, code in enumerate(table.agency_code)]
    table = table.groupby("_group", sort=False, as_index=False).agg(
        agency_code=("agency_code", "first"), agency_name=("agency_name", unique_name),
        contract_count=("contract_count", lambda values: values.sum(min_count=1)))
    if names is not None and not names.empty:
        reference = names[["기관코드", "기관명"]].fillna("").astype(str).apply(lambda column: column.str.strip())
        reference = reference[reference["기관코드"].ne("")]
        mapping = reference.groupby("기관코드")["기관명"].agg(unique_name)
        missing = table.agency_name.eq("")
        table.loc[missing, "agency_name"] = table.loc[missing, "agency_code"].map(mapping).fillna("")
    missing = table.agency_name.eq("")
    table.loc[missing, "agency_name"] = table.loc[missing, "agency_code"].map(
        lambda code: f"기관명 미제공 ({code})" if code else "기관명·코드 미제공")
    return table.drop(columns="_group").sort_values(
        ["contract_count", "agency_code"], ascending=[False, True], na_position="last").reset_index(drop=True)


def institution_contract_table(institutions: pd.DataFrame, **options) -> pd.DataFrame:
    """표시 전 숫자로 합산·정렬하며 원천 자료를 변경하지 않는다."""
    table = institution_contract_counts(institutions, **options)
    table["contract_count"] = table["contract_count"].map(num)
    return table.rename(columns={"agency_name": "계약기관", "agency_code": "기관코드", "contract_count": "계약 수 (건)"}).set_index("계약기관")


def show_contract_patterns(type_year: pd.DataFrame, supported: bool, institutions: pd.DataFrame,
                           *, years=None, types=None, names=None):
    st.caption("계약 특성은 관측된 계약 건수·금액입니다. 계약방법·업체 선호·향후 발주를 뜻하지 않습니다.")
    with card("어느 조달 유형의 계약이 많나요?", "분류별 집계표 기준: 선택 연도·유형·분류의 계약일 집계. 기관·지역·낙찰금액·낙찰/유찰 조건은 미지원입니다."):
        if not supported:
            st.info("상세 필터를 해제해야 계약일 기준 유형 비교를 볼 수 있습니다.")
        elif type_year.empty:
            st.info("선택 기간의 계약 집계가 없습니다.")
            empty_chart(key="empty_contract_type_count")
        else:
            table = type_year.groupby("procurement_type", as_index=False).agg(
                contract_count=("contract_count", lambda s: s.sum(min_count=1)),
                contract_amount=("contract_amount", lambda s: s.sum(min_count=1)))
            table["평균 계약금액 (억원)"] = (table["contract_amount"] / table["contract_count"].replace(0, float("nan"))) / 1e8
            table.loc[table.procurement_type == "외자", ["contract_amount", "평균 계약금액 (억원)"]] = float("nan")
            chart_column, table_column = st.columns([1, 1], gap="large", vertical_alignment="center")
            with chart_column:
                show(bar_figure(table, "procurement_type", "contract_count", category_title="조달 유형",
                                value_title="계약 수 (건)", integer=True, series="procurement_type"),
                     key="contract_type_count")
            table["계약금액 (억원)"] = table.pop("contract_amount") / 1e8
            table["contract_count"] = table["contract_count"].map(num)
            for column in ("평균 계약금액 (억원)", "계약금액 (억원)"):
                table[column] = table[column].map(lambda value: num(value, 2) if pd.notna(value) else "—")
            with table_column:
                reference_table(table.rename(columns={"procurement_type": "유형", "contract_count": "계약 수 (건)"}),
                                key="ov_contract_types_table", label="유형별 계약 특성",
                                fit_container=True,
                                widths={"유형": 64, "계약 수 (건)": 110, "평균 계약금액 (억원)": 148, "계약금액 (억원)": 150},
                                numeric_columns=("계약 수 (건)", "계약금액 (억원)", "평균 계약금액 (억원)"))
            st.caption("평균 계약금액은 총금액을 계약 수로 나눈 값입니다. 외자는 통화가 달라 원화 비교에서 제외합니다. 이 집계는 단가계약과 총액계약을 구분하지 않으므로, 이 평균만으로 건별 구매 규모를 판단할 수 없습니다.")
    period = f"{years[0]}~{years[1]}년" if years is not None else "게시 전체 기간"
    scope = f"기관별 집계표 기준: {period} · 선택 조달 유형의 연도별 계약 건수를 기관코드별로 합산합니다. 분류·수요기관·지역·금액·낙찰/유찰 필터는 적용되지 않습니다. 기관별 표에는 분류가 연결되지 않은 계약도 포함되므로, 분류가 있는 계약만 집계한 위 그래프와 합계가 다를 수 있습니다."
    with card("계약기관별 계약 건수", scope):
        required = {"year"} if years is not None else set()
        if types is not None:
            required.add("procurement_type")
        if not required.issubset(institutions.columns):
            st.info("기관 집계에 연도·조달 유형 자료가 없어 선택 조건을 적용할 수 없습니다.")
            return
        inst = institution_contract_counts(institutions, years=years, types=types, names=names)
        if inst.empty:
            st.info("선택 기간·유형의 계약기관별 계약 건수가 없습니다.")
            return
        labels = dict(zip(inst.agency_code, inst.agency_name))
        options = inst.loc[inst.agency_code.ne(""), "agency_code"].drop_duplicates().tolist()
        if "contract_pattern_agencies" in st.session_state:
            st.session_state.contract_pattern_agencies = [code for code in st.session_state.contract_pattern_agencies if code in options]
        selected = st.multiselect("계약기관 선택", options,
                                  format_func=lambda code: labels[code] if labels[code].startswith("기관명 미제공") else f"{labels[code]} ({code})",
                                  key="contract_pattern_agencies")
        inst = inst[inst.agency_code.isin(selected)] if selected else inst
        display = inst.rename(columns={"agency_name": "계약기관", "agency_code": "기관코드", "contract_count": "계약 수 (건)"}).set_index("계약기관")
        reference_table(display, key="ov_contract_agencies_table", label="계약기관별 계약 건수",
                        formats={"계약 수 (건)": "integer"},
                        height=400, numeric_columns=("계약 수 (건)",))
        unknown = inst.agency_name.str.startswith("기관명 미제공").sum() + inst.agency_name.eq("기관명·코드 미제공").sum()
        st.caption(f"기관명이 확인되지 않은 곳은 {unknown}곳이며, 기관코드로 표시합니다. 기관명은 정확히 일치하는 코드로만 연결합니다.")
        st.caption("계약을 체결한 기관의 계약 건수입니다. 수요기관과 다를 수 있으며, 기관 이름만으로 국방 조달 대상 여부나 계약 성향을 판단하지 않습니다.")
