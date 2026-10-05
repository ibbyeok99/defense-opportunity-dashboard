"""원천 읽기 — 파일과 MySQL에 닿는 유일한 곳.

고객 화면은 기본으로 MySQL `defense_analysis`의 게시 지표를 읽는다.
테스트와 명시적 오프라인 점검에서는 `FRONTLINE_DATA_SOURCE=eda_csv`로 CSV를 쓸 수 있다.
"""

from __future__ import annotations

import json
import os
import hashlib
import uuid
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from service import admin_access

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


def _evidence_input_hash(value):
    import pickle
    return hashlib.sha256(pickle.dumps(value, protocol=5)).hexdigest()


@st.cache_data(ttl=NOTICE_TTL, max_entries=2, show_spinner=False, hash_funcs={list: _evidence_input_hash})
def _prepare_requirement_records(records, processing_version):
    """최신 원문이 같으면 의미 해석을 재사용한다. 사본·규칙 변경은 전체 입력 키로 구분한다."""
    from service.requirement_overlay import prepare
    prepared = []
    for value in records:
        try:
            prepared.append(prepare(value, value['procurement_type']))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return prepared


@st.cache_data(ttl=60, max_entries=2, show_spinner=False)
def read_requirement_evidence(*, include_expired=False, legacy_only=False) -> list[dict]:
    """공고별 최신 사본만 해석한다. 과거 사본은 보존하고 잘못된 파일은 사용하지 않는다."""
    if SOURCE == 'api':
        return [] if include_expired or legacy_only else _api_client().stored_requirements()
    import re
    from service.requirement_overlay import fresh, identity
    records = {}
    directory = requirement_evidence_directory()
    if not directory.exists():
        return []
    preferred = {}
    for index in (directory / 'latest').glob('*.json'):
        try:
            if index.stat().st_size > 2048:
                continue
            filename = json.loads(index.read_text(encoding='utf-8')).get('file', '')
            if re.fullmatch(r'(?:public_)?[0-9a-f]{64}\.json', filename):
                preferred[index.stem] = filename
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    for path in directory.glob("*.json"):
        if legacy_only and path.name.startswith('public_'):
            continue
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if not include_expired and not fresh(value):
                continue
            if not isinstance(value, dict) or value.get('error'):
                continue
            key = identity(value)
            stamp = value['checked_at']
            priority = (stamp, preferred.get(hashlib.sha256('|'.join(key).encode()).hexdigest()) == path.name)
            if key not in records or priority > records[key][0]:
                records[key] = (priority, value)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    from service.notice_requirements import SCHEMA
    return _prepare_requirement_records([value for _, value in records.values()], SCHEMA)


@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def read_api_requirement_evidence() -> list[dict]:
    """목록에서 재사용할 공식 API 값만 읽는다. 문서 추출/구조화는 실행하지 않는다."""
    if SOURCE == 'api':
        return _api_client().api_requirements()
    from service.requirement_overlay import fresh, prepare
    records = {}
    directory = requirement_evidence_directory()
    if not directory.exists():
        return []
    for path in directory.glob('*.json'):
        # 전수 원문 사본이 늘어도 일반 목록은 본문 JSON을 열지 않는다.
        # 과거 무접두사 사본은 아래 input_mode 검사로 계속 안전하게 제외한다.
        if path.name.startswith('public_'):
            continue
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            raw = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or raw.get('error') or not fresh(raw):
                continue
            # 공개 화면/첨부 사본은 API 조회가 아니다. 새 빈 API 행으로 이전의
            # 유효한 API 확인값을 목록에서 지우지 않는다.
            if raw.get('input_mode') == '저장 API 재사용':
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


