"""공고 CSV 출력용 한글 열 계약. 원본 값·정렬·공고 수는 보존한다."""
HEADERS = {
    'procurement_type': '조달 유형', 'notice_name': '공고명', 'notice_date': '공고일',
    'bid_close_date': '마감일', 'demand_agency_name': '수요기관', 'category_value': '분류',
    'status': '참여 판단', 'license_values': '면허 조건', 'region_values': '지역 조건',
    'notice_url': '공고 원문 주소',
}


def notice_csv(frame):
    if set(frame.columns) != set(HEADERS):
        raise ValueError('공고 내보내기 열 계약 불일치')
    return frame.rename(columns=HEADERS).to_csv(index=False).encode('utf-8-sig')
