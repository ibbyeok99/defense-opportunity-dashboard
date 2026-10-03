"""Codex, 2026-10-03: 표시 문구만 변환한다. 저장 상태·원문·판정은 변경하지 않는다."""
import pandas as pd


REVIEW_LABELS = {
    '근거 충돌': '자료마다 조건이 다름 · 원문 확인 필요',
    '자료 확인 미완료': '원문·첨부 확인 필요',
    '일부 첨부 미확인': '일부 첨부 확인 필요',
    '추출 실패': '자료를 읽지 못함 · 원문 확인 필요',
    '확인 자료에서 근거 미탐지': '읽은 자료에서 조건을 찾지 못함',
    '자료 미제공': '확인할 첨부 정보 없음',
    'OCR 원문 대조 필요': '이미지 인식 결과 · 원문 대조 필요',
    '문서 요건 후보·원문 검토': '관련 참가 조건 확인 필요',
    '문서 제한 조건·원문 검토': '문서에 제한 명시 · 원문 확인 필요',
    '문서 지역 조건 확인·원문 검토': '문서에 지역 제한 명시 · 원문 확인 필요',
    '공식 제한 표시·상세 미제공': '제한 있음 · 세부 조건 확인 필요',
    '근거 확인·해석 필요': '참가 조건 해석 필요',
    '공식 조건 확인': '나라장터 등록 조건 확인',
}


def review_label(value):
    return REVIEW_LABELS.get(value, value)


def api_condition_records(rows):
    """기록의 키만 한글화한다. 미등록 필드는 원래 키를 유지해 근거를 누락하지 않는다."""
    names = {'bidNtceNo':'공고번호', 'bidNtceOrd':'차수', 'lmtGrpNo':'조건 묶음', 'lmtSno':'조건 순번',
             'lcnsLmtNm':'면허 제한명', 'prtcptPsblRgnNm':'참가 가능 지역',
             'permsnIndstrytyList':'허용 업종 목록', 'indstrytyMfrcFldList':'업종 주력분야 목록', 'rgstDt':'등록일'}
    return [{names.get(key,key): value for key,value in row.items()} for row in rows]


def korean_time(value):
    """시간대가 있는 값만 변환한다. 시간대 없는 값을 UTC로 추정하지 않는다."""
    try:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp):
            return '확인 필요'
        if stamp.tzinfo is None:
            return stamp.strftime('%Y-%m-%d %H:%M') + ' (시간대 미확인)'
        return stamp.tz_convert('Asia/Seoul').strftime('%Y-%m-%d %H:%M') + ' (한국시간)'
    except (ValueError, TypeError, OverflowError):
        return '확인 필요'


def condition_text(value):
    """사유 접두부만 바꾼다. 뒤의 면허명·번호는 그대로 둔다."""
    if not isinstance(value, str):
        return value
    reason, separator, detail = value.partition(' — ')
    return review_label(reason) + separator + detail


def judgement_reason(value):
    if not isinstance(value, str):
        return value
    return ' · '.join('확인 시각 ' + korean_time(part.removeprefix('근거 조회 '))
                      if part.startswith('근거 조회 ') else review_label(part)
                      for part in value.split(' · '))


def evidence_label(value):
    """출처/읽기 상태의 기술 용어. 법적 근거 문장에는 적용하지 않는다."""
    text = str(review_label(value))
    if text.lower().endswith(('.pdf', '.hwp', '.hwpx', '.xlsx', '.xls', '.zip', '.png', '.jpg', '.jpeg', '.txt')):
        return text
    return text.replace('공식 API', '나라장터 등록정보').replace('API/첨부', '등록정보/첨부').replace('OCR', '이미지 문자 인식').replace('ZIP', '압축파일')
