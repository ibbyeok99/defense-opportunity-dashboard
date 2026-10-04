"""관리자 접근 경계. 로컬 로그인 보존·API 모드는 검증된 OIDC 계정만 허용."""
import time
from functools import wraps
import streamlit as st


def config():
    try:
        return dict(st.secrets.get('admin', {}))
    except FileNotFoundError:
        return {}


def allowed_identity(claims, identities, now=None):
    """이메일 문자열이나 세션 플래그가 아니라 공급자 issuer+subject로 권한을 확인."""
    if not isinstance(claims, dict) or not isinstance(identities, list):
        return False
    issuer, subject = claims.get('iss'), claims.get('sub')
    if not isinstance(issuer, str) or not issuer.startswith('https://') or not isinstance(subject, str) or not subject:
        return False
    expiry = claims.get('exp')
    if expiry is not None and (not isinstance(expiry, (int, float)) or expiry <= (time.time() if now is None else now)):
        return False
    return issuer + '|' + subject in identities


def authorized():
    from service import source
    if source.SOURCE != 'api':
        return bool(st.session_state.get('is_admin'))
    try:
        return bool(st.user.is_logged_in and allowed_identity(dict(st.user), config().get('identities', [])))
    except (AttributeError, KeyError, TypeError):
        return False


def require():
    if not authorized():
        raise PermissionError('관리자 로그인이 필요합니다.')


def api_guard(cached):
    """공유 캐시 적중도 매 요청의 계정 권한을 다시 확인한다."""
    @wraps(cached)
    def guarded(*args, **kwargs):
        from service import source
        if source.SOURCE == 'api':
            require()
        return cached(*args, **kwargs)
    guarded.clear = cached.clear
    return guarded


def login_ready():
    try:
        auth = st.secrets.get('auth', {})
        provider = auth.get(config().get('provider'), {}) if config().get('provider') else auth
        return bool(auth.get('redirect_uri') and auth.get('cookie_secret') and config().get('identities')
                    and all(provider.get(k) for k in ('client_id', 'client_secret', 'server_metadata_url')))
    except FileNotFoundError:
        return False
