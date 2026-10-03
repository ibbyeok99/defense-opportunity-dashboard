"""원천 읽기 — 파일과 MySQL에 닿는 유일한 곳.

고객 화면은 기본으로 MySQL `defense_analysis`의 게시 지표를 읽는다.
테스트와 명시적 오프라인 점검에서는 `FRONTLINE_DATA_SOURCE=eda_csv`로 CSV를 쓸 수 있다.
"""

from __future__ import annotations

import json
import os
import hashlib
import uuid
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


def requirement_evidence_directory() -> Path:
    return REPO_ROOT / "data" / "dashboard_requirement_evidence"


@st.cache_data(ttl=60, max_entries=2, show_spinner=False)
def read_requirement_evidence(*, include_expired=False) -> list[dict]:
    """공개 근거 보완 사본만 읽는다. 잘못된 파일은 요건으로 사용하지 않는다."""
    from service.requirement_overlay import fresh, prepare
    records = {}
    directory = requirement_evidence_directory()
    if not directory.exists():
        return []
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if not include_expired and not fresh(value):
                continue
            value = prepare(value, value["procurement_type"])
            key = (value["procurement_type"], value["notice_number"], value["notice_order"])
            if key not in records or value["checked_at"] > records[key]["checked_at"]:
                records[key] = value
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return list(records.values())


@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def read_api_requirement_evidence() -> list[dict]:
    """목록에서 재사용할 공식 API 값만 읽는다. 문서 추출/구조화는 실행하지 않는다."""
    from service.requirement_overlay import fresh, prepare
    records = {}
    directory = requirement_evidence_directory()
    if not directory.exists():
        return []
    for path in directory.glob('*.json'):
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            raw = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or raw.get('error') or not fresh(raw):
                continue
            if any(not isinstance(raw.get('api_' + kind + '_rows', []), list) or
                   any(not isinstance(row, dict) for row in raw.get('api_' + kind + '_rows', []))
                   for kind in ('license', 'region')):
                continue
            key = (raw['procurement_type'], raw['notice_number'], raw['notice_order'])
            value = {field: raw[field] for field in ('schema','notice_number','notice_order','checked_at',
                'api_license_rows','api_region_rows','notice_flags','notice_facts') if field in raw}
            value.update(evidence=[], sources=[], warnings=[], api_only=True)
            if key not in records or raw['checked_at'] > records[key]['checked_at']:
                records[key] = prepare(value, raw['procurement_type'])
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return list(records.values())


