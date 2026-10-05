"""게시 메타데이터(`source.mysql_metadata`)를 화면·점검용 문구로 바꾼다. 조회·추정 없이 받은 값만 쓴다.

구분하는 세 가지 시각:
- 통계 자료 기준 범위: 게시 통계 행의 data_as_of 최소~최대(시간대 변환 없음)
- DB 최근 반영 확인: 완료된 실제 적재 이력의 마지막 시각(변경분 0건 회차 포함)
- 수집 최근 성공: 관리자 → 운영 상태의 수집기 기록(여기서 다루지 않음)
"""

UNKNOWN = '확인 필요'


def short_time(text) -> str:
    """'2026-10-05T12:02:35' -> '2026-10-05 12:02'. 값이 없으면 '확인 필요'."""
    if not text:
        return UNKNOWN
    return str(text)[:16].replace('T', ' ')


def has_detail(meta: dict) -> bool:
    """세대 요약을 담은 새 응답인지(구버전 API 응답이면 False)."""
    return isinstance(meta.get('table_generations'), dict) and isinstance(meta.get('ledger'), dict)


def data_range(meta: dict) -> str:
    low, high = meta.get('data_as_of_min'), meta.get('data_as_of_max')
    if low and high:
        return short_time(high) if short_time(low) == short_time(high) else f'{short_time(low)} ~ {short_time(high)}'
    if meta.get('data_as_of'):          # 구버전 응답: 표 하나의 기준일 뿐이라 전체 범위로 읽지 않는다
        return f"{short_time(meta['data_as_of'])} (구버전 응답, 범위 확인 필요)"
    return UNKNOWN


def applied_at(meta: dict) -> str:
    ledger = meta.get('ledger') or {}
    if not ledger.get('last_applied_at'):
        return UNKNOWN
    zone = f" {ledger['timezone']}" if ledger.get('timezone') else ' (시간대 미확인)'
    return f"{short_time(ledger['last_applied_at'])}{zone}"


def applied_note(meta: dict) -> str:
    """최근 반영 회차가 실제로 교체한 표·행 수(이력에 기록된 값만)."""
    ledger = meta.get('ledger') or {}
    rows, tables = ledger.get('last_applied_rows'), ledger.get('last_applied_tables')
    if not ledger.get('last_applied_at') or rows is None or tables is None:
        return ''
    if rows == 0:
        return '최근 반영 회차는 교체할 통계 변경분이 없어 기존 값을 유지했습니다.'
    return f'최근 반영 회차에서 {tables:,}개 표 {rows:,}행을 교체했습니다.'


def exception_tables(meta: dict) -> dict:
    """행 run_id와 소유 대장·적재 이력에 차이가 있는 표 -> (대장에 없거나 행 수가 다른 강한 신호 여부, 세대 라벨 차이 파티션 수).

    차이는 참고 신호다. 행 run_id(생성 세대)와 대장 run_id(적재 세대)는 다를 수 있어, 규약 검증 전에는 오류로 해석하지 않는다.
    """
    found = {}
    for table, check in (meta.get('ownership_checks') or {}).items():
        if not check.get('checked'):
            continue
        strong = (check.get('no_ledger_record') or 0) + (check.get('row_count_differs') or 0)
        label = max(check.get('ledger_run_differs') or 0, check.get('row_run_not_in_load_ledger') or 0)
        if strong or label:
            found[table] = (bool(strong), label)
    return found


def convention_verified(meta: dict) -> bool:
    """생성 세대·적재 세대 대응 규약을 검증한 뒤에만 대조 차이를 정상/실패로 판정한다."""
    return bool(meta.get('ledger_convention_verified'))


def problems_present(meta: dict) -> bool:
    return bool(exception_tables(meta))


def status_label(meta: dict) -> str:
    consistent = meta.get('version_consistent')
    if not has_detail(meta):
        return UNKNOWN
    return '정상' if consistent is True else '실패' if consistent is False else UNKNOWN


def check_rows(meta: dict) -> list[dict]:
    """관리자 데이터 기준 화면의 '게시 상태' 점검 행."""
    present = meta.get('required_tables_present', False)
    rows = [{'검사 항목': '대시보드 지표 테이블 조회', '통과': present, '결과': f"{len(meta.get('table_version_states') or {})}개 핵심 테이블"}]
    if not has_detail(meta):
        rows.append({'검사 항목': '게시 세대·소유 대장 대조', '통과': None,
                     '결과': '게시 세대 정보를 제공하지 않는 구버전 응답입니다. 확인 필요'})
        rows.append({'검사 항목': '활성 적재 이력', '통과': None, '결과': '확인 불가'})
        return rows
    problems = exception_tables(meta)
    parts = ['여러 세대 사용(변경된 부분만 갱신)'] if meta.get('mixed_generations') else []
    if not convention_verified(meta) and not problems_present(meta):
        parts.append('세대 대응 규약 확인 전이라 정상 판단 보류')
    if problems:
        note = '' if convention_verified(meta) else ' (생성 세대와 적재 세대 대응 규약 확인 전이라 정상/실패 판단 보류)'
        parts.append('행 run_id와 적재 대장 run_id가 다른 파티션이 있는 표 ' + ', '.join(sorted(problems)) + note)
    states = meta.get('table_version_states') or {}
    unreadable = [t for t, s in states.items() if s in {'조회 실패', '게시 행 없음', '버전 값 미확인', '대장 확인 불가'}]
    if unreadable:
        parts.append('확인하지 못한 표 ' + ', '.join(unreadable))
    rows.append({'검사 항목': '게시 세대·소유 대장 대조', '통과': meta.get('version_consistent'),
                 '결과': ' · '.join(parts) or f"{len(states)}개 표 대조 통과"})
    ledger = meta['ledger']
    ok = ledger.get('state') == '확인'
    active = ledger.get('active_run_id')
    rows.append({'검사 항목': '활성 적재 이력', '통과': True if ok else None,
                 '결과': (f"{active[:8]}… · 최근 반영 {applied_at(meta)}" if ok else ledger.get('reason') or '확인 불가')})
    return rows
