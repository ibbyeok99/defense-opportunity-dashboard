"""브라우저용 표시 사본. 회사 판정·인증·원문 재조회 입력으로 사용하지 않는다."""
import json
from datetime import datetime, timezone

SCHEMA = 1
MAX_BYTES = 200_000
FIELDS = ('notice_id', 'notice_name', 'procurement_type', 'demand_agency_name',
          'notice_number', 'notice_order', 'notice_date', 'bid_close_date',
          'license_state', 'license_values', 'region_state', 'region_values',
          'license_review_status', 'region_review_status', 'requirement_checked_at',
          'requirement_other_summary', 'license_evidence_quote', 'region_evidence_quote')


def snapshot(row):
    values = {}
    for field in FIELDS:
        value = row.get(field)
        if value is None or str(value) in {'NaT', 'nan', '<NA>'}:
            value = ''
        values[field] = str(value)[:4000 if field.endswith(('values', 'summary', 'quote')) else 1000]
    return {'schema': SCHEMA, 'saved_at': datetime.now(timezone.utc).isoformat(), 'row': values}


def clean(value, ids):
    """개수·크기·형식 제한. 브라우저 값을 검증된 참가 판단으로 승격하지 않는다."""
    if not isinstance(value, dict):
        return {}
    out = {}
    for notice_id in ids[:10]:
        record = value.get(notice_id)
        if not isinstance(record, dict) or record.get('schema') != SCHEMA:
            continue
        row = record.get('row')
        if not isinstance(row, dict) or row.get('notice_id') != notice_id:
            continue
        if not isinstance(record.get('saved_at'), str):
            continue
        if not all(isinstance(v, str) for v in row.values()):
            continue
        bounded = {k: v[:4000 if k.endswith(('values', 'summary', 'quote')) else 1000]
                   for k, v in row.items() if k in FIELDS}
        out[notice_id] = {'schema': SCHEMA, 'saved_at': record['saved_at'][:80], 'row': bounded}
        if len(json.dumps(out, ensure_ascii=False).encode('utf-8')) > MAX_BYTES:
            del out[notice_id]
    return out
