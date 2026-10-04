"""데이터 기준 화면의 읽기 전용 결과 표시. 원본 점검 값은 바꾸지 않는다."""

import pandas as pd
import streamlit as st


def check_status(value) -> str:
    """문자열 False·빈 값 등을 참으로 오인하지 않고 명시된 결과만 표시한다."""
    if pd.isna(value):
        return ":orange-badge[확인 필요]"
    token = str(value).strip().casefold()
    if token in {"true", "1", "1.0"}:
        return ":green-badge[통과]"
    if token in {"false", "0", "0.0"}:
        return ":red-badge[실패]"
    return ":orange-badge[확인 필요]"


def checks_for_display(frame: pd.DataFrame) -> pd.DataFrame:
    shown = frame.copy().rename(columns={"검사": "검사 항목", "통과": "점검 결과"})
    if "점검 결과" in shown:
        shown["점검 결과"] = shown["점검 결과"].map(check_status)
    return shown


def csv_download(frame: pd.DataFrame, name: str, key: str):
    """표와 같은 원본 행·열을 Excel에서도 읽을 수 있는 UTF-8 BOM CSV로 제공한다."""
    st.download_button("CSV 다운로드", frame.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{name}.csv", mime="text/csv", key=key,
                       icon=":material/download:", on_click="ignore", width="content")