def save_requirement_evidence(result: dict, procurement_type: str) -> dict:
    """원본 DB가 아닌 별도 공개 근거 저장소. 검사 시각별 사본을 원자적으로 남긴다."""
    from service.requirement_overlay import prepare
    value = prepare(result, procurement_type)
    allowed = {"schema", "notice_number", "notice_order", "checked_at", "evidence", "sources",
               "warnings", "api_license_rows", "api_region_rows", "procurement_type", "overlay_schema", "resolved",
               "notice_flags", "notice_facts", "structured", "coverage", "attachment_inventory_complete", "source_fingerprint", "detail_fingerprint"}
    value = {k: v for k, v in value.items() if k in allowed}
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(payload.encode("utf-8")) > 1024 * 1024 or "serviceKey" in payload:
        raise ValueError("근거 저장 크기·비밀값 검사를 통과하지 못했습니다")
    directory = requirement_evidence_directory()
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    target = directory / (digest + ".json")
    if not target.exists():
        temporary = directory / (uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    read_requirement_evidence.clear()
    read_api_requirement_evidence.clear()
    return value


def read_requirement_failures():
    """자격 보완값과 분리한 실패 이력. 원문 오류·비밀값은 저장하지 않는다."""
    from service.requirement_overlay import identity
    directory = requirement_evidence_directory() / 'failures'
    records = []
    for path in directory.glob('*.json'):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            identity(value)
            if value.get('stage') in {'응답 시간 초과', '조회 실패'}:
                records.append(value)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return records




def requirement_queue_path():
    return requirement_evidence_directory() / 'queue' / 'state.json'


def read_requirement_queue():
    from service.requirement_queue import empty_state, validate_state
    path = requirement_queue_path()
    if not path.exists():
        return empty_state()
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('요건 체크포인트 크기 한도 초과. 초기화/전체 재조회 금지')
    try:
        return validate_state(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        raise ValueError('요건 체크포인트 읽기 실패. 파일을 보존하고 원인을 확인하세요.') from None


def save_requirement_queue(value):
    from service.requirement_queue import validate_state
    validate_state(value)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(payload.encode()) > 20 * 1024 * 1024 or 'serviceKey' in payload:
        raise ValueError('요건 체크포인트 크기/비밀값 검사 실패')
    path = requirement_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(payload, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_requirement_watch():
    from service.requirement_watch import validate_watch
    path = requirement_queue_path().with_name('watch.json')
    if not path.exists():
        return None
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('신규 감지 상태 크기 한도 초과. 자동 초기화 금지')
    return validate_watch(json.loads(path.read_text(encoding='utf-8')))


def save_requirement_watch(value):
    from service.requirement_watch import validate_watch
    payload = json.dumps(validate_watch(value), ensure_ascii=False, sort_keys=True)
    if len(payload.encode('utf-8')) > 20 * 1024 * 1024 or 'serviceKey' in payload:
        raise ValueError('신규 감지 상태 크기/비밀값 검사 실패')
    path = requirement_queue_path().with_name('watch.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(payload, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def requirement_queue_lock():
    """같은 호스트에서 단일 worker만 허용. 다른 프로세스의 잠금을 강제 해제하지 않는다."""
    from contextlib import contextmanager

    @contextmanager
    def locked():
        path = requirement_queue_path().with_suffix('.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as handle:
            if path.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError('다른 요건 worker가 실행 중입니다. 동시에 조회하지 않습니다.') from None
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return locked()


def save_requirement_failure(number, order, procurement_type, *, timeout=False):
    from datetime import timezone
    from service.requirement_overlay import identity
    value = dict(notice_number=number, notice_order=order, procurement_type=procurement_type,
                 checked_at=datetime.now(timezone.utc).isoformat(),
                 stage='응답 시간 초과' if timeout else '조회 실패')
    identity(value)
    directory = requirement_evidence_directory() / 'failures'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (uuid.uuid4().hex + '.json')
    target.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return value


def read_product_name_reference() -> dict:
    """공식 API 읽기 조회로 검증한 공개 품명 사본. 화면 실행 시 API 키를 쓰지 않는다."""
    path = Path(__file__).resolve().parents[1] / "assets" / "reference" / "product8_official_names.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _query_mysql(query: str) -> pd.DataFrame:
    """Streamlit이 관리하는 SQLAlchemy 연결로 읽기 전용 SELECT를 실행한다."""
    from sqlalchemy import text
    conn = st.connection("mysql", type="sql", max_entries=1)
    # Streamlit 1.64.0의 conn.query는 connect()의 반환 연결을 닫지 않는다.
    # 반복 점검에서 pool(5+10)이 고갈됨을 확인했다. 상위 표 캐시는 그대로 유지한다.
    with conn.connect() as connection:
        return pd.read_sql(text(query), connection)


def _mysql_query_for(name: str) -> str:
    """실제 스키마의 열 차이를 대시보드 데이터 계약에 맞춘 SQL."""
    if name == "mart_notice_eligibility.csv":
        from service.notice_projection import notice_select_columns
        # 요건 요약 뷰는 복합 조인 때문에 4개 공고 키에서 같은 행이 두 번 나온다.
        # 사전 확인에서 중복 행의 면허·지역·URL 값은 모두 같았으므로 키별로 1행만 만든다.
        return f"""
            SELECT {notice_select_columns()},
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
    versions, states = [], {}
    for table in PUBLISHED_TABLES:
        try:
            row = query(
                f"SELECT run_id, data_version, metric_version, data_as_of "
                f"FROM `{table}` LIMIT 1"
            )
        except Exception:
            versions.append((table, None))
            states[table] = '조회 실패'
            continue
        if row.empty:
            versions.append((table, None))
            states[table] = '게시 행 없음'
        else:
            values = row.iloc[0].tolist()
            if len(values) != 4 or any(pd.isna(v) or str(v).strip() in {'','None','nan','NaT'} for v in values):
                versions.append((table, None))
                states[table] = '버전 값 미확인'
            else:
                versions.append((table, tuple(str(v) for v in values)))
                states[table] = '버전 확인'

    populated = [version for _, version in versions if version is not None]
    version_consistent = (False if len(set(populated)) > 1 else
                          True if len(populated) == len(PUBLISHED_TABLES) else None)
    version = populated[0] if populated else (None, None, None, None)
    try:
        basis = query("SELECT DISTINCT contract_population_basis FROM mart_category_market LIMIT 1")
        contract_basis = basis.iloc[0, 0] if not basis.empty else ""
    except Exception:
        contract_basis = ''
    return {
        "run_id": version[0],
        "snapshot_id": version[0],
        "data_version": version[1],
        "metric_version": version[2],
        "data_as_of": version[3],
        "contract_population_basis": contract_basis,
        "version_consistent": version_consistent,
        "version_status": '일치' if version_consistent is True else '불일치' if version_consistent is False else '미확인',
        "table_version_states": states,
        "table_versions": {table: value for table,value in versions},
        "required_tables_present": len(populated) == len(PUBLISHED_TABLES),
    }


def read_pending_institutions(cols: list[str]) -> pd.DataFrame:
    """기관 판정 대기 목록(읽기 전용). 운영 원천은 S3 `reference/institutions/Allowlist_Pending.xlsx`.
    프로토타입은 로컬 사본이 있으면 읽고, 없으면 빈 표."""
    path = ALLOWLIST_DIR / "Allowlist_Pending.xlsx"
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_excel(path, dtype=str)


def read_contract_institution_names() -> dict[str, str]:
    """게시 계약기관의 이름만 보완하는 코드 명부. 기관 판정에는 사용하지 않는다."""
    path = REPO_ROOT / "dashboard/assets/reference/contract_agency_names.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), dict):
        raise ValueError("계약기관 이름 명부의 형식을 확인해야 합니다.")
    records = payload["records"]
    if any(not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip()
           for code, name in records.items()):
        raise ValueError("계약기관 이름 명부에 빈 코드·이름이 있습니다.")
    return records


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


def read_historical_institution_codes() -> frozenset[str]:
    """과거 검토 완료 기관의 코드 집합. 현재 운영 대장은 기준에 섞지 않는다."""
    codes = set()
    for relative in ("TRY02/result/defense_institution_whitelist_try02_all.csv",
                     "TRY01/result/defense_institution_whitelist_final.csv"):
        frame = pd.read_csv(ALLOWLIST_DIR / relative, dtype=str, usecols=["institution_code"])
        values = frame["institution_code"].dropna().str.strip()
        values = values[values.ne("")]
        if values.empty:
            raise ValueError("과거 기관 검토 기준 목록이 비어 있습니다.")
        codes.update(values)
    return frozenset(codes)


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


def requirement_service_key() -> str:
    """공식 공고 API 읽기 전용 설정. 비밀값을 반환 결과·기록에 저장하지 않는다."""
    value = os.environ.get("G2B_SERVICE_KEY") or os.environ.get("G2B_CNTRCT_SERVICE_KEY")
    if value:
        return value.strip()
    try:
        value = st.secrets.get("g2b", {}).get("service_key", "")
    except FileNotFoundError:
        value = ""
    if value:
        return str(value).strip()
    env = REPO_ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("G2B_CNTRCT_SERVICE_KEY="):
                return line.split("=", 1)[1].split(" #", 1)[0].strip().strip('"\'')
    return ""
