"""PC 확인 결과의 최소 전달 계약. 원문/첨부/발췌/주소/임의 키는 보내지 않는다."""
from copy import deepcopy
import re

SCHEMA = 'requirement-result-public-v1'
MAX_BYTES = 16384


def request_identity(pt, number, order, source_hash, detail_hash):
    from service.requirement_overlay import identity
    key = identity(dict(procurement_type=pt, notice_number=number, notice_order=order))
    if order != key[2] or any(not re.fullmatch(r'[0-9a-f]{64}', v) for v in (source_hash, detail_hash)):
        raise ValueError('요건 요청 식별자 오류')
    return key


def _text(value, limit):
    if not isinstance(value, str) or len(value) > limit or re.search(r'https?://|[<>\r\n]|serviceKey|Bearer ', value, re.I):
        raise ValueError('공개 요건 필드 형식 오류')
    return value


def validate(value):
    """서버/클라이언트 공통 검사. 원문 사본을 전달 계약으로 위장할 수 없다."""
    from service.requirement_overlay import identity, fresh
    fields = {'projection_schema', 'schema', 'overlay_schema', 'procurement_type', 'notice_number',
              'notice_order', 'checked_at', 'detail_fingerprint', 'resolved', 'coverage', 'evidence',
              'sources', 'warnings', 'api_license_rows', 'api_region_rows', 'structured'}
    if not isinstance(value, dict) or set(value) != fields or value.get('projection_schema') != SCHEMA:
        raise ValueError('공개 요건 전달 계약 오류')
    identity(value)
    if not fresh(value) or not re.fullmatch(r'[0-9a-f]{64}', value['detail_fingerprint']):
        raise ValueError('만료되거나 변경된 공고 결과')
    if value['schema'] != SCHEMA:
        raise ValueError('요건 규칙 버전 불일치')
    for field in ('evidence', 'sources', 'warnings', 'api_license_rows', 'api_region_rows'):
        if value[field] != []:
            raise ValueError('원문/근거 사본 전송 금지')
    if value['structured'] != {'clauses': []} or set(value['resolved']) != {'license', 'region'}:
        raise ValueError('요건 결과 형식 오류')
    for condition in value['resolved'].values():
        if set(condition) != {'state', 'values', 'review', 'manual', 'quote'} or condition['quote'] != '':
            raise ValueError('요건 원문 전송 금지')
        if condition['state'] not in {'제한있음', '조건없음', '미확인'} or type(condition['manual']) is not bool:
            raise ValueError('조건 상태 오류')
        _text(condition['values'], 4096)
        if any(len(v.strip()) > 200 for v in condition['values'].split('|')):
            raise ValueError('조건 값에 장문 혼입')
        _text(condition['review'], 120)
        if condition['state'] == '조건없음' and condition['values']:
            raise ValueError('조건 상태와 값 불일치')
        # 원문을 전달하지 않는 결과로 참가 가능/제한 없음을 자동 확정하지 않는다.
        if condition['state'] == '조건없음' and not condition['manual']:
            raise ValueError('원문 확인 없이 조건 없음 확정 금지')
    coverage = value['coverage']
    if set(coverage) != {'status', 'gaps', 'attachments_listed', 'attachments_read'}:
        raise ValueError('읽기 범위 형식 오류')
    if coverage['status'] not in {'저장 결과 확인', '자료 확인 미완료'} or coverage['gaps'] not in (
            [], ['읽기·해석 공백이 남아 있습니다. 원문 확인이 필요합니다.']):
        raise ValueError('읽기 범위 원문 전송 금지')
    for field in ('attachments_listed', 'attachments_read'):
        if type(coverage[field]) is not int or not 0 <= coverage[field] <= 1000:
            raise ValueError('첨부 건수 오류')
    return deepcopy(value)


def project(record, pt, number, order, source_hash, detail_hash):
    from service.requirement_overlay import identity, fresh, prepare
    key = request_identity(pt, number, order, source_hash, detail_hash)
    if not isinstance(record, dict) or identity(record) != key or not fresh(record):
        return None
    if not re.fullmatch(r'g2b-requirement-evidence-v(?:[4-9]|1[0-6])', str(record.get('schema', ''))):
        return None
    # PC 감시기는 source hash, 상세 조회는 detail hash로 변경 공고를 구분한다.
    if not (record.get('detail_fingerprint') == detail_hash or record.get('source_fingerprint') == source_hash):
        return None
    prepared = prepare(record, pt)  # 저장 판정을 그대로 믿지 않고 현재 규칙으로 재계산.
    from service.requirement_display_audit import display_issues
    if display_issues(prepared):
        return None
    coverage = prepared['coverage']
    def count(field):
        v = coverage.get(field)
        return v if type(v) is int and 0 <= v <= 1000 else 0
    # 입력의 수집기 버전과 전달 규칙 버전은 다르다. 과거 사본도 현재 prepare로
    # 재검증하되 24시간/지문/공백은 그대로 보존한다. 원문을 새로 읽었다고 하지 않는다.
    value = dict(projection_schema=SCHEMA, schema=SCHEMA,
                 overlay_schema=prepared['overlay_schema'], procurement_type=pt,
                 notice_number=number, notice_order=order, checked_at=prepared['checked_at'],
                 detail_fingerprint=detail_hash,
                 resolved={kind: dict(prepared['resolved'][kind], quote='') for kind in ('license', 'region')},
                 coverage=dict(status='자료 확인 미완료' if coverage.get('gaps') else '저장 결과 확인',
                               gaps=['읽기·해석 공백이 남아 있습니다. 원문 확인이 필요합니다.'] if coverage.get('gaps') else [],
                               attachments_listed=count('attachments_listed'), attachments_read=count('attachments_read')),
                 evidence=[], sources=[], warnings=[], api_license_rows=[], api_region_rows=[], structured={'clauses': []})
    return validate(value)
