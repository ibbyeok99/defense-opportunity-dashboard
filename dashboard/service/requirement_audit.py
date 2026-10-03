"""조회 이력과 읽기/해석 상태를 구분한다. 실패를 제한 없음으로 바꾸지 않는다."""
from collections import Counter
from datetime import timezone

from service.requirement_overlay import condition, fresh, identity, overlay, pending


def targets(frame, now, scope="active"):
    if scope == "active":
        return pending(frame, now)
    if scope != "all":
        raise ValueError("범위는 active/all만 지원합니다")
    # 알려진 면허·지역이 있더라도 다른 참가 제한을 확인할 대상에 포함한다.
    result = frame.drop_duplicates("notice_id").copy()
    result['_open'] = result.bid_close_date.ge(now).fillna(False)
    result['_unknown'] = result.license_state.eq('미확인') | result.region_state.eq('미확인')
    return result.sort_values(['_open', '_unknown', 'notice_date', 'notice_id'], ascending=[False, False, False, True], na_position='last').drop(columns=['_open', '_unknown'])


def audit_requirements(frame, records, now, failures=(), scope="active", details=False):
    work = targets(frame, now, scope)
    latest = {}
    failed = {identity(record): record for record in sorted(failures, key=lambda r: r.get('checked_at', ''))}
    for record in records:
        key = identity(record)
        if key not in latest or record.get("checked_at", "") > latest[key].get("checked_at", ""):
            latest[key] = record
    stages, reasons = Counter(), {kind: Counter() for kind in ("license", "region")}
    # now는 공고 날짜와 비교하는 KST naive 시각. 근거 시각은 UTC로 변환한다.
    from zoneinfo import ZoneInfo
    instant = now.replace(tzinfo=ZoneInfo("Asia/Seoul")).astimezone(timezone.utc) if not now.tzinfo else now
    current = overlay(frame, list(latest.values()), instant)
    entries, coverage_states = [], Counter()
    for index, row in work.iterrows():
        try:
            key = identity(row)
        except ValueError:
            stages['식별자 확인 필요'] += 1
            coverage_states['식별자 확인 필요'] += 1
            for kind in reasons:
                reasons[kind]['식별자 확인 필요'] += 1
            entries.append(dict(notice_id=str(row.notice_id), stage='식별자 확인 필요'))
            continue
        record = latest.get(key)
        stage = "미조회" if record is None else "재조회 필요" if not fresh(record, instant) else "조회 완료"
        if stage == "조회 완료" and not current.at[index, 'requirement_checked_at']:
            stage = "자료 버전 불일치"
        failure = failed.get(key)
        if failure and (record is None or failure.get('checked_at', '') > record.get('checked_at', '')):
            stage = failure['stage']
        stages[stage] += 1
        from service.requirement_coverage import coverage
        checked = coverage(record) if record and stage == '조회 완료' else None
        coverage_states[checked['status'] if checked else stage] += 1
        if details:
            entries.append(dict(notice_id=str(row.notice_id), stage=stage,
                coverage=checked, license=condition(record, 'license') if record and stage == '조회 완료' else None,
                region=condition(record, 'region') if record and stage == '조회 완료' else None,
                other_categories=list(dict.fromkeys(v['category'] for c in (record or {}).get('structured', {}).get('clauses', [])
                                                    for v in c.get('other_requirements', [])))))
        for kind in reasons:
            reasons[kind][condition(record, kind)["review"]
                          if stage == "조회 완료" else stage] += 1
    selected = current.loc[work.index]
    report = {"target": len(work), "scope": scope, "stages": dict(stages), "coverage": dict(coverage_states),
            "reasons": {kind: dict(values) for kind, values in reasons.items()},
            "unknown": {kind: int(selected[f"{kind}_state"].eq("미확인").sum()) for kind in reasons}}
    if details:
        report['notices'] = entries
    return report
