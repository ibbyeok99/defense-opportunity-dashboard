"""페이지 이동 중 목록을 재사용하되 마감·근거 시효 경계를 넘기지 않는다."""
import pandas as pd


def refresh_deadline(frame, now):
    """한국시간의 현재 조회 결과는 최대 60초, 다음 상태 변화 직전까지만 재사용한다."""
    now = pd.Timestamp(now)
    deadline = min(now + pd.Timedelta(seconds=60), now.normalize() + pd.Timedelta(days=1))
    for column in ('bid_close_date', 'notice_date'):
        values = pd.to_datetime(frame[column], errors='coerce')
        future = values[values >= now]
        if len(future):
            deadline = min(deadline, future.min())
    if 'requirement_checked_at' in frame:
        expires = (pd.to_datetime(frame.requirement_checked_at, utc=True, errors='coerce', format='mixed')
                   + pd.Timedelta(hours=24)).dt.tz_convert('Asia/Seoul').dt.tz_localize(None)
        future = expires[expires >= now]
        if len(future):
            deadline = min(deadline, future.min())
    return deadline.to_pydatetime()