def read_requirement_checkpoint_evidence(state):
    """별도 전수 처리기의 재개용. 이미 처리된 사본은 전문 재해석 없이 메타만 읽는다."""
    from service.requirement_overlay import identity,prepare
    records={}
    known=state.get('jobs',{})
    for path in requirement_evidence_directory().glob('*.json'):
        try:
            if path.stat().st_size > 1024*1024:
                continue
            raw=json.loads(path.read_text(encoding='utf-8'))
            key='|'.join(identity(raw))
            if raw.get('error'):
                continue
            value=({k:raw[k] for k in ('procurement_type','notice_number','notice_order',
                    'checked_at','overlay_schema','source_fingerprint') if k in raw}
                   if key in known else prepare(raw,raw['procurement_type']))
            if key not in records or value['checked_at'] > records[key]['checked_at']:
                records[key]=value
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            continue
    return list(records.values())


def save_requirement_evidence(result: dict, procurement_type: str) -> dict:
    """원본 DB가 아닌 별도 공개 근거 저장소. 검사 시각별 사본을 원자적으로 남긴다."""
    from service.requirement_overlay import prepare
    value = prepare(result, procurement_type)
    from service.requirement_display_audit import display_issues
    if display_issues(value):
        raise ValueError('조건 값·요약의 원문/HTML/장문 혼입. 저장하지 않고 표시를 재검토합니다.')
    allowed = {"schema", "notice_number", "notice_order", "checked_at", "evidence", "sources",
               "warnings", "api_license_rows", "api_region_rows", "procurement_type", "overlay_schema", "resolved",
               "notice_flags", "notice_facts", "structured", "coverage", "attachment_inventory_complete", "source_fingerprint", "detail_fingerprint",
               "public_page", "input_mode", "repair_review", "automation"}
    value = {k: v for k, v in value.items() if k in allowed}
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(payload.encode("utf-8")) > 1024 * 1024 or "serviceKey" in payload:
        raise ValueError("근거 저장 크기·비밀값 검사를 통과하지 못했습니다")
    directory = requirement_evidence_directory()
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    prefix = 'public_' if value.get('input_mode') == '저장 API 재사용' else ''
    target = directory / (prefix + digest + ".json")
    if not target.exists():
        temporary = directory / (uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    _index_requirement_evidence(value, target.name)
    read_requirement_evidence.clear()
    read_api_requirement_evidence.clear()
    return value


def _index_requirement_evidence(value, filename):
    """공고별 최신 사본의 파일명만 별도 색인. 원문 중복 저장/DB 변경 없음."""
    from service.requirement_overlay import identity
    key = '|'.join(identity(value))
    folder = requirement_evidence_directory() / 'latest'
    folder.mkdir(parents=True,exist_ok=True)
    path = folder / (hashlib.sha256(key.encode()).hexdigest()+'.json')
    # UI와 별도 처리기가 같은 공고를 저장해도 오래된 결과가 최신을 덮지 않는다.
    with path.with_suffix('.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        try:
            if path.exists():
                try:
                    previous=json.loads(path.read_text(encoding='utf-8'))
                    if previous.get('checked_at','') > value['checked_at']:
                        return
                except (OSError,ValueError,TypeError,AttributeError):
                    pass  # 사본은 별도 불변 파일이므로 손상된 색인만 재생성한다.
            temporary=folder/(uuid.uuid4().hex+'.tmp')
            try:
                temporary.write_text(json.dumps(dict(file=filename,checked_at=value['checked_at'])),encoding='utf-8')
                os.replace(temporary,path)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def read_notice_requirement_evidence(procurement_type,number,order):
    """상세/즐겨찾기는 해당 공고의 최신 사본 한 개만 읽고 해석한다."""
    import re
    from service.requirement_overlay import identity, fresh, prepare
    key=identity(dict(procurement_type=procurement_type,notice_number=number,notice_order=order))
    directory=requirement_evidence_directory()
    index=directory/'latest'/(hashlib.sha256('|'.join(key).encode()).hexdigest()+'.json')
    if index.exists():
        try:
            if index.stat().st_size > 2048:
                raise ValueError('근거 색인 크기 오류')
            pointer=json.loads(index.read_text(encoding='utf-8'))
            filename=pointer.get('file','')
            if not re.fullmatch(r'(?:public_)?[0-9a-f]{64}\.json',filename):
                raise ValueError('근거 색인 파일명 오류')
            path=directory/filename
            if path.stat().st_size > 1024*1024:
                raise ValueError('근거 사본 크기 오류')
            raw=json.loads(path.read_text(encoding='utf-8'))
            if identity(raw)!=key:
                raise ValueError('근거 색인 공고 불일치')
            return prepare(raw,procurement_type) if fresh(raw) else None
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            pass  # 잘못된 색인을 조건으로 쓰지 않는다. 기존 검증된 사본 읽기로 복구.
    # 색인 도입 전 사본만 기존 60초 캐시로 읽는다. 새 저장은 모두 색인한다.
    return next((r for r in read_requirement_evidence(legacy_only=True) if identity(r)==key),None)


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


@admin_access.api_guard
@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def read_collector_operations():
    """운영 대장 GetObject·성공 로그 FilterLogEvents만 사용. 실패를 0으로 바꾸지 않는다."""
    if SOURCE == 'api':
        from service.admin_transport import client
        from service.api_transport import DataAPIError
        try:
            return client().read('operations')
        except DataAPIError:
            from zoneinfo import ZoneInfo
            return dict(checked_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
                        errors=['관리자 API 운영 상태 확인 실패'], last_success=None,
                        repair_pending=None, judgment_pending=None, isolated_rows=None, repair_given_up=None)
    from zoneinfo import ZoneInfo
    from io import BytesIO
    from service import automatic_review
    from service.operations import read_last_success, state_counts
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    value = dict(checked_at=now.isoformat(), errors=[], last_success=None,
                 repair_pending=None, judgment_pending=None, isolated_rows=None, repair_given_up=None)
    if os.environ.get('FRONTLINE_REVIEW_BACKEND') == 'offline':
        value['errors'] = ['오프라인 검증: 운영 연결 안 함']
        return value
    try:
        s3 = automatic_review.client()
        def read(key, maximum):
            response = s3.get_object(Bucket=automatic_review.bucket(), Key=key)
            body = response['Body']
            try:
                if response.get('ContentLength', maximum+1) > maximum:
                    raise ValueError('대장 크기 한도 초과')
                payload = body.read(maximum+1)
                if len(payload) > maximum:
                    raise ValueError('대장 크기 한도 초과')
                return payload
            finally:
                body.close()
        state = json.loads(read('state/pipeline_state.json', 32*1024*1024))
        pending = pd.read_excel(BytesIO(read('reference/institutions/Allowlist_Pending.xlsx', 5*1024*1024)), dtype=str)
        value.update(state_counts(state, pending))
    except Exception:
        value['errors'].append('운영 상태/판정 대장 확인 실패')
    try:
        logs = automatic_review.client('logs')
        value['last_success'] = read_last_success(logs, os.environ.get(
            'FRONTLINE_COLLECTOR_LOG_GROUP', '/ecs/frontline-g2b-dev-collector'), now)
    except Exception:
        value['errors'].append('수집 성공 로그 확인 실패')
    return value


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
        # Windows에서는 짧은 읽기 중에도 파일 교체가 거절될 수 있다.
        # 원본을 지우지 않고 같은 임시 파일의 원자적 교체만 제한적으로 재시도한다.
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.05 * (2 ** attempt))
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


_BLANK_TOKENS = {'', 'none', 'nan', 'nat'}
# 행의 run_id는 "그 묶음을 계산한 실행"(생성 세대), 소유 대장·적재 이력의 run_id는 "DB에 적재한 실행"(적재 세대)일 수 있다.
# 변하지 않은 파일은 이전 실행의 파일 참조를 유지하므로 두 값이 다른 것이 정상 규약일 수 있다
# (docs/데이터_전처리/전처리A/S3_정제_지표_JSON_운영연결.md 5절). 매니페스트의 파일 참조·해시·행 수로 대응을 검증하기 전까지는
# 이 대조로 정상/실패를 판정하지 않는다. 검증을 마치면 True로 바꾼다.
LEDGER_CONVENTION_VERIFIED = False
_OWNERSHIP_FIELDS = ('no_ledger_record', 'ledger_run_differs', 'row_count_differs', 'row_run_not_in_load_ledger')


def _clean_value(value):
    """빈 값·NaN·NaT를 None으로 통일한다. 값을 추정해 채우지 않는다."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return None if text.casefold() in _BLANK_TOKENS else text


def _recorded_time(value):
    """DB에 기록된 시각을 시간대 변환 없이 그대로 읽는다. 해석할 수 없으면 None."""
    text = _clean_value(value)
    if text is None:
        return None
    stamp = pd.to_datetime(text, errors='coerce')
    if pd.isna(stamp):
        return None
    return stamp.tz_localize(None) if stamp.tzinfo is not None else stamp


def _time_text(stamp) -> str | None:
    return None if stamp is None else stamp.strftime('%Y-%m-%dT%H:%M:%S')


def _count(value) -> int:
    try:
        return 0 if pd.isna(value) else int(float(value))
    except (TypeError, ValueError):
        return 0


def _table_generation_state(query, table):
    """한 표의 게시 세대(run_id·버전·자료 기준 시각)와 행 수를 모두 읽는다."""
    try:
        frame = query(
            f"SELECT run_id, data_version, metric_version, data_as_of, COUNT(*) AS row_count "
            f"FROM `{table}` GROUP BY run_id, data_version, metric_version, data_as_of"
        )
    except Exception:
        return {'state': '조회 실패'}
    if frame.empty:
        return {'state': '게시 행 없음'}
    generations, unreadable = [], 0
    for record in frame.to_dict('records'):
        values = [_clean_value(record.get(name)) for name in ('run_id', 'data_version', 'metric_version', 'data_as_of')]
        stamp = _recorded_time(values[3]) if None not in values else None
        if None in values or stamp is None:
            unreadable += 1
            continue
        generations.append({'run_id': values[0], 'data_version': values[1], 'metric_version': values[2],
                            'as_of': stamp, 'as_of_text': values[3], 'rows': _count(record.get('row_count'))})
    if unreadable or not generations:
        return {'state': '버전 값 미확인'}
    latest = max(generations, key=lambda g: (g['as_of'], g['rows']))
    return {'state': '버전 확인', 'latest': latest,
            'summary': {'generations': len({g['run_id'] for g in generations}),
                        'rows': sum(g['rows'] for g in generations),
                        'as_of_min': _time_text(min(g['as_of'] for g in generations)),
                        'as_of_max': _time_text(max(g['as_of'] for g in generations))}}


def _ownership_check(query, table):
    """게시 행의 run_id와 소유 대장·적재 이력의 차이를 읽기 전용으로 센다(audit_published_data와 같은 질의).
    차이는 사실로만 기록하며, 생성 세대와 적재 세대의 대응 규약을 검증하기 전에는 오류로 해석하지 않는다."""
    try:
        frame = query(
            f"SELECT COUNT(*) AS partitions, SUM(p.partition_id IS NULL) AS no_ledger_record, "
            f"SUM(p.run_id <> a.run_id) AS ledger_run_differs, SUM(p.row_count <> a.actual_rows) AS row_count_differs, "
            f"SUM(r.run_id IS NULL OR r.status <> 'COMMITTED') AS row_run_not_in_load_ledger "
            f"FROM (SELECT _partition_id, run_id, COUNT(*) AS actual_rows FROM `{table}` "
            f"GROUP BY _partition_id, run_id) a "
            f"LEFT JOIN db_partition_ledger p ON p.partition_id = a._partition_id AND p.table_name = '{table}' "
            f"LEFT JOIN db_load_run_ledger r ON r.run_id = a.run_id"
        )
        if frame.empty:
            raise ValueError
        row = frame.iloc[0]
        return {'checked': True, 'partitions': _count(row['partitions']),
                **{name: _count(row[name]) for name in _OWNERSHIP_FIELDS}}
    except Exception:
        return {'checked': False}


def _is_zero(value) -> bool:
    return str(value).strip().casefold() in {'0', '0.0', 'false'}


def _read_ledger(query):
    """활성 적재 세대와 최근 반영 시각을 읽는다. 확인하지 못한 값은 비워 둔다(현재 시각으로 채우지 않는다)."""
    info = {'state': '확인 필요', 'reason': '', 'active_run_id': None, 'active_count': None,
            'last_applied_at': None, 'last_applied_run_id': None, 'last_applied_tables': None,
            'last_applied_rows': None, 'timezone': None}
    try:
        active = query("SELECT run_id, status, dry_run FROM db_load_run_ledger WHERE is_active = 'Y'")
        last = query("SELECT run_id, applied_at, total_tables, total_rows FROM db_load_run_ledger "
                     "WHERE status = 'COMMITTED' AND dry_run = 0 ORDER BY applied_at DESC LIMIT 1")
        clock = query("SELECT NOW() AS db_now, UTC_TIMESTAMP() AS utc_now")
    except Exception:
        info['reason'] = '적재 이력 조회 실패'
        return info
    info['active_count'] = int(len(active))
    if len(active) == 1:
        record = active.iloc[0]
        if str(record['status']).strip() == 'COMMITTED' and _is_zero(record['dry_run']):
            info['active_run_id'] = _clean_value(record['run_id'])
        else:
            info['reason'] = '활성 이력이 완료된 실제 적재가 아닙니다'
    else:
        info['reason'] = '활성 적재 이력이 없습니다' if active.empty else f'활성 적재 이력이 {len(active)}개입니다'
    if not last.empty:
        stamp = _recorded_time(last.iloc[0]['applied_at'])
        info['last_applied_at'] = _time_text(stamp)
        info['last_applied_run_id'] = _clean_value(last.iloc[0]['run_id'])
        info['last_applied_tables'] = _count(last.iloc[0]['total_tables'])
        info['last_applied_rows'] = _count(last.iloc[0]['total_rows'])
    try:
        offset = (_recorded_time(clock.iloc[0]['db_now']) - _recorded_time(clock.iloc[0]['utc_now']))
        hours = round(offset.total_seconds() / 3600)
        info['timezone'] = 'KST' if hours == 9 else f'UTC{hours:+d}'
    except Exception:
        info['timezone'] = None
    if info['active_run_id'] and info['last_applied_at']:
        info['state'] = '확인'
    elif not info['reason']:
        info['reason'] = '최근 반영 시각을 확인하지 못했습니다'
    return info


def _ledger_state(query):
    """적재 이력 응답 형식이 예상과 달라도 메타데이터 전체를 실패시키지 않고 '확인 필요'로 둔다."""
    try:
        return _read_ledger(query)
    except Exception:
        return {'state': '확인 필요', 'reason': '적재 이력 형식을 확인하지 못했습니다', 'active_run_id': None,
                'active_count': None, 'last_applied_at': None, 'last_applied_run_id': None,
                'last_applied_tables': None, 'last_applied_rows': None, 'timezone': None}


def mysql_metadata(query) -> dict:
    """로컬과 API가 동일한 게시 메타데이터 계약을 사용한다. 조회만 수행한다.

    통계는 변경된 파티션만 교체하므로 한 표에 여러 세대가 함께 있는 것이 정상이다. 표의 첫 행 하나가 아니라
    모든 세대를 읽어 자료 기준 시각의 범위를 만든다. 소유 대장·적재 이력과의 차이는 사실로만 기록하며,
    LEDGER_CONVENTION_VERIFIED가 True가 되기 전에는 정상/실패로 판정하지 않고 항상 '확인 필요'다.
    - 자료 기준 범위: 게시 통계 행의 data_as_of 최소~최대(시간대 변환 없음)
    - DB 최근 반영: 완료된 실제 적재 이력의 마지막 시각(변경분 0건 회차 포함)
    """
    states, versions, summaries, ownership = {}, {}, {}, {}
    problems, exceptions = [], []
    populated = []
    for table in PUBLISHED_TABLES:
        result = _table_generation_state(query, table)
        if result['state'] != '버전 확인':
            states[table] = result['state']
            versions[table] = None
            problems.append(table)
            continue
        latest = result['latest']
        versions[table] = (latest['run_id'], latest['data_version'], latest['metric_version'], latest['as_of_text'])
        summaries[table] = result['summary']
        populated.append(latest)
        check = _ownership_check(query, table)
        ownership[table] = check
        if not check['checked']:
            states[table] = '대장 확인 불가'
            problems.append(table)
        elif any(check[name] for name in _OWNERSHIP_FIELDS):
            states[table] = '대조 차이'      # 참고 신호. 오류가 아니다(생성 세대와 적재 세대는 다를 수 있다).
            exceptions.append((table, bool(check['no_ledger_record'] or check['row_count_differs'])))
        else:
            states[table] = '대조 일치'

    ledger = _ledger_state(query)
    try:
        basis = query("SELECT DISTINCT contract_population_basis FROM mart_category_market LIMIT 1")
        contract_basis = basis.iloc[0, 0] if not basis.empty else ""
    except Exception:
        contract_basis = ''

    # 규약 검증 전: 항상 '확인 필요'. 검증 후: 대장에 없거나 행 수가 다르면 실패, 세대 라벨 차이·조회 실패·이력 이상은 확인 필요.
    broken = LEDGER_CONVENTION_VERIFIED and any(hard for _, hard in exceptions)
    unverified = (not LEDGER_CONVENTION_VERIFIED or bool(problems) or any(not hard for _, hard in exceptions)
                  or ledger['state'] != '확인')
    version_consistent = False if broken else None if unverified else True
    mins = [s['as_of_min'] for s in summaries.values()]
    maxs = [s['as_of_max'] for s in summaries.values()]
    as_of_min, as_of_max = (min(mins), max(maxs)) if summaries else (None, None)
    newest = max(populated, key=lambda g: (g['as_of'], g['rows']), default=None)
    published_run = ledger['active_run_id']
    return {
        "run_id": published_run,
        "snapshot_id": published_run,
        "data_version": newest['data_version'] if newest else None,
        "metric_version": newest['metric_version'] if newest else None,
        # 호환용: 가장 최근 자료 기준. 전체가 이 시각까지 갱신됐다는 뜻이 아니다. 범위는 data_as_of_min/max.
        "data_as_of": as_of_max,
        "data_as_of_min": as_of_min,
        "data_as_of_max": as_of_max,
        "latest_generation_run_id": newest['run_id'] if newest else None,
        "contract_population_basis": contract_basis,
        "version_consistent": version_consistent,
        "version_status": '정상' if version_consistent is True else '실패' if version_consistent is False else '확인 필요',
        "mixed_generations": any(s['generations'] > 1 for s in summaries.values()),
        "table_version_states": states,
        "table_versions": versions,
        "table_generations": summaries,
        "ownership_checks": ownership,
        "ledger_convention_verified": LEDGER_CONVENTION_VERIFIED,
        "ledger": ledger,
        "required_tables_present": len(populated) == len(PUBLISHED_TABLES),
    }


def read_pending_institutions(cols: list[str]) -> pd.DataFrame:
    """기관 판정 대기 목록(읽기 전용). 운영 원천은 S3 `reference/institutions/Allowlist_Pending.xlsx`.
    프로토타입은 로컬 사본이 있으면 읽고, 없으면 빈 표."""
    if SOURCE == 'api':
        from service.admin_transport import client
        return pd.DataFrame(client().read('pending'), columns=cols)
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
    if SOURCE == 'api':
        from service.admin_transport import client
        return frozenset(client().read('historical'))
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
    if SOURCE == 'api':
        from service.admin_transport import client
        return pd.DataFrame(client().read('automatic-fallback'))
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
