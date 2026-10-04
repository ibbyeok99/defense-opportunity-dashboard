"""나라장터 공개 상세 화면의 읽기 전용 요청. 로그인/쿠키 저장/임의 URL 실행 없음.

2026-10-04 공개 통합 화면의 MainBidPbancM/각 view 스크립트와 실제 화면 대조.
N 플래그의 ‘공고서참조’를 ‘제한 없음’으로 바꾸지 않는다.
"""
from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser

import requests

HOST = 'https://www.g2b.go.kr'
ROUTES = {
    '물품': ('/pn/pnp/pnpe/ItemBidPbac/selectItemAnncMngV.do', 'dmItemMap'),
    '용역': ('/pn/pnp/pnpe/ItemBidPbac/selectItemAnncMngV.do', 'dmItemMap'),
    '기술용역': ('/pn/pnp/pnpe/TechBidPbac/selectTechAnncMngV.do', 'dmItemMap'),
    '공사': ('/pn/pnp/pnpe/facilBidPbac/selectFacilAnncMngV.do', 'dmItemMap'),
    '외자': ('/pn/pnp/pnpe/BidPbac/selectFrcpBidPbacDtlInfo.do', 'dlBidPbancM'),
}
MAX_RESPONSE = 2 * 1024 * 1024
FILES_ROUTE = '/fs/fsc/fscb/UntyAtchFile/selectUntyAtchFileList.do'
DOWNLOAD_ROUTE = '/pn/pnp/pnpe/UntyAtchFile/downloadFile.do'


class PublicPageError(ValueError):
    pass


