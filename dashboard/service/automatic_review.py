"""Codex, 2026-10-01: 관리자 자동판별 S3 검토 연결. 조회/수정은 사용 시에만 수행."""
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from service import source, admin_access

from service import review_identity as protocol


def _local_protocol():
    raise RuntimeError('운영 AWS 작업은 관리자 API 서버에서만 실행합니다.')

# 과거 분석 스냅샷 마지막 날은 9/15. 이후 신규 관측만 검토한다.
LIVE_REVIEW_START = pd.Timestamp("2026-09-16", tz="Asia/Seoul")


def whole_registry():
    """전체 재검토는 사용자가 선택한 서버 실행 설정에서만 활성화한다."""
    scope = os.environ.get('FRONTLINE_REVIEW_SCOPE')
    if scope is None and source.SOURCE == 'mysql':
        try:
            scope = st.secrets.get('admin_api', {}).get('review_scope', 'new')
        except FileNotFoundError:
            scope = 'new'
    return scope == 'all'


@admin_access.api_guard
@st.cache_data(ttl=300, show_spinner=False)
def historical_codes():
    if source.SOURCE != 'api' and whole_registry():
        return frozenset()
    return source.read_historical_institution_codes()


def live_new_rows(frame, baseline_codes):
    """과거 검토에 없는 코드 + 수집 전환 이후 최초 관측. 원본·판정·검토 ID 보존."""
    if frame.empty:
        return frame.copy()
    required = {"institution_code", "first_observed_at", "is_defense"}
    if not required.issubset(frame.columns):
        return frame.iloc[:0].copy()
    codes = frame["institution_code"].fillna("").astype(str).str.strip()
    if frame.attrs.get('review_scope') == 'all':
        return frame.loc[codes.ne('') & frame['is_defense'].isin(['Y', 'N'])].copy().reset_index(drop=True)
    observed = pd.to_datetime(frame["first_observed_at"], errors="coerce", utc=True, format="mixed")
    mask = (codes.ne("") & ~codes.isin(baseline_codes) & observed.ge(LIVE_REVIEW_START)
            & frame["is_defense"].isin(["Y", "N"]))
    return frame.loc[mask].copy().reset_index(drop=True)


def scope_batch(batch, baseline_codes):
    """미제출 목록만 좁힌다. 이미 제출한 재시도 묶음은 변경하지 않고 범위 충돌 시 차단한다."""
    frame = pd.DataFrame(batch['rows'])
    frame.attrs['review_scope'] = batch.get('review_scope', 'new')
    kept = live_new_rows(frame, baseline_codes).to_dict("records")
    valid = len(kept) == len(batch["rows"])
    if batch.get("attempt"):
        return batch, valid
    return {**batch, "rows": kept}, True


def client(service_name='s3'):
    raise RuntimeError('운영 AWS 작업은 관리자 API 서버에서만 실행합니다.')


def bucket():
    raise RuntimeError('운영 AWS 작업은 관리자 API 서버에서만 실행합니다.')


@admin_access.api_guard
@st.cache_data(ttl=30, show_spinner=False)
def snapshot():
    if source.SOURCE == 'api':
        from service.admin_transport import client as api_client
        value = api_client().read('automatic')
        frame = pd.DataFrame(value['rows'])
        frame.attrs['review_scope'] = value['receipts'].get('review_scope', 'new')
        return frame, value['receipts']
    if os.environ.get("FRONTLINE_REVIEW_BACKEND") == "offline":
        raise RuntimeError("오프라인 검증에서는 운영 S3 검토를 실행하지 않습니다.")
    s3 = client()
    backend = _local_protocol()
    options = {'whole_registry': True} if whole_registry() else {}
    rows, receipts = backend.snapshot(s3, bucket(), **options)
    receipts["pending_requests"] = backend.pending_requests(s3, bucket(), receipts, **options)
    frame = pd.DataFrame(rows)
    frame.attrs['review_scope'] = receipts.get('review_scope', 'new')
    return live_new_rows(frame, historical_codes()), receipts


def confirm(rows, decisions, reviewer, batch_id):
    if source.SOURCE == 'api':
        from service.admin_transport import client as api_client
        return api_client().confirm(rows, decisions, reviewer, batch_id)
    if os.environ.get("FRONTLINE_REVIEW_BACKEND") == "offline":
        raise RuntimeError("오프라인 검증에서는 운영 S3 판정을 저장하지 않습니다.")
    frame = pd.DataFrame(rows)
    if whole_registry():
        frame.attrs['review_scope'] = 'all'
    eligible = live_new_rows(frame, historical_codes())
    if not rows or len(eligible) != len(rows):
        raise ValueError("실시간 수집 이후 신규 관측 기관만 검토할 수 있습니다. 과거 기관·관측 시각을 확인하세요.")
    options = {'whole_registry': True} if whole_registry() else {}
    return _local_protocol().confirm(client(), bucket(), rows, decisions, reviewer, batch_id, **options)
