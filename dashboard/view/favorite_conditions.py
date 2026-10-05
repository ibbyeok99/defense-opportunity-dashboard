"""즐겨찾기·비교 카드의 짧은 요건 표시. 원본 근거와 회사 판단은 변경하지 않는다."""
import pandas as pd

from view.fmt import registered_requirement_summary
from view.detail_design import condition_verdict


def deadline_text(row):
    value = pd.to_datetime(row.get('bid_close_date'), errors='coerce')
    return '마감일: ' + (value.strftime('%Y-%m-%d %H:%M') if pd.notna(value) else '미확인')


def requirement_lines(row, detail=None):
    conditions = {r['구분']: r for r in detail['conditions'].to_dict('records')} if detail else {}
    result = []
    for kind, label in [('license', '면허'), ('region', '지역')]:
        values = dict(license_state='미확인', license_values='', region_state='미확인', region_values='')
        values.update({kind+'_state': row.get(kind+'_state'), kind+'_values': row.get(kind+'_values', ''),
                       kind+'_requires_review': row.get(kind+'_requires_review', False),
                       kind+'_review_status': row.get(kind+'_review_status', '')})
        text = registered_requirement_summary(**values) or f'{label} 조건: 확인 필요'
        condition = conditions.get(label)
        if condition is not None and isinstance(condition.get('판단'), str) and condition['판단']:
            status, tone, _ = condition_verdict(condition)
            status = {'input': '조건 미입력', 'check': '확인 필요'}.get(tone, status)
            color = {'ok': 'green', 'no': 'red', 'check': 'orange', 'input': 'gray'}[tone]
            text = f':{color}-badge[{status}] ' + text
        result.append(text)
    return result
