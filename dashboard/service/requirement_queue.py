"""신규·변경 공고의 요건 처리 계획/체크포인트. IO·예약·법적 적격 판정 없음."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import timezone
from zoneinfo import ZoneInfo

import pandas as pd

from service.notice_saved_details import _extra, _text
from service.requirement_overlay import identity, prepare, fresh
from service.requirement_coverage import coverage

QUEUE_SCHEMA = 'requirement-queue-v1'
ROOT_FIELDS = ('notice_name', 'notice_date', 'bid_close_date', 'license_state', 'license_values',
               'region_state', 'region_values', 'notice_url')
EXTRA_FIELDS = ('chgDt', 'chgDt_kst', 'indstrytyLmtYn', 'bidPrtcptLmtYn', 'prdctClsfcLmtYn',
                'cmmnSpldmdMethdNm', 'cmmnSpldmdAgrmntClseDt', 'rgnDutyJntcontrctYn', 'cmmnSpldmdCorpRgnLmtYn')


def source_fingerprint(row):
    """수집 시각/통계 게시 버전은 제외. 실제 요건/첨부/공고 변경만 재처리한다."""
    extra = _extra(row.get('extra_attributes'))
    values = {field: _text(row.get(field)) for field in ROOT_FIELDS}
    keys = EXTRA_FIELDS + tuple(f'ntceSpec{stem}{i}' for stem in ('DocUrl', 'FileNm') for i in range(1, 11))
    values['extra'] = {key: _text(extra.get(key)) for key in keys}
    # 원본에 API 키가 섞여도 공개 상태에는 해시만 저장한다.
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def empty_state():
    return {'schema': QUEUE_SCHEMA, 'jobs': {}}


def validate_state(state):
    if not isinstance(state, dict) or state.get('schema') != QUEUE_SCHEMA or not isinstance(state.get('jobs'), dict):
        raise ValueError('요건 체크포인트 형식 오류. 초기화하거나 전체 재조회하지 않습니다.')
    for key, value in state['jobs'].items():
        if not isinstance(value, dict) or value.get('phase') not in {'기존 근거 재분류', '조회 처리', '실패 중단', '처리 중단·확인 필요'}:
            raise ValueError('요건 체크포인트 항목 오류. 자동 재처리하지 않습니다.')
        identity({'procurement_type': key.split('|')[0], 'notice_id': key})
    return state


def plan_work(frame, records, state, now, *, refresh_active=False, retry_failed=False, failures=()):
    """전체 과거 자료도 계획하되 실행은 최신/마감 전부터 한도 내 진행한다."""
    state = validate_state(state)
    latest = {}
    for record in records:
        key = '|'.join(identity(record))
        if key not in latest or record.get('checked_at', '') > latest[key].get('checked_at', ''):
            latest[key] = record
    jobs = dict(state['jobs'])
    failed = {'|'.join(identity(record)): record for record in sorted(failures, key=lambda record: record.get('checked_at', ''))}
    instant = now.replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(timezone.utc) if not now.tzinfo else now
    work, counts, classified, date_holds = [], Counter(), Counter(), []
    ordered = frame.drop_duplicates('notice_id').copy()
    dates = pd.to_datetime(ordered.notice_date, errors='coerce')
    closes = pd.to_datetime(ordered.bid_close_date, errors='coerce')
    # 1년 초과 입찰기간은 원본 확인 대상으로 보류한다. 법적 오류라고 확정하지 않는다.
    ordered['_date_hold'] = (dates.gt(now) | closes.lt(dates) | (closes - dates).gt(pd.Timedelta(days=365))).fillna(False)
    ordered['_open'] = (dates.le(now) & dates.ge(now - pd.Timedelta(days=365))
                        & closes.ge(now) & ~ordered['_date_hold']).fillna(False)
    ordered = ordered.sort_values(['_open', 'notice_date', 'notice_id'], ascending=[False, False, True], na_position='last')
    for row in ordered.to_dict('records'):
        try:
            key = '|'.join(identity(row))
            if _text(row.get('notice_id')) != key:
                raise ValueError('행의 공고 식별자와 번호/차수 불일치')
        except ValueError:
            counts['식별자 확인 필요'] += 1
            continue
        if row['_date_hold']:
            counts['날짜 원본 확인 보류'] += 1
            date_holds.append(key)
            continue
        digest, previous, record = source_fingerprint(row), jobs.get(key), latest.get(key)
        active = bool(row['_open'])
        failure_record = failed.get(key)
        if not previous and failure_record and (not record or failure_record.get('checked_at', '') > record.get('checked_at', '')):
            jobs[key] = {'fingerprint': digest, 'phase': '실패 중단'}
            previous = jobs[key]
        # 최초 도입 시 기존 사본을 재해석만 한다. 원문/ZIP/OCR 공백은 그대로 남긴다.
        if not previous and record and record.get('source_fingerprint', digest) == digest:
            prepared = prepare(record, row['procurement_type'])
            jobs[key] = {'fingerprint': digest, 'phase': '기존 근거 재분류', 'checked_at': record['checked_at'],
                         'coverage': coverage(prepared)['status'], 'gaps': coverage(prepared)['gaps']}
            previous = jobs[key]
            for kind in ('license', 'region'):
                classified[f"{kind}:{prepared['resolved'][kind]['review']}"] += 1
        same = previous and previous.get('fingerprint') == digest
        failure = same and previous['phase'] in {'실패 중단', '처리 중단·확인 필요'}
        stale = record is not None and not fresh(record, instant)
        if same and failure and not retry_failed:
            counts['실패 보류·반복 안 함'] += 1
        elif same and not (retry_failed and failure) and not (refresh_active and active and stale):
            counts['기존 입력 동일·조회 생략'] += 1
            if stale and active:
                counts['마감 전 근거 시효 확인 필요'] += 1
        else:
            reason = ('실패 명시적 재처리' if failure else '마감 전 근거 갱신' if same else
                      '입력 변경' if previous or record else '신규 미조회')
            work.append({'notice_id': key, 'fingerprint': digest, 'reason': reason,
                         'expected_title': _text(row.get('notice_name')).strip(),
                         'expected_close': _text(row.get('bid_close_date'))})
            counts[reason] += 1
    return {'state': {'schema': QUEUE_SCHEMA, 'jobs': jobs}, 'work': work, 'date_holds':date_holds,
            'summary': {'target': len(ordered), 'queued': len(work), 'counts': dict(counts),
                        'existing_reclassified': dict(classified)}}


def process_work(plan, checker, save_evidence, save_state, *, limit=5, progress=lambda value: None, can_start=lambda: True):
    """작업 전 체크포인트/건별 저장. 중단·오류는 다음 실행에서 자동 재시도하지 않는다."""
    if not 1 <= limit <= 200:
        raise ValueError('회차 한도는 1~200건입니다.')
    state = validate_state(plan['state'])
    save_state(state)
    processed = []
    for job in plan['work'][:limit]:
        if not can_start():
            progress({'stopped': '회차 시간 한도·미실행 작업은 대기 유지'})
            break
        pt, number, order = job['notice_id'].split('|')
        state['jobs'][job['notice_id']] = {'fingerprint': job['fingerprint'], 'phase': '처리 중단·확인 필요'}
        save_state(state)  # 프로세스가 여기서 종료돼도 자동 중복 호출하지 않는다.
        try:
            result = checker(number, order, pt)
            if identity(dict(result, procurement_type=pt)) != (pt, number, order):
                raise ValueError('조회 결과의 공고 식별자 불일치')
            facts = result.get('notice_facts', {})
            if facts.get('bidNtceNm') and _text(facts['bidNtceNm']).strip() != job['expected_title']:
                raise ValueError('조회 결과와 저장 공고 제목 불일치')
            if facts.get('bidClseDt'):
                expected = pd.to_datetime(job['expected_close'], errors='coerce')
                observed = pd.to_datetime(facts['bidClseDt'], errors='coerce')
                if pd.isna(expected) or pd.isna(observed) or expected != observed:
                    raise ValueError('조회 결과와 저장 공고 마감 불일치')
            result = dict(result, source_fingerprint=job['fingerprint'])
            saved = save_evidence(result, pt)
        except Exception:
            state['jobs'][job['notice_id']]['phase'] = '실패 중단'
            save_state(state)
            progress({'stopped': '조회/저장 오류·재시도 보류', 'notice_id': job['notice_id']})
            return processed, False
        details = coverage(saved)
        state['jobs'][job['notice_id']].update(phase='조회 처리', checked_at=saved['checked_at'],
                                             coverage=details['status'], gaps=details['gaps'])
        save_state(state)
        processed.append(saved)
        progress({'notice_id': job['notice_id'], 'coverage': details['status'], 'gaps': details['gaps'],
                  'resolved': {kind: saved['resolved'][kind]['review'] for kind in ('license', 'region')}})
        useful = any(e.get('scope') in {'공식 API', '참가자격 구역'} and e.get('relevant', True)
                     for e in saved.get('evidence', []))
        useful |= any(saved['resolved'][kind]['review'] in {'공식 조건 확인', '공식 업종 제한 없음'} for kind in ('license','region'))
        if not useful:
            progress({'stopped': '새로 읽은 근거 없음·누락/읽기 실패 원인 점검 필요', 'notice_id': job['notice_id']})
            return processed, False
    return processed, True
