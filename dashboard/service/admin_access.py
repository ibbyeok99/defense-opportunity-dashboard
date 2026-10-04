"""관리자 접근 경계. 로컬 로그인 보존·API 모드는 검증된 OIDC 계정만 허용."""
import time
from functools import wraps
import streamlit as st


def config():
    try:
        return dict(st.secrets.get('admin', {}))
    except FileNotFoundError:
        return {}


def identity_code(claims, now=None):
    """Streamlit이 검증한 현재 로그인 정보의 고유 ID. 이 함수만으로 권한을 부여하지 않는다."""
    if not isinstance(claims, dict):
        return None
    issuer, subject = claims.get('iss'), claims.get('sub')
    if not isinstance(issuer, str) or not issuer.startswith('https://') or not isinstance(subject, str) or not subject:
        return None
    expiry = claims.get('exp')
    if expiry is not None and (not isinstance(expiry, (int, float)) or expiry <= (time.time() if now is None else now)):
        return None
    return issuer + '|' + subject


def allowed_identity(claims, identities, now=None):
    """이메일 문자열이나 세션 플래그가 아니라 공급자 issuer+subject로 권한을 확인."""
    if not isinstance(identities, list):
        return False
    code = identity_code(claims, now=now)
    return code is not None and code in identities


def allowed_google_email(claims, emails, now=None):
    """검증된 Google 로그인에서 사전 승인한 Gmail만 허용. 입력창·타 공급자 이메일은 사용하지 않는다."""
    if not isinstance(emails, list) or identity_code(claims, now=now) is None:
        return False
    if claims.get('iss') != 'https://accounts.google.com' or claims.get('email_verified') is not True:
        return False
    email = claims.get('email')
    if not isinstance(email, str):
        return False
    email = email.lower()
    if email.count('@') != 1 or not email.endswith('@gmail.com') or not email.removesuffix('@gmail.com'):
        return False
    return email in {value.strip().lower() for value in emails if isinstance(value, str)}


def authorized():
    from service import source
    if source.SOURCE != 'api':
        return bool(st.session_state.get('is_admin'))
    try:
        if not st.user.is_logged_in:
            return False
        claims, admin = dict(st.user), config()
        return allowed_identity(claims, admin.get('identities', [])) or allowed_google_email(claims, admin.get('google_emails', []))
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
        return bool(auth.get('redirect_uri') and auth.get('cookie_secret')
                    and (config().get('identities') or config().get('google_emails'))
                    and all(provider.get(k) for k in ('client_id', 'client_secret', 'server_metadata_url')))
    except FileNotFoundError:
        return False
