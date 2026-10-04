"""일반 목록용 공식 API 저장값 계약. 문서 발췌·첨부·임의 필드는 공유하지 않는다."""
from copy import deepcopy
import json

from service.requirement_overlay import fresh, identity, prepare
from service.requirement_projection import _text

SCHEMA = 'api-condition-list-v1'
MAX_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 10000


def project(records):
    out = []
    for record in records:
        if not fresh(record) or not record.get('api_only'):
            continue
        pt, number, order = identity(record)
        value = dict(schema=SCHEMA, overlay_schema=record['overlay_schema'], procurement_type=pt,
                     notice_number=number, notice_order=order, checked_at=record['checked_at'],
                     api_only=True, notice_flags={}, notice_facts={}, api_license_rows=[], api_region_rows=[])
        flag = record.get('notice_flags', {}).get('indstrytyLmtYn')
        if flag in {'Y', 'N'}:
            value['notice_flags']['indstrytyLmtYn'] = flag
        for field in ('bidNtceNm', 'bidClseDt'):
            item = record.get('notice_facts', {}).get(field)
            if item:
                value['notice_facts'][field] = _text(item, 500)
        for kind, field in (('license', 'lcnsLmtNm'), ('region', 'prtcptPsblRgnNm')):
            value['api_' + kind + '_rows'] = [{field: _text(row[field], 200)}
                for row in record.get('api_' + kind + '_rows', []) if isinstance(row.get(field), str)]
        out.append(value)
    validate(out)
    return out


def validate(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS or len(json.dumps(records).encode()) > MAX_BYTES:
        raise ValueError('목록 조건 응답 한도 오류')
    fields = {'schema', 'overlay_schema', 'procurement_type', 'notice_number', 'notice_order', 'checked_at',
              'api_only', 'notice_flags', 'notice_facts', 'api_license_rows', 'api_region_rows'}
    for value in records:
        if not isinstance(value, dict) or set(value) != fields or value['schema'] != SCHEMA or value['api_only'] is not True:
            raise ValueError('목록 공식 API 계약 오류')
        identity(value)
        if not fresh(value):
            raise ValueError('만료된 목록 조건')
        if not isinstance(value['notice_flags'], dict) or set(value['notice_flags']) - {'indstrytyLmtYn'} or any(v not in {'Y', 'N'} for v in value['notice_flags'].values()):
            raise ValueError('목록 제한 플래그 오류')
        if not isinstance(value['notice_facts'], dict) or set(value['notice_facts']) - {'bidNtceNm', 'bidClseDt'}:
            raise ValueError('목록 원문 전송 금지')
        for item in value['notice_facts'].values():
            _text(item, 500)
        for kind, field in (('license', 'lcnsLmtNm'), ('region', 'prtcptPsblRgnNm')):
            rows = value['api_' + kind + '_rows']
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('목록 조건 건수 오류')
            for row in rows:
                if not isinstance(row, dict) or set(row) != {field}:
                    raise ValueError('목록 원문 전송 금지')
                _text(row[field], 200)
    return deepcopy(records)


def prepared(records):
    return [prepare(dict(value, evidence=[], sources=[], warnings=[]), value['procurement_type'])
            for value in validate(records)]
