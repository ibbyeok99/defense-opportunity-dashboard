"""요건 표시 회귀 감시. 근거 전문은 보존하되 값/요약에 원문 덩어리를 넣지 않는다."""
import re

from service.requirement_overlay import condition
from service.requirement_summary import summarize_participation

DIRTY = re.compile(r'<\/?(?:p|div|br|script|table|span)\b|https?://|[-_=─━]{5,}', re.I)


def display_issues(record):
    """내용을 지우거나 자격을 판단하지 않는다. 이상 신호의 항목/사유만 반환한다."""
    issues = []
    for kind in ('license', 'region'):
        resolved = condition(record, kind)
        for value in str(resolved['values']).split('|'):
            if DIRTY.search(value) or len(value.strip()) > 200:
                issues.append({'field': kind, 'reason': '조건 값에 원문·HTML·장문 혼입'})
    for item in summarize_participation(record):
        if DIRTY.search(item['summary']) or len(item['summary']) > 300:
            issues.append({'field': item['category'], 'reason': '요약에 원문·HTML·장문 혼입'})
    return issues
