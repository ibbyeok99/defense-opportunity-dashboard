"""Cloud 관리자 전용 API 클라이언트. 일반 읽기 키와 분리·사용자 확인 후 요청."""
import hashlib
import json
import os
import time

import requests
from service.api_transport import DataAPIClient, DataAPIError
from service import admin_access

MAX_BYTES = 8 * 1024 * 1024
READS = frozenset({'operations', 'pending', 'historical', 'automatic', 'automatic-fallback', 'requirement-audit'})


class AdminAPIClient(DataAPIClient):
    def read(self, name):
        admin_access.require()
        if name not in READS:
            raise ValueError('허용되지 않은 관리자 조회')
        try:
            return json.loads(self._get('/v1/admin/' + name, 'application/json', timeout=(5, 90), payload_limit=MAX_BYTES))
        except (ValueError, TypeError):
            raise DataAPIError('관리자 API 결과를 해석할 수 없습니다.') from None

    def confirm(self, rows, decisions, reviewer, batch_id):
        admin_access.require()
        payload = json.dumps(dict(rows=rows, decisions=decisions, reviewer=reviewer, batch_id=batch_id),
                             ensure_ascii=False).encode('utf-8')
        if len(payload) > MAX_BYTES:
            raise ValueError('관리자 검토 요청 크기 한도 초과')
        try:
            # 쓰기를 자동 재시도하지 않는다. 같은 batch_id 재확인은 기존 영수증 계약 사용.
            with requests.post(self.url + '/v1/admin/confirm', data=payload,
                               headers={'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json'},
                               timeout=(5, 90), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise DataAPIError('관리자 저장 확인 실패. 완료 기록을 다시 읽고 같은 검토 묶음으로 확인하세요.')
                if response.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise DataAPIError('관리자 응답 형식 오류')
                body = bytearray()
                deadline = time.monotonic() + 120
                for chunk in response.iter_content(chunk_size=65536):
                    if len(body) + len(chunk) > MAX_BYTES or time.monotonic() > deadline:
                        raise DataAPIError('관리자 응답 한도 초과')
                    body.extend(chunk)
                if hashlib.sha256(body).hexdigest() != response.headers.get('X-Content-SHA256'):
                    raise DataAPIError('관리자 결과 무결성 확인 실패')
                value = json.loads(body)
                if not isinstance(value, dict) or type(value.get('changed')) is not int:
                    raise ValueError
                return value
        except requests.RequestException:
            raise DataAPIError('관리자 연결 실패. 새 검토로 제출하지 말고 기존 완료 기록을 확인하세요.') from None
        except (ValueError, TypeError):
            raise DataAPIError('관리자 저장 결과 형식 오류') from None


def client():
    admin_access.require()
    from service.source import _api_client
    return AdminAPIClient(_api_client().url, os.environ.get('FRONTLINE_ADMIN_API_TOKEN', admin_access.config().get('api_token', '')),
                          max_bytes=MAX_BYTES)
