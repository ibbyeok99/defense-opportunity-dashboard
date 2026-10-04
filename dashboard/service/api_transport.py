"""인증된 읽기 전용 데이터 API 클라이언트. SQL·DB 비밀값을 전달하지 않는다."""

from __future__ import annotations

import hashlib
import io
import json
import time
from urllib.parse import quote, urlsplit

import pandas as pd
import pyarrow as pa
import requests

ARROW_TYPE = "application/vnd.apache.arrow.stream"
MAX_BYTES = 128 * 1024 * 1024


def valid_token(token) -> bool:
    return (isinstance(token, str) and len(token) >= 32
            and not any(c.isspace() for c in token)
            and not token.startswith("REPLACE_"))


class DataAPIError(RuntimeError):
    """사용자에게 URL·인증키·DB 오류 원문을 노출하지 않는 연결 오류."""


def validate_url(url: str) -> str:
    parts = urlsplit(url)
    local = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if (not parts.hostname or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {"", "/"}
            or (parts.scheme != "https" and not (parts.scheme == "http" and local))):
        raise DataAPIError("데이터 API 주소는 HTTPS 기본 주소여야 합니다. 로컬 시험만 HTTP를 허용합니다.")
    return url.rstrip("/")


def encode_frame(frame: pd.DataFrame) -> bytes:
    """코드 문자열·null·날짜·Decimal을 유지하는 Arrow 형식(pickle 금지)."""
    table = pa.Table.from_pandas(frame, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata[b"frontline.attrs"] = json.dumps(frame.attrs, ensure_ascii=False).encode("utf-8")
    table = table.replace_schema_metadata(metadata)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def decode_frame(payload: bytes) -> pd.DataFrame:
    with pa.ipc.open_stream(io.BytesIO(payload)) as reader:
        table = reader.read_all()
    frame = table.to_pandas(use_threads=False)
    attrs = (table.schema.metadata or {}).get(b"frontline.attrs", b"{}")
    frame.attrs.update(json.loads(attrs))
    return frame


class DataAPIClient:
    def __init__(self, url: str, token: str, *, max_bytes: int = MAX_BYTES):
        self.url = validate_url(url)
        if not valid_token(token):
            raise DataAPIError("데이터 API 인증키를 설정하세요(32자 이상).")
        self._token = token
        self.max_bytes = max_bytes

    def _get(self, path: str, content_type: str, *, timeout=(5, 90), payload_limit=None) -> bytes:
        try:
            # 리다이렉트로 다른 호스트에 인증키가 전달되지 않도록 자동 이동 금지.
            with requests.get(self.url + path, headers={"Authorization": "Bearer " + self._token},
                              timeout=timeout, allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    if response.status_code in {401, 403}:
                        raise DataAPIError("데이터 API 인증에 실패했습니다. 인증키를 확인하세요.")
                    raise DataAPIError("데이터 API가 응답하지 않습니다. API·DB PC와 연결 상태를 확인하세요.")
                if response.headers.get("Content-Type", "").split(";")[0] != content_type:
                    raise DataAPIError("데이터 API 응답 형식이 올바르지 않습니다.")
                body = bytearray()
                deadline = time.monotonic() + 120
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if time.monotonic() > deadline or len(body) + len(chunk) > min(self.max_bytes, payload_limit or self.max_bytes):
                        raise DataAPIError("데이터 API 응답 크기·시간 한도를 초과했습니다. 부분 데이터는 사용하지 않습니다.")
                    body.extend(chunk)
                payload = bytes(body)
                digest = response.headers.get("X-Content-SHA256")
                if not digest or hashlib.sha256(payload).hexdigest() != digest:
                    raise DataAPIError("데이터 API 응답 무결성 확인에 실패했습니다.")
                return payload
        except requests.RequestException:
            raise DataAPIError("데이터 API에 연결할 수 없습니다. API·DB PC와 연결 상태를 확인하세요.") from None

    def table(self, name: str) -> pd.DataFrame:
        try:
            return decode_frame(self._get("/v1/tables/" + quote(name, safe=""), ARROW_TYPE))
        except (pa.ArrowException, ValueError, TypeError, KeyError):
            raise DataAPIError("데이터 API 표를 해석할 수 없습니다.") from None

    def metadata(self) -> dict:
        try:
            result = json.loads(self._get("/v1/metadata", "application/json"))
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, TypeError):
            raise DataAPIError("데이터 API 게시 정보를 해석할 수 없습니다.") from None

    def requirement(self, pt, number, order, source_hash, detail_hash):
        from service.requirement_projection import request_identity, validate, MAX_BYTES
        request_identity(pt, number, order, source_hash, detail_hash)
        path = '/v1/requirements/' + '/'.join(quote(v, safe='') for v in (pt, number, order, source_hash, detail_hash))
        try:
            value = json.loads(self._get(path, 'application/json', timeout=(3, 8), payload_limit=MAX_BYTES))
            if not isinstance(value, dict) or set(value) != {'result'}:
                raise ValueError
            result = value['result']
            if result is None:
                return None
            result = validate(result)
            if (result['procurement_type'], result['notice_number'], result['notice_order']) != (pt, number, order) or result['detail_fingerprint'] != detail_hash:
                raise ValueError
            return result
        except (ValueError, TypeError, KeyError):
            raise DataAPIError('저장 요건 결과의 공고·버전·형식을 확인하지 못했습니다.') from None

    def api_requirements(self):
        from service.api_requirement_list import prepared, MAX_BYTES
        try:
            value = json.loads(self._get('/v1/api-requirements', 'application/json', timeout=(3, 8), payload_limit=MAX_BYTES))
            if not isinstance(value, dict) or set(value) != {'records'}:
                raise ValueError
            return prepared(value['records'])
        except (ValueError, TypeError, KeyError):
            raise DataAPIError('저장된 공식 조건의 형식을 확인하지 못했습니다.') from None
