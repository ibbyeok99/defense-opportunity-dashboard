"""저장 문서의 목록용 조건 전달. 원문·첨부·발췌는 보내지 않는다."""
from copy import deepcopy
import json
import re

import pandas as pd

from service.requirement_overlay import identity, fresh, condition, SCHEMA as OVERLAY_SCHEMA
from service.requirement_projection import _text

SCHEMA = 'stored-condition-list-v1'
MAX_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 10000


def project(records, frame):
    """현행 공고 지문과 같은 사본의 조건만 전달한다. 원본은 변경하지 않는다."""
    from service.requirement_queue import source_fingerprint
    from service.notice_requirements import detail_fingerprint
    rows = {identity(row): row for row in frame.to_dict('records')}
    result = []
    for record in records:
        try:
            key = identity(record)
            row = rows.get(key)
            if row is None or not fresh(record):
                continue
            source_hash, detail_hash = source_fingerprint(row), detail_fingerprint(row)
            if record.get('source_fingerprint') != source_hash and record.get('detail_fingerprint') != detail_hash:
                continue
            facts = record.get('notice_facts', {})
            if facts.get('bidNtceNm') and str(facts['bidNtceNm']).strip() != str(row.get('notice_name', '')).strip():
                continue
            if facts.get('bidClseDt') and pd.to_datetime(facts['bidClseDt'], errors='coerce') != row.get('bid_close_date'):
                continue
            value = dict(list_projection_schema=SCHEMA, overlay_schema=OVERLAY_SCHEMA,
                         procurement_type=key[0], notice_number=key[1], notice_order=key[2],
                         checked_at=record['checked_at'], detail_fingerprint=detail_hash, source_fingerprint=source_hash,
                         resolved={kind: dict(condition(record, kind), quote='') for kind in ('license', 'region')})
            validate([value])
            result.append(value)
        except (ValueError, TypeError, KeyError):
            continue
    return validate(result)


def validate(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS or len(json.dumps(records).encode()) > MAX_BYTES:
        raise ValueError('저장 조건 목록 응답 한도 오류')
    fields = {'list_projection_schema', 'overlay_schema', 'procurement_type', 'notice_number',
              'notice_order', 'checked_at', 'detail_fingerprint', 'source_fingerprint', 'resolved'}
    for item in records:
        if not isinstance(item, dict) or set(item) != fields or item['list_projection_schema'] != SCHEMA:
            raise ValueError('저장 조건 목록 전달 계약 오류')
        identity(item)
        if not fresh(item) or not isinstance(item['detail_fingerprint'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['detail_fingerprint']):
            raise ValueError('만료되거나 변경된 저장 조건')
        if not isinstance(item['source_fingerprint'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['source_fingerprint']):
            raise ValueError('원본 공고 지문 오류')
        if not isinstance(item['resolved'], dict) or set(item['resolved']) != {'license', 'region'}:
            raise ValueError('저장 조건 항목 오류')
        for value in item['resolved'].values():
            if not isinstance(value, dict) or set(value) != {'state', 'values', 'review', 'manual', 'quote'} or value['quote'] != '':
                raise ValueError('원문 사본 전송 금지')
            if value['state'] not in {'미확인', '조건없음', '제한있음'} or type(value['manual']) is not bool:
                raise ValueError('저장 조건 상태 오류')
            _text(value['values'], 4096)
            _text(value['review'], 120)
            if any(len(v.strip()) > 200 for v in value['values'].split('|')):
                raise ValueError('조건 값에 장문 혼입')
            if value['state'] == '조건없음' and (value['values'] or not value['manual']):
                raise ValueError('근거 없이 제한 없음 확정 금지')
    return deepcopy(records)
