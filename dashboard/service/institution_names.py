"""계약기관 이름 표시 전용 명부. 판정·분석 대상 선정에는 사용하지 않는다."""
import pandas as pd
from service.source import read_contract_institution_names


def contract_institution_names(defense_names: pd.DataFrame) -> pd.DataFrame:
    """현재 검토 완료 이름 우선, 빠진 코드만 출처가 기록된 과거 명부로 보완한다."""
    names = defense_names[["기관코드", "기관명"]].copy()
    records = read_contract_institution_names()
    extra = pd.DataFrame(list(records.items()), columns=["기관코드", "기관명"])
    extra = extra[~extra["기관코드"].isin(names["기관코드"].dropna().astype(str).str.strip())]
    return pd.concat([names, extra], ignore_index=True)
