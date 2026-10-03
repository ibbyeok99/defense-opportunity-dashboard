"""공고 화면/요건 변경 감지에 쓰는 부가 필드만 읽기 위한 고정 계약. IO 없음."""
from __future__ import annotations

# 원본 JSON은 DB에 보존한다. 여기서는 표시/첨부/요건 fingerprint 소비 필드만 고른다.
NOTICE_COLUMNS = (
    'notice_id', 'procurement_type', 'item_code', 'item_name', 'item_label', 'item_name_status',
    'bidNtceNo', 'bidNtceOrd', 'bidNtceNm', 'notice_name', 'notice_url',
    'bidNtceDt', 'bidNtceDt_kst', 'notice_date', 'bidBeginDt', 'bidBeginDt_kst',
    'bidClseDt', 'bidClseDt_kst', 'opengDt', 'opengDt_kst', 're_notice', 'reNtceYn',
    'ntceInsttCd', 'ntceInsttNm', 'notice_agency_code', 'dminsttCd', 'dminsttNm',
    'demand_agency_code', 'cntrctCnclsMthdNm', 'bidMethdNm', 'sucsfbidMthdNm',
    'sucsfbidLwltRate', 'asignBdgtAmt', 'presmptPrce', 'bdgtAmt', 'license_count',
    'region_count', 'license_absence_confirmed', 'region_absence_confirmed',
    'license_state', 'region_state', 'year', 'month', 'run_id', 'data_version',
    'metric_version', 'data_as_of',
)
NOTICE_EXTRA_FIELDS = (
    'contract_method', 'cntrctCnclsMthdNm', 'sucsfbidLwltRate_num', 'sucsfbidLwltRate',
    'bidNtceNo', 'bidNtceOrd', 'notice_date', 'bidNtceDt_kst', 'bidNtceDt',
    'bidQlfctRgstDt_kst', 'bidQlfctRgstDt', 'bidWgrnteeRcptClseDt_kst', 'bidWgrnteeRcptClseDt',
    'bidBeginDt_kst', 'bidBeginDt', 'bidClseDt_kst', 'bidClseDt', 'bid_close_date',
    'opengDt_kst', 'opengDt', 'asignBdgtAmt_num', 'asignBdgtAmt',
    'presmptPrce_num', 'presmptPrce', 'prearngPrceDcsnMthdNm',
    'sucsfbidMthdNm', 'sucsfbidMthdAppStd', 'ntceKindNm', 'cmmnSpldmdMethdNm',
    'cmmnSpldmdAgrmntRcptdocMethd', 'cmmnSpldmdAgrmntClseDt_kst', 'cmmnSpldmdAgrmntClseDt',
    'rbidPermsnYn', 'intrbidYn', 'refNo', 'bfSpecRgstNo', 'orderPlanUntyNo',
    'prev_bid_no', 'befBidBbancNo_std', 'befBidBbancNo',
    'chgDt', 'chgDt_kst', 'indstrytyLmtYn', 'bidPrtcptLmtYn', 'prdctClsfcLmtYn',
    'rgnDutyJntcontrctYn', 'cmmnSpldmdCorpRgnLmtYn',
) + tuple(f'ntceSpec{stem}{slot}' for stem in ('DocUrl', 'FileNm') for slot in range(1, 11))


def notice_select_columns():
    """식별자는 고정. 객체 유무·기존1MiB 문자 한도도 원래 상세 읽기와 같게 유지."""
    pairs = ', '.join(f"'{key}', JSON_EXTRACT(n.extra_attributes, '$.{key}')" for key in NOTICE_EXTRA_FIELDS)
    columns = ', '.join(f'n.`{key}`' for key in NOTICE_COLUMNS)
    projected = ("CASE WHEN JSON_TYPE(n.extra_attributes) = 'OBJECT' "
                 "AND CHAR_LENGTH(CAST(n.extra_attributes AS CHAR)) <= 1048576 "
                 "THEN JSON_MERGE_PATCH('{}', JSON_OBJECT(" + pairs +
                 "), CASE WHEN JSON_LENGTH(n.extra_attributes) > 0 "
                 "THEN JSON_OBJECT('_source_extra_present', TRUE) ELSE JSON_OBJECT() END) "
                 "ELSE JSON_OBJECT() END")
    return columns + ', ' + projected + ' AS extra_attributes, n.`_partition_id`'
