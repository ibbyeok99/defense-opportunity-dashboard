"""공고 유형별 수집 분류. 원본 날짜·참가 적격성은 수정하거나 확정하지 않는다."""
import re

from service.notice_saved_details import _extra, _text


def notice_kind(row):
    """저장 필드에 명시된 유형만 사용한다. 제목·차수로 추정하지 않는다."""
    raw = _text(row.get('ntceKindNm')) or _text(_extra(row.get('extra_attributes')).get('ntceKindNm'))
    kind = re.sub(r'\s+', '', raw)
    if kind == '실공고':
        return ''  # 공개 화면의 포괄 표기는 취소/변경 여부를 확정하는 정보가 아니다.
    # 공개 화면은 같은 종류를 '실공고(등록공고)'처럼 표시한다.
    wrapped = re.fullmatch(r'실공고\((등록공고|변경공고|재공고|취소공고)\)', kind)
    return wrapped[1] if wrapped else kind


def cancelled(result):
    return notice_kind(result.get('notice_facts', {})) == '취소공고'
