"""Codex 2026-10-04: 고객용 설치·점검·실행기. 관리자/DB/AWS 기능 없음."""
import argparse
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tomllib
import venv

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'dashboard'
ENV = ROOT / '.venv'
PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
DEPENDENCIES = ('streamlit', 'pandas', 'pyarrow', 'plotly', 'requests', 'pypdf',
                'pypdfium2', 'openpyxl', 'olefile', 'xlrd')


def connection_config():
    path = APP / '.streamlit/secrets.toml'
    if not path.is_file():
        raise ValueError('API 연결 설정이 없습니다. README의 로컬 연결 설정을 먼저 완료하세요.')
    try:
        config = tomllib.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        raise ValueError('API 연결 설정 파일을 읽을 수 없습니다. TOML 서식을 확인하세요.') from None
    dashboard = config.get('dashboard', {})
    if not isinstance(dashboard, dict) or dashboard.get('data_source') != 'api':
        raise ValueError('고객 패키지는 API 방식만 지원합니다. data_source = "api"로 설정하세요.')
    from urllib.parse import urlsplit
    api = config.get('data_api', {})
    if not isinstance(api, dict) or not isinstance(api.get('url'), str):
        raise ValueError('API 설정의 url은 HTTPS 주소 문자열이어야 합니다.')
    try:
        parts = urlsplit(api['url'])
    except ValueError:
        raise ValueError('API 주소 형식을 확인하세요.') from None
    token = api.get('token', '')
    if (parts.scheme != 'https' or not parts.hostname or parts.hostname == 'your-api-host'
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {'', '/'}):
        raise ValueError('별도로 전달받은 HTTPS API 기본 주소를 설정하세요.')
    if (not isinstance(token, str) or len(token) < 32 or token.startswith('REPLACE_')
            or any(c.isspace() for c in token)):
        raise ValueError('별도로 전달받은 API 인증키를 설정하세요. 키를 Git에 올리지 마세요.')
    return api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true', help='전용 .venv 생성과 의존성 설치')
    parser.add_argument('--check', action='store_true', help='구조·설치·설정 점검. 네트워크 조회 없음')
    parser.add_argument('--check-api', action='store_true', help='인증된 API 상태만 읽기 확인')
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        raise SystemExit('이 제출본은 Python 3.14로 검증합니다. Python 3.14 64비트를 사용하세요.')
    if not 1024 <= args.port <= 65535:
        raise SystemExit('포트는 1024~65535로 지정하세요.')
    if args.setup:
        if not PYTHON.is_file():
            venv.EnvBuilder(with_pip=True).create(ENV)
        subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r',
                        str(APP / 'requirements.txt')], check=True, cwd=ROOT)
        print('설치 완료. API 연결 설정 후 run_dashboard.cmd를 실행하세요.')
        return
    if PYTHON.is_file() and Path(sys.executable).resolve() != PYTHON.resolve():
        raise SystemExit(subprocess.call([str(PYTHON), str(Path(__file__).resolve()),
                                         *sys.argv[1:]], cwd=ROOT))
    if not PYTHON.is_file():
        raise SystemExit('먼저 setup.cmd 또는 python start_dashboard.py --setup을 실행하세요.')
    for name in ('app_pages', 'service', 'view', 'assets'):
        if not (APP / name).is_dir():
            raise SystemExit('필수 폴더가 없습니다. ZIP 전체를 해제하세요.')
    missing = [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit('필수 패키지 누락: ' + ', '.join(missing) + '. 설치를 다시 진행하세요.')
    try:
        api = connection_config()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if args.check_api:
        import requests
        try:
            response = requests.get(api['url'].rstrip('/') + '/healthz',
                                    headers={'Authorization': 'Bearer ' + api['token']},
                                    timeout=(5, 30), allow_redirects=False)
            if response.status_code != 200:
                raise SystemExit(f'API 확인 실패(HTTP {response.status_code}). 전달자에게 연결 상태를 문의하세요.')
            try:
                health = response.json()
            except ValueError:
                raise SystemExit('API 응답 형식이 다릅니다. API 기본 주소를 확인하세요.') from None
            if not isinstance(health, dict) or health.get('status') != 'ok' or health.get('mode') != 'read-only':
                raise SystemExit('고객 읽기 API 상태를 확인할 수 없습니다. 전달자에게 문의하세요.')
            print('인증 API 상태 정상. 전체 화면·모든 데이터의 검증을 뜻하지 않습니다.')
        except requests.RequestException:
            raise SystemExit('API 연결 실패. 주소·인터넷·API/DB PC 실행 상태를 확인하세요.') from None
        return
    if args.check:
        print('구조·설치·API 설정 서식 정상. 실제 API/DB 연결은 --check-api로 별도 확인하세요.')
        return
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', args.port)) == 0:
            raise SystemExit('해당 포트는 사용 중입니다. 기존 창을 확인하거나 --port 8505를 지정하세요.')
    env = os.environ.copy()
    env['FRONTLINE_DATA_SOURCE'] = 'api'
    for name in ('FRONTLINE_API_URL', 'FRONTLINE_API_TOKEN'):
        env.pop(name, None)
    print(f'이 PC에서만 실행합니다: http://127.0.0.1:{args.port}')
    raise SystemExit(subprocess.call([sys.executable, '-m', 'streamlit', 'run', 'streamlit_app.py',
        '--server.address=127.0.0.1', f'--server.port={args.port}',
        '--browser.gatherUsageStats=false'], cwd=APP, env=env))


if __name__ == '__main__':
    main()
