"""원천 읽기 — 파일과 MySQL에 닿는 유일한 곳.

고객 화면은 기본으로 MySQL `defense_analysis`의 게시 지표를 읽는다.
테스트와 명시적 오프라인 점검에서는 `FRONTLINE_DATA_SOURCE=eda_csv`로 CSV를 쓸 수 있다.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
EDA_DIR = Path(os.environ.get("FRONTLINE_EDA_DIR", REPO_ROOT / "data" / "EDA"))
ALLOWLIST_DIR = Path(os.environ.get("FRONTLINE_ALLOWLIST_DIR", REPO_ROOT / "data" / "allowlist"))
def _configured_source() -> str:
    """Cloud만 Secrets로 원천을 선택한다. 로컬 기본 MySQL은 유지한다."""
    if "FRONTLINE_DATA_SOURCE" in os.environ:
        return os.environ["FRONTLINE_DATA_SOURCE"]
    try:
        return st.secrets.get("dashboard", {}).get("data_source", "mysql")
    except FileNotFoundError:
        return "mysql"


SOURCE = _configured_source()

# 공고는 매시간, 통계는 게시 버전이 바뀔 때만 달라진다는 가정에 맞춘 캐시 시간
NOTICE_TTL = "10m"
STATS_TTL = "1h"

# 사용자 입력값으로 테이블 이름을 만들지 않는다. 요청 파일명은 이 allowlist만 통과한다.
MYSQL_TABLES = {
    "mart_procurement_overview.csv": "mart_procurement_overview",
    "latest_ytd_overview.csv": "latest_ytd_overview",
    "mart_category_market.csv": "mart_category_market",
    "latest_ytd_market.csv": "latest_ytd_market",
    "category_catalog.csv": "category_catalog",
    "mart_supplier_structure.csv": "mart_supplier_structure",
    "mart_lifecycle.csv": "mart_lifecycle",
    "h05_monthly_monitoring.csv": "h05_monthly_monitoring",
    "mart_institution.csv": "mart_institution",
    "mart_notice_eligibility.csv": "mart_notice_eligibility",
    "link_quality.csv": "link_quality",
    "detail_coverage.csv": "detail_coverage",
    "mart_data_quality.csv": "mart_data_quality",
}

PUBLISHED_TABLES = tuple(MYSQL_TABLES.values())


def _query_mysql(query: str) -> pd.DataFrame:
    """Streamlit이 관리하는 SQLAlchemy 연결로 읽기 전용 SELECT를 실행한다."""
    conn = st.connection("mysql", type="sql", max_entries=1)
    return conn.query(query, ttl=0, show_spinner=False)


def _mysql_query_for(name: str) -> str:
    """실제 스키마의 열 차이를 대시보드 데이터 계약에 맞춘 SQL."""
    if name == "mart_notice_eligibility.csv":
        # 요건 요약 뷰는 복합 조인 때문에 4개 공고 키에서 같은 행이 두 번 나온다.
        # 사전 확인에서 중복 행의 면허·지역·URL 값은 모두 같았으므로 키별로 1행만 만든다.
        return """
            SELECT n.*,
                   n.bidClseDt AS bid_close_date,
                   c.classification_type,
                   c.category_value,
                   CASE WHEN n.license_state = '제한있음'
                        THEN COALESCE(v.required_licenses, '') ELSE '' END AS license_values,
                   CASE WHEN n.region_state = '제한있음'
                        THEN COALESCE(v.allowed_regions, '') ELSE '' END AS region_values,
                   v.detail_url AS eligibility_notice_url
            FROM mart_notice_eligibility AS n
            LEFT JOIN category_catalog AS c
              ON c.procurement_type = n.procurement_type AND c.item_code = n.item_code
            LEFT JOIN (
                SELECT bidNtceNo, bidNtceOrd,
                       MAX(required_licenses) AS required_licenses,
                       MAX(allowed_regions) AS allowed_regions,
                       MAX(bidNtceDtlUrl) AS detail_url
                FROM view_notice_license_region_summary
                GROUP BY bidNtceNo, bidNtceOrd
            ) AS v
              ON v.bidNtceNo = n.bidNtceNo AND v.bidNtceOrd = n.bidNtceOrd
        """
    if name == "mart_lifecycle.csv":
        # v5 라이프사이클에는 개찰별 낙찰금액·재절차 통합 열이 없다.
        # 낙찰 테이블은 표준 공고번호·차수·분류·재입찰 번호 키가 유일함을 확인했다.
        return """
            SELECT l.*,
                   a.sucsfbidAmt_num AS award_amount,
                   CASE WHEN COALESCE(l.rbid_num, 0) > 0 OR COALESCE(n.re_notice, 0) = 1
                        THEN 1 ELSE 0 END AS reprocedure
            FROM mart_lifecycle AS l
            LEFT JOIN final_award AS a
              ON a.bidNtceNo_std = l.bidNtceNo_std
             AND a.bidNtceOrd_std = l.bidNtceOrd_std
             AND a.bidClsfcNo_std = l.bidClsfcNo_std
             AND a.rbidNo_std = l.rbidNo_std
            LEFT JOIN mart_notice_eligibility AS n
              ON n.notice_id = l.notice_id
        """
    table = MYSQL_TABLES.get(name)
    if table is None:
        raise ValueError(f"DB에서 읽도록 등록되지 않은 자료입니다: {name}")
    return f"SELECT * FROM `{table}`"


def read_table(name: str) -> pd.DataFrame:
    """지정된 대시보드 표를 CSV 또는 게시된 MySQL 마트에서 읽는다."""
    if SOURCE == "mysql":
        return _query_mysql(_mysql_query_for(name))
    if SOURCE == "api":
        if name not in MYSQL_TABLES:
            raise ValueError("API에서 읽도록 등록되지 않은 자료입니다.")
        return _api_client().table(name)
    if SOURCE == "eda_csv":
        path = EDA_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"{path} 가 없습니다. FRONTLINE_EDA_DIR 설정을 확인하세요.")
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=True)
    raise ValueError("FRONTLINE_DATA_SOURCE는 'mysql', 'api', 'eda_csv'여야 합니다.")


def _api_client():
    from service.api_transport import DataAPIClient

    try:
        config = st.secrets.get("data_api", {})
    except FileNotFoundError:
        config = {}
    return DataAPIClient(
        os.environ.get("FRONTLINE_API_URL", config.get("url", "")),
        os.environ.get("FRONTLINE_API_TOKEN", config.get("token", "")),
    )


def read_metadata() -> dict:
    """DB 게시 버전과 대시보드 핵심 테이블의 버전 일관성을 읽는다."""
    if SOURCE == "api":
        return _api_client().metadata()
    if SOURCE == "mysql":
        return mysql_metadata(_query_mysql)
    if SOURCE != "eda_csv":
        raise ValueError("FRONTLINE_DATA_SOURCE는 'mysql', 'api', 'eda_csv'여야 합니다.")
    path = EDA_DIR / "통합실행_metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def mysql_metadata(query) -> dict:
    """로컬과 API가 동일한 게시 버전 검사·메타데이터 계약을 사용한다."""
    versions = []
    for table in PUBLISHED_TABLES:
        row = query(
            f"SELECT run_id, data_version, metric_version, data_as_of "
            f"FROM `{table}` LIMIT 1"
        )
        if row.empty:
            versions.append((table, None))
        else:
            values = row.iloc[0].tolist()
            versions.append((table, tuple(str(v) for v in values)))

    populated = [version for _, version in versions if version is not None]
    version_consistent = len(populated) == len(PUBLISHED_TABLES) and len(set(populated)) == 1
    version = populated[0] if populated else (None, None, None, None)
    basis = query("SELECT DISTINCT contract_population_basis FROM mart_category_market LIMIT 1")
    contract_basis = basis.iloc[0, 0] if not basis.empty else ""
    return {
        "run_id": version[0],
        "snapshot_id": version[0],
        "data_version": version[1],
        "metric_version": version[2],
        "data_as_of": version[3],
        "contract_population_basis": contract_basis,
        "version_consistent": version_consistent,
        "required_tables_present": len(populated) == len(PUBLISHED_TABLES),
    }


def read_pending_institutions(cols: list[str]) -> pd.DataFrame:
    """기관 판정 대기 목록(읽기 전용). 운영 원천은 S3 `reference/institutions/Allowlist_Pending.xlsx`.
    프로토타입은 로컬 사본이 있으면 읽고, 없으면 빈 표."""
    path = ALLOWLIST_DIR / "Allowlist_Pending.xlsx"
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_excel(path, dtype=str)


def read_defense_institutions() -> pd.DataFrame:
    """공개 안내용 프로젝트 판정 대장. 로컬 사본만 읽으며 S3·대장은 수정하지 않는다."""
    if SOURCE == "api":
        return _api_client().table("defense_institutions")
    return read_local_defense_institutions()


def read_local_defense_institutions() -> pd.DataFrame:
    """게이트웨이/로컬 화면 공통 목록 읽기. API 모드에서도 재귀 호출하지 않는다."""
    path = ALLOWLIST_DIR / "Allowlist_Y_Master.xlsx"
    df = pd.read_excel(path, dtype=str)
    df.attrs["source"] = path.name
    df.attrs["modified_at"] = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return df


def read_automatic_institutions() -> pd.DataFrame:
    """자동 판정 Y/N 확인용 로컬 파일만 읽는다. 최신 S3 상태를 대신하지 않는다."""
    frames = []
    for path in sorted((ALLOWLIST_DIR / "new_institutions").glob("신규기관_*.xlsx")):
        frame = pd.read_excel(path, dtype=str)
        frame["source_file"] = path.name
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["institution_code", "institution_name_raw", "is_defense", "classification_reason", "source_file"])
    result = pd.concat(frames, ignore_index=True)
    result = result[result.is_defense.isin(["Y", "N"])]
    return result.drop_duplicates(["institution_code", "is_defense", "classification_reason"], keep="last").reset_index(drop=True)
