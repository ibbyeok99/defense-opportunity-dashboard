# Frontline Data — 강사님 제출본

작성: Codex, 2026-10-04

## 1. 설치 없이 대시보드 확인

- [대시보드 열기](https://defense-opportunity-dashboard-doadt6mmhedzmntzqsg8oj.streamlit.app/)
- 첫 화면에서 **대시보드 바로 가기 →**를 누릅니다.
- 공고 검색 → 상세 확인, 분야별 입찰 분석, 시장 동향, 즐겨찾기를 확인할 수 있습니다.
- 휴면 상태에서 시작하면 준비 시간이 걸릴 수 있습니다.
- 현재 사이트와 Git은 비공개입니다. 강사님 계정의 사이트/Git 열람 권한을 전달 전에 확인해야 합니다. 공개 전환은 아직 하지 않았습니다.
- API PC·DB PC의 전원/네트워크, API 서버·HTTPS 연결이 유지되어야 실제 데이터를 조회할 수 있습니다. 클라우드 배포가 이 의존성을 제거하지는 않습니다.

## 2. 소스코드 확인

- [고객용 Git 저장소](https://github.com/ibbyeok99/defense-opportunity-dashboard)
- `소스코드_안내.md`: 폴더 구조, 모듈 용도, 각 소스 파일의 Git 링크.
- `RELEASE_MANIFEST.json`: 이 ZIP의 코드 기준 커밋과 파일별 SHA-256.
- 고객 화면만 포함합니다. 관리자·수집기·API 서버·DB 원본·조회 근거 사본·실제 인증키는 포함하지 않습니다.
- 기존 과거 ZIP 대신 이 제출본을 사용합니다.

## 3. 내 PC에서 직접 실행 — Windows

### 설치 조건

- Python **3.14 64비트**. 다른 버전은 이 제출본의 검증 대상이 아닙니다.
- [Python 공식 설치 안내](https://www.python.org/downloads/windows/)
- 최초 패키지 설치와 데이터 조회에 인터넷이 필요합니다.
- Anaconda는 필요 없습니다. 제출 폴더에 전용 `.venv`를 만듭니다.
- 압축 파일 안에서 실행하지 말고 전체를 새 폴더에 해제합니다. 폴더 구조를 유지합니다.

### 최초 설치

1. ZIP 전체 해제.
2. `setup.cmd` 실행. Python 3.14로 `.venv`를 만들고 `dashboard/requirements.txt`의 패키지를 설치합니다.
3. 설치 실패 시 창의 오류를 확인합니다. `py -3.14 --version`으로 Python을 확인합니다. `py`가 없는 설치 환경에서는 `python --version`을 확인하며 Python 3.14가 PATH에 있어야 합니다.

같은 작업의 직접 명령:

```powershell
py -3.14 start_dashboard.py --setup
```

`py`가 없고 `python --version`이 3.14라면 `python start_dashboard.py --setup`으로 설치할 수 있습니다. 실행기는 다른 Python 버전에서 설치를 중단합니다.

가상환경 수동 활성화(선택): `.venv\Scripts\Activate.ps1`. 실행기는 활성화 없이도 전용 환경을 사용합니다. PowerShell 실행 정책을 바꿀 필요는 없습니다.

### 로컬 연결 설정

1. `dashboard/.streamlit/secrets.community.example.toml`을 같은 폴더의 `secrets.toml`로 복사합니다.
2. 제출자에게 **HTTPS API 주소와 API 인증키를 별도 안전한 경로로 전달받습니다**. 이 ZIP과 공개 Git에는 실제 값을 넣지 않습니다.
3. 아래 두 예시값만 바꿉니다. DB 비밀번호나 학원 VPN은 필요 없습니다.

```toml
[dashboard]
data_source = "api"

[data_api]
url = "https://YOUR-API-HOST"
token = "REPLACE_WITH_RANDOM_TOKEN_AT_LEAST_32_CHARACTERS"
```

설정·설치 확인과 API 연결 확인:

```powershell
.venv\Scripts\python.exe start_dashboard.py --check
.venv\Scripts\python.exe start_dashboard.py --check-api
```

`--check`는 설정 서식만 검사합니다. 실제 네트워크 연결 성공을 뜻하지 않습니다.

### 실행·종료

- `run_dashboard.cmd` 실행 → 브라우저에서 `http://127.0.0.1:8501` 열기.
- 실행 창은 유지합니다. 종료하려면 실행 창에서 `Ctrl+C`.
- 8501 포트를 다른 앱이 사용하면 `run_dashboard.cmd --port 8505` → `http://127.0.0.1:8505`.
- 코드 수정 뒤 저장하면 화면을 다시 확인할 수 있습니다. Git에 `secrets.toml`을 올리지 않습니다.

### 주요 설치 패키지

| 역할 | 패키지 |
|---|---|
| 화면 | Streamlit |
| 데이터·전송 | pandas, pyarrow, requests |
| 그래프 | Plotly, Altair, matplotlib |
| PDF | pypdf, pypdfium2 |
| 문서 형식 처리 | openpyxl, xlrd, olefile |
| 시간대 | tzdata |

정확한 버전은 `dashboard/requirements.txt`를 따릅니다. MySQL 드라이버·SQLAlchemy·AWS 인증은 이 고객용 API 패키지의 필수 설치 항목이 아닙니다.

## 4. 다른 운영체제

macOS/Linux에서도 Python 3.14로 `python3 start_dashboard.py --setup` 후 `.venv/bin/python start_dashboard.py`를 사용합니다. 이 제출 작업의 실제 설치 검증은 Windows 기준이며 다른 운영체제의 신규 설치는 별도 검증이 필요합니다.

## 5. 기능 범위와 오류 대응

- 저장된 공고·면허/지역·일정/금액·첨부 링크를 표시합니다. `상세 확인`은 제한 없음이나 참가 가능을 뜻하지 않습니다.
- 상세/즐겨찾기에서 공개 원문·저장된 첨부 주소를 비동기로 확인합니다. 먼저 저장 정보를 표시하고 확인 중인 요건은 ‘찾는 중…’으로 표시합니다. 공식 API 보충 조회는 별도 조회키가 필요합니다. 이 제출본에는 키·조회 사본이 없으며 전체 공고 확인 완료를 보장하지 않습니다.
- OCR 모델은 포함하지만 Tesseract 엔진은 별도입니다. 기본 저장 정보 조회에는 필요 없으며 설치 조건·라이선스는 `dashboard/assets/ocr/README.md`를 확인합니다.
- API 오류: 제출자 PC의 API/HTTPS 연결과 DB PC 상태 확인 요청. 임시 HTTPS 주소 변경 시 `secrets.toml` 주소 갱신.
- 모듈 누락: ZIP 전체 해제 여부 확인 후 `setup.cmd` 다시 실행.
- Git·사이트 접근 제한: 제출자에게 공개 전환 상태 또는 권한 확인 요청.
- 신규·변경 공고의 10분 감시 예약은 제출자의 PC에 등록했습니다. PC·DB·사용자 로그인 상태가 필요하며, 로그아웃/전원 종료/임시 HTTPS 주소 변경은 자동 복구하지 않습니다. 이 PC의 저장 근거를 사이트에 전달하는 공유 경로는 추가 승인 전까지 미연결입니다.
- 전체 원문·ZIP·OCR 대조 및 실제 브라우저 다운로드 파일 수신은 완료 범위와 구분합니다. 제출 검증 결과는 `검증결과.md`를 확인합니다.
