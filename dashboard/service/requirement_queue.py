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
from service.notice_date_policy import notice_kind

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


def plan_work(frame, records, state, now, *, refresh_active=False, retry_failed=False, failures=(),
              reprocess_incomplete=False, processing_version='', deadline_edge_size=0,
              deadline_edges_only=False):
    """전체 자료에서 구간을 정한 뒤 기존 처리 건을 제외한다. 기본은 마감 임박 순서다."""
    if type(deadline_edge_size) is not int or not 0 <= deadline_edge_size <= 10000:
        raise ValueError('마감일 양끝 구간 크기는 0~10000건입니다.')
    if deadline_edges_only and not deadline_edge_size:
        raise ValueError('양끝만 처리하려면 구간 크기를 지정하세요.')
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
    kinds = ordered.apply(notice_kind, axis=1)
    cancelled = kinds.eq('취소공고')
    long_period = (closes - dates).gt(pd.Timedelta(days=365)).fillna(False)
    long_registration = long_period & kinds.isin(['등록공고', '변경공고'])
    # 취소 게시일과 기존 입찰 마감은 순서가 역전될 수 있다. 장기 등록/변경은
    # 날짜 원본 확인을 위한 별도 수집 대상이며 일반 진행 중 입찰로 우선하지 않는다.
    ordered['_date_hold'] = (dates.gt(now) | (closes.lt(dates) & ~cancelled)
                             | (long_period & ~long_registration & ~cancelled)).fillna(False)
    ordered['_open'] = (dates.le(now) & dates.ge(now - pd.Timedelta(days=365))
                        & closes.ge(now) & ~ordered['_date_hold'] & ~cancelled & ~long_period).fillna(False)
    ordered['_notice_kind'] = kinds
    ordered['_date_review'] = '일반 공고'
    ordered.loc[long_registration, '_date_review'] = '장기 등록·변경공고·날짜 원본 확인'
    ordered.loc[cancelled, '_date_review'] = '취소공고·이력 확인'
    ordered.loc[ordered['_date_hold'], '_date_review'] = '날짜 원본 확인 보류'
    ordered['_priority'] = 1
    ordered.loc[ordered['_open'], '_priority'] = 0
    ordered.loc[long_registration, '_priority'] = 2
    ordered.loc[cancelled, '_priority'] = 3
    ordered['_deadline_priority'] = closes.where(ordered['_open'])
    ordered = ordered.sort_values(['_priority', '_deadline_priority', 'notice_date', 'notice_id'],
                                 ascending=[True, True, False, True], na_position='last')
    ordered['_deadline_group'] = '기존 순서'
    if deadline_edge_size:
        # 처리 이력을 빼기 전에 구간을 고정한다. 회차마다 앞 1000개가 이동하지 않는다.
        dated = ordered.loc[~ordered['_date_hold'] & closes.notna()].copy()
        dated['_close_order'] = closes.loc[dated.index]
        dated = dated.sort_values(['_close_order', 'notice_id'])
        front = dated.head(deadline_edge_size).index
        back = dated.tail(deadline_edge_size).index.difference(front, sort=False)
        ordered['_edge_priority'] = 2
        ordered['_edge_deadline'] = closes
        ordered['_deadline_group'] = '중간 구간'
        ordered.loc[front, ['_edge_priority', '_deadline_group']] = [0, '앞 구간']
        ordered.loc[back, ['_edge_priority', '_deadline_group']] = [1, '뒤 구간']
        ordered.loc[~ordered['_date_hold'] & closes.isna(), ['_edge_priority', '_deadline_group']] = [3, '마감일 미확인']
        ordered = ordered.sort_values(['_edge_priority', '_edge_deadline', 'notice_id'],
                                     na_position='last')
        if deadline_edges_only:
            ordered = ordered.loc[ordered['_deadline_group'].isin(['앞 구간', '뒤 구간'])]
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
        upgrade = (same and not failure and reprocess_incomplete and previous.get('gaps')
                   and processing_version and previous.get('processing_version') != processing_version)
        if same and failure and not retry_failed:
            counts['실패 보류·반복 안 함'] += 1
        elif same and not upgrade and not (retry_failed and failure) and not (refresh_active and active and stale):
            counts['기존 입력 동일·조회 생략'] += 1
            if stale and active:
                counts['마감 전 근거 시효 확인 필요'] += 1
        else:
            reason = ('실패 명시적 재처리' if failure else '읽기 보완 버전 적용' if upgrade else '마감 전 근거 갱신' if same else
                      '입력 변경' if previous or record else '신규 미조회')
            work.append({'notice_id': key, 'fingerprint': digest, 'reason': reason,
                         'date_review': row['_date_review'], 'notice_kind': row['_notice_kind'],
                         'deadline_group': row['_deadline_group'],
                         'processing_version': processing_version,
                         'expected_title': _text(row.get('notice_name')).strip(),
                         'expected_close': _text(row.get('bid_close_date'))})
            counts[reason] += 1
    return {'state': {'schema': QUEUE_SCHEMA, 'jobs': jobs}, 'work': work, 'date_holds':date_holds,
            'summary': {'target': len(ordered), 'queued': len(work), 'counts': dict(counts),
                        'date_reviews': ordered['_date_review'].value_counts().to_dict(),
                        'deadline_edge_size': deadline_edge_size,
                        'deadline_edges_only': deadline_edges_only,
                        'deadline_groups': ordered.loc[~ordered['_date_hold'], '_deadline_group'].value_counts().to_dict(),
                        'queued_deadline_groups': dict(Counter(job['deadline_group'] for job in work)),
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
        state['jobs'][job['notice_id']] = {'fingerprint': job['fingerprint'], 'phase': '처리 중단·확인 필요',
                                         'deadline_group': job.get('deadline_group', '기존 순서'),
                                         'date_review': job.get('date_review', '일반 공고')}
        save_state(state)  # 프로세스가 여기서 종료돼도 자동 중복 호출하지 않는다.
        stage = '원문·첨부 읽기'
        try:
            progress({'started': '원문·첨부 읽기', 'notice_id': job['notice_id'], 'deadline': job['expected_close'],
                      'deadline_group': job.get('deadline_group', '기존 순서')})
            result = checker(number, order, pt)
            stage = '공고 번호·차수 대조'
            if identity(dict(result, procurement_type=pt)) != (pt, number, order):
                raise ValueError('조회 결과의 공고 식별자 불일치')
            facts = result.get('notice_facts', {})
            stage = '공고 제목 대조'
            if facts.get('bidNtceNm') and _text(facts['bidNtceNm']).strip() != job['expected_title']:
                raise ValueError('조회 결과와 저장 공고 제목 불일치')
            stage = '공고 종류 대조'
            expected_kind, observed_kind = job.get('notice_kind'), notice_kind(facts)
            if expected_kind and observed_kind and expected_kind != observed_kind:
                raise ValueError('조회 결과와 저장 공고 종류 불일치')
            stage = '공고 마감일 대조'
            if facts.get('bidClseDt'):
                expected = pd.to_datetime(job['expected_close'], errors='coerce')
                observed = pd.to_datetime(facts['bidClseDt'], errors='coerce')
                if pd.isna(expected) or pd.isna(observed) or expected != observed:
                    raise ValueError('조회 결과와 저장 공고 마감 불일치')
            result = dict(result, source_fingerprint=job['fingerprint'])
            stage = '요건 표시 검사'
            from service.requirement_display_audit import display_issues
            if display_issues(result):
                raise ValueError('조건 값/요약의 원문·HTML·장문 혼입. 저장 전 검토 필요')
            stage = '검증 결과 저장'
            saved = save_evidence(result, pt)
        except Exception:
            state['jobs'][job['notice_id']].update(phase='실패 중단', failure_stage=stage)
            save_state(state)
            progress({'stopped': '조회/저장 오류·재시도 보류', 'notice_id': job['notice_id'], 'failure_stage': stage})
            return processed, False
        # 보호/미지원 등 알려진 스킵은 뒤 공고를 막지 않는다. 새 오류는 검증된
        # 부분 근거를 보존하되 성공 체크포인트로 처리하지 않아 자동 반복을 막는다.
        if any(item.get('action') == '새 오류·원인 점검'
               for item in saved.get('automation', {}).get('source_skips', [])):
            state['jobs'][job['notice_id']].update(phase='실패 중단',
                failure_stage='새 첨부 읽기 오류·원인 점검', checked_at=saved['checked_at'])
            save_state(state)
            processed.append(saved)
            progress({'stopped': '새 첨부 읽기 오류·부분 근거 보존·재시도 보류',
                      'notice_id': job['notice_id'], 'failure_stage': '새 첨부 읽기 오류·원인 점검'})
            return processed, False
        details = coverage(saved)
        state['jobs'][job['notice_id']].update(phase='조회 처리', checked_at=saved['checked_at'],
                                             coverage=details['status'], gaps=details['gaps'],
                                             processing_version=job.get('processing_version', ''))
        save_state(state)
        processed.append(saved)
        progress({'notice_id': job['notice_id'], 'coverage': details['status'], 'gaps': details['gaps'],
                  'resolved': {kind: saved['resolved'][kind]['review'] for kind in ('license', 'region')}})
        useful = any(e.get('scope') in {'공식 API', '참가자격 구역', '공개 화면 구조화 조건'} and e.get('relevant', True)
                     for e in saved.get('evidence', []))
        useful |= any(saved['resolved'][kind]['review'] in {'공식 조건 확인', '공식 업종 제한 없음'} for kind in ('license','region'))
        # 실제 공개 본문 읽기 성공/내용 없음과 접근 실패를 분리한다. 조건을 억지로 만들지 않는다.
        useful |= any(s.get('name') == '원문 페이지' and s.get('status') == '동적 본문 확인'
                      for s in saved.get('sources', []))
        if not useful:
            progress({'stopped': '새로 읽은 근거 없음·누락/읽기 실패 원인 점검 필요', 'notice_id': job['notice_id']})
            return processed, False
    return processed, True
