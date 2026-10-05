"""운영 상태 표시용 해석. 수집/판정/대장 쓰기 없음."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

KST = ZoneInfo('Asia/Seoul')
WARNING_HOURS = 3


def last_success(events):
    """최종 RUN00+exit0인 실제 수집 실행만 성공으로 사용. status 조회 제외."""
    times = []
    for event in events:
        try:
            value = json.loads(event['message'])
            if value.get('job') not in {'collect', 'hourly'} or value.get('code') != 'G2B-RUN00' or value.get('exit_code') != 0:
                continue
            stamp = datetime.fromisoformat(value['ts'])
            if stamp.tzinfo:
                times.append(stamp.astimezone(KST))
        except (KeyError, ValueError, TypeError):
            continue
    return max(times).isoformat() if times else None


def read_last_success(logs, group, now):
    """최신 세 시간을 먼저 완전히 읽고, 성공이 없으면 나머지 하루 범위를 읽는다."""
    for start, end in ((now - timedelta(hours=3), now), (now - timedelta(hours=24), now - timedelta(hours=3))):
        request = dict(logGroupName=group, startTime=int(start.timestamp()*1000), endTime=int(end.timestamp()*1000),
                       filterPattern='{ $.code = "G2B-RUN00" }', limit=100)
        events, tokens = [], set()
        for _ in range(3):
            response = logs.filter_log_events(**request)
            events.extend(response.get('events', []))
            token = response.get('nextToken')
            if not token:
                break
            if token in tokens:
                raise ValueError('성공 로그 조회가 진행되지 않아 최신 여부를 확인하지 못했습니다.')
            tokens.add(token)
            request['nextToken'] = token
        else:
            raise ValueError('성공 로그 조회 한도 초과·최신 여부 미확인')
        success = last_success(events)
        if success:
            return success
    return None


def state_counts(state, pending_frame):
    if not isinstance(state.get('repairs'), dict) or not isinstance(state.get('pending'), dict):
        raise ValueError('상태 대장 필수 항목 없음')
    if not {'institution_code', 'manual_is_defense'} <= set(pending_frame.columns):
        raise ValueError('판정 대장 필수 열 없음')
    mask = ~pending_frame.manual_is_defense.fillna('').astype(str).str.strip().str.upper().isin(['Y','N'])
    codes = pending_frame.loc[mask, 'institution_code'].fillna('').astype(str).str.strip()
    if codes.eq('').any():
        raise ValueError('판정 대장 기관코드 누락')
    return dict(repair_pending=sum(v.get('status') == 'pending' for v in state['repairs'].values()),
                judgment_pending=int(codes.nunique()),
                isolated_rows=sum(v.get('status') == 'pending' for v in state['pending'].values()),
                repair_given_up=sum(v.get('status') == 'given_up' for v in state['repairs'].values()))


def warning(snapshot, now=None, hours=WARNING_HOURS):
    now = now or datetime.now(KST)
    if snapshot.get('errors'):
        return '확인 실패'
    if not snapshot.get('last_success'):
        return '24시간 내 수집 성공 기록 없음'
    stamp = datetime.fromisoformat(snapshot['last_success'])
    if not stamp.tzinfo or stamp > now:
        return '성공 시각 확인 필요'
    return '수집 지연' if now - stamp >= timedelta(hours=hours) else None