class PublicPageIdentityError(PublicPageError):
    """응답은 있지만 다른 공고/버전이다. 첨부 결합이나 정적 fallback을 금지한다."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.hidden += 1
        if tag in {'p', 'div', 'br', 'tr', 'li'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {'p', 'div', 'tr', 'li'}:
            self.parts.append('\n')

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def plain_text(value):
    """HTML 태그와 엔티티를 평문으로. 링크/스크립트를 실행하거나 표시하지 않는다."""
    if value is None:
        return ''
    if not isinstance(value, str) or len(value) > 200_000:
        raise PublicPageError('공개 본문 필드 형식·길이 확인 필요')
    text = value
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    parser = _Text()
    parser.feed(text)
    text = ''.join(parser.parts)
    return '\n'.join(re.sub(r'[^\S\n]+', ' ', line).strip()
                     for line in text.splitlines() if line.strip())


def title_text(value):
    """공고명은 값이다. <긴급> 같은 실제 문자까지 HTML 태그로 삭제하지 않는다."""
    if not isinstance(value, str) or len(value) > 2000:
        raise PublicPageError('공개 공고명 형식·길이 확인 필요')
    for _ in range(2):
        value = html.unescape(value)
    return value.strip()


def parse_page(obj, number, order, title, route_type):
    """번호·차수·제목 일치 후 참가자격 필드만 선택. 담당자/세션 정보는 버린다."""
    if not isinstance(obj, dict) or str(obj.get('ErrorCode', '0')) not in {'0', '00', ''}:
        raise PublicPageError('공개 본문 조회 거부/오류')
    map_name = ROUTES[route_type][1]
    main = obj.get(map_name)
    if not isinstance(main, dict):
        raise PublicPageError('공개 본문 미제공')
    if main.get('bidPbancNo') != number or str(main.get('bidPbancOrd')) != order:
        raise PublicPageIdentityError('공개 본문의 공고번호·차수 불일치')
    actual_title = title_text(main.get('bidPbancNm'))
    if ' '.join(actual_title.split()) != ' '.join(title_text(title).split()):
        raise PublicPageIdentityError('공개 본문과 저장 공고 제목 불일치')
    guide = obj.get('dmItemGuidMap') or {}
    if not isinstance(guide, dict):
        raise PublicPageError('공개 참가자격 구역 형식 오류')
    fields = {}
    for label, field, container in (
        ('업종제한', 'intpLmtCn', main), ('지역제한', 'rgnLmtGuidCn', main),
        ('지역제한 안내', 'rgnLmtCn', main), ('입찰참가자격', 'bulkBidPrqfGuidCn', guide),
        ('제조물품 등록', 'mnftrItemLmtCn', main),
    ):
        value = plain_text(container.get(field))
        if value and not value.startswith('관련없음') and value not in {'공고서참조', '공고문참조', '제한안함'}:
            fields[label] = value
    limits = {}
    if route_type in {'물품', '용역', '기술용역'}:
        specs = {'license': ('dmItemLmtList2', 'bidLmtUntyNm'),
                 'region': ('dmItemLmtList1', 'bidLmtUntyNm')}
    elif route_type == '공사':
        specs = {'license': ('dmItemList7', 'licenseNm'), 'region': ('dmItemList5', 'bidLmtUntyNm')}
    else:
        specs = {}  # 외자 화면에 없는 표를 국내 표로 추정하지 않는다.
    for kind, (key, name_field) in specs.items():
        rows = obj.get(key) or []
        if not isinstance(rows, list) or len(rows) > 300:
            raise PublicPageError('공개 제한 표 형식·크기 확인 필요')
        selected = []
        for row in rows:
            if not isinstance(row, dict):
                raise PublicPageError('공개 제한 행 형식 오류')
            if row.get('bidPbancNo', number) != number or str(row.get('bidPbancOrd', order)) != order:
                raise PublicPageIdentityError('공개 제한 표 공고번호·차수 불일치')
            name = plain_text(row.get(name_field))
            if name and name not in {'-', '공고서참조', '공고문참조'}:
                selected.append({'name': name, 'code': str(row.get('bidLmtUntyCd') or ''),
                                 'group': row.get('lmtGupSqno', ''), 'sequence': row.get('lmtSqno', '')})
        limits[kind] = selected
    close = main.get('slprRcptDdlnDt') or ''
    if close and not isinstance(close, str):
        raise PublicPageError('공개 마감일 형식 확인 필요')
    if re.fullmatch(r'\d{12}(?:\d{2})?', close):
        from datetime import datetime
        close = datetime.strptime(close, '%Y%m%d%H%M%S' if len(close) == 14 else '%Y%m%d%H%M').isoformat(' ')
    return {'fields': fields, 'limits': limits,
            '_attachment_params': {'untyAtchFileNo': main.get('itemPbancUntyAtchFileNo') or '',
                                   'bsneClsfCd': main.get('prcmBsneSeCd') or ''},
            'notice_facts': {'bidNtceNm': actual_title, 'bidClseDt': close,
                             'ntceKindNm': plain_text(main.get('pbancKndNm'))}, 'labels': {
        kind: plain_text(main.get(field)) for kind, field in
        (('license', 'lcnsLmtYnNm'), ('region', 'rgnLmtYnNm'))}}


def read_public_page(number, order, procurement_type, title, deadline, *, service_division=''):
    if not re.fullmatch(r'[A-Za-z0-9]{8,20}', number) or not re.fullmatch(r'\d{3}', order):
        raise PublicPageError('공개 본문 식별자 오류')
    route_type = '기술용역' if procurement_type == '용역' and '기술' in service_division else procurement_type
    if route_type not in ROUTES:
        raise PublicPageError('지원하지 않는 공개 공고 화면')
    path, container = ROUTES[route_type]
    page = HOST + '/link/PNPE027_01/single/?bidPbancNo=' + number + '&bidPbancOrd=' + order
    obj = _request_json(path, {container: {'bidPbancNo': number, 'bidPbancOrd': order}}, page, deadline)
    result = parse_page(obj, number, order, title, route_type)
    params = result.pop('_attachment_params')
    result['attachment_inventory_complete'] = False
    try:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(params['untyAtchFileNo'])) or not re.fullmatch(r'\d{2}', str(params['bsneClsfCd'])):
            raise PublicPageError('공개 첨부 목록 연결키 미제공')
        params.update(bsnePath='PNPE', tblNm='PBANC_BID_PBANC', colNm='ITEM_PBANC_UNTY_ATCH_FILE_NO', viewMode='view')
        files = _request_json(FILES_ROUTE, {'dlUntyAtchFileM': params}, page, deadline)
        result['attachments'] = parse_attachments(files, params, number, order)
        result['attachment_inventory_complete'] = True
        result['attachment_inventory_status'] = '공개 화면 파일 목록 확인'
    except PublicPageIdentityError:
        raise
    except PublicPageError as exc:
        # 본문 읽기 성공은 유지하되 파일 목록 확인 실패를 숨기지 않는다.
        result['attachment_inventory_status'] = str(exc)
    return result


def parse_attachments(obj, params, number, order):
    if not isinstance(obj, dict) or str(obj.get('ErrorCode', '0')) not in {'0','00',''}:
        raise PublicPageError('공개 첨부 목록 조회 거부/오류')
    rows = obj.get('dlUntyAtchFileL')
    if not isinstance(rows, list) or len(rows) > 100:
        raise PublicPageError('공개 첨부 목록 형식·개수 한도')
    selected, seen = [], set()
    from urllib.parse import urlencode
    for row in rows:
        if not isinstance(row, dict) or row.get('untyAtchFileNo') != params['untyAtchFileNo']:
            raise PublicPageIdentityError('공개 첨부 목록의 연결키 불일치')
        seq = str(row.get('atchFileSqno', ''))
        if not re.fullmatch(r'\d{1,6}', seq) or seq in seen:
            raise PublicPageError('공개 첨부 순번 오류·중복')
        seen.add(seq)
        name = title_text(row.get('orgnlAtchFileNm'))
        # 실제 공개 kUpload는 N만 제외한다. 미설정(null)은 공개 다운로드 가능이다.
        # 화면 비표시 파일은 목록에 있어도 읽지 않는다.
        permitted = row.get('dwnldPrmsYn') != 'N' and row.get('scrnIndtYn') != 'N'
        url = HOST + DOWNLOAD_ROUTE + '?' + urlencode(dict(bidPbancNo=number,bidPbancOrd=order,
                  fileType='',fileSeq=seq,prcmBsneSeCd=params['bsneClsfCd'])) if permitted else ''
        item = dict(name=name, sequence=seq, url=url, download_permitted=permitted,
                    category=str(row.get('atchFileKndCd') or ''))
        # 실제 공개 목록의 fileSz는 byte 단위. 값이 없거나 잘못된 경우
        # 추측하지 않고 기존 스트리밍 다운로드 한도로 검사한다.
        size = row.get('fileSz')
        if not isinstance(size, bool) and re.fullmatch(r'\d{1,18}', str(size)):
            item['size_bytes'] = int(size)
        selected.append(item)
    return selected


def _request_json(path, payload, page, deadline):
    if path not in {r[0] for r in ROUTES.values()} | {FILES_ROUTE}:
        raise PublicPageError('허용하지 않은 공개 읽기 경로')
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PublicPageError('공개 본문 확인 시간 한도')
    try:
        # 화면의 select 요청만 사용. insert/update 및 로그인 경로는 호출하지 않는다.
        with requests.post(HOST + path, json=payload,
                           headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36',
                                    'Referer': page, 'Accept': 'application/json'},
                           timeout=(4, min(12, remaining)), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise PublicPageError(f'공개 본문 접근 실패(HTTP {response.status_code})')
            import json
            parts, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_RESPONSE or time.monotonic() >= deadline:
                    raise PublicPageError('공개 본문 크기·시간 한도')
                parts.append(chunk)
            obj = json.loads(b''.join(parts))
        return obj
    except PublicPageError:
        raise
    except Exception:
        raise PublicPageError('공개 본문 연결·JSON 읽기 실패') from None
