# Frontline Data — 강사님 제출본

작성: Codex, 2026-10-04

## 사이트 재배포 완료 (Codex, 2026-10-04)

- 배포 코드 기준 `b9fcd16b1bb28822618dbb6dee704eb5ad10b7b3`, 프로젝트 코드 기준 `4e8270e40c4211cd5d12410de30991d1457bde3b`. 두 Git 정상 push·원격 일치. 후속 문서 커밋은 코드 기준과 구분합니다.
- 전체917개·추가91개 검사 통과. 고객119파일80Python·공개 이력8커밋236blob의 알려진 비밀값/실데이터 감사 발견0. 실제 API 연결 고객8화면 통과.
- Cloud 앱1회 재시작 후 실제 목록79건·미확인 요건 공란·등록 면허/지역·관리 버튼·즐겨찾기 저장/새로고침 복원/회사 조건 변경 비교 갱신을 확인했습니다. 검증용 입력과 공고는 빈 상태로 원복했습니다.
- 관리자 로그인 설정은 배포 후 별도 진행합니다. 현재 관리 버튼은 미설정 안내를 표시하며 실제 관리자 로그인·운영 저장은 미완료입니다.
- ZIP/Drive는 갱신하지 않았습니다. 기존 ZIP을 이번 사이트/Git과 같은 최신본으로 제출하지 마세요. 아래 재배포 전 기록은 당시 이력입니다.

## 최신 수정 반영 (Codex, 2026-10-04)

- 사용자 승인된 최신 공고/즐겨찾기 역할 분리·회사 입력 안내·준비 내용 우선 표시·즐겨찾기 요건 표시 저장/복원·조건 변경 갱신·관리 버튼 복원 포함.
- 전체917개148.82초·기존 인증 HTTPS 고객8화면/29,198공고·고객119파일80Python 비밀값/실데이터0 검증 후 이번 재배포 진행. 실제 사이트 확인 결과는 후속 기록한다.
- 관리자 로그인은 배포 후 설정한다. 설정 전 일반 고객 화면 사용은 가능하지만 공개 관리자 로그인/운영 저장은 미완료다. 실제 인증 설정·DB/AWS/기관 판정은 변경하지 않는다.
- 기존 Drive ZIP은 이번 수정 이전 제출본이다. Git/사이트와 구 ZIP을 최신 동일본으로 혼동하지 않는다. 이번에는 ZIP/Drive를 갱신하지 않는다.

## 1. 설치 없이 대시보드 확인

- [대시보드 열기](https://defense-opportunity-dashboard-doadt6mmhedzmntzqsg8oj.streamlit.app/)
- 첫 화면에서 **대시보드 바로 가기 →**를 누릅니다.
- 공고 검색 → 상세 확인, 분야별 입찰 분석, 시장 동향, 즐겨찾기를 확인할 수 있습니다.
- 휴면 상태에서 시작하면 준비 시간이 걸릴 수 있습니다.
- 고객 사이트와 고객 Git은 공개입니다. 팀 프로젝트 Git과 실제 API 인증키는 공개하지 않습니다.
- API PC·DB PC의 전원/네트워크, API 서버·HTTPS 연결이 유지되어야 실제 데이터를 조회할 수 있습니다. 클라우드 배포가 이 의존성을 제거하지는 않습니다.

## 2. 소스코드 확인

- [고객용 Git 저장소](https://github.com/ibbyeok99/defense-opportunity-dashboard)
- `소스코드_안내.md`: 폴더 구조, 모듈 용도, 각 소스 파일의 Git 링크.
- `RELEASE_MANIFEST.json`: 이 ZIP의 코드 기준 커밋과 파일별 SHA-256.
- 고객 화면과 권한 확인 후 접근하는 관리자 화면을 포함합니다. 수집기·API 서버·DB 원본·조회 근거 사본·실제 인증키는 포함하지 않습니다.
- 2026-10-04 관리자 복원 수정본은 재배포 전입니다. 기존 Drive ZIP과 공개 Git/사이트에 이번 수정이 반영되었다는 뜻이 아닙니다. 최종 전달본은 커밋·명세를 재검증한 뒤 새로 제작합니다.

### 공고 조건 표시

- 일반 목록: DB와 PC에 저장된 공식 API 면허·지역 값만 표시합니다. 미확인 값은 공란이며 제한 없음이라는 뜻이 아닙니다. 목록에서 원문/첨부 크롤링은 하지 않습니다.
- 내 회사 조건: 공고·즐겨찾기 사이드바에서 같은 입력을 사용합니다. 입력으로 일반 목록을 줄이지 않으며 상세·즐겨찾기에서 면허·지역을 비교합니다. 회사 전용 목록은 모든 공고로 통합했습니다.
- 상세: 원문·첨부 비동기 확인과 회사 조건 비교를 유지합니다. 저장 정보를 먼저 표시합니다.
- 즐겨찾기: 최대 10개 공고의 원문·첨부 조건을 자동 확인합니다. API 조건이 있는 공고도 기타 참가조건을 확인합니다. 저장값 선표시 → ‘찾는 중…’ → 완료 결과 갱신, 최대 4개 비교와 기타 참가조건·근거 펼쳐보기를 제공합니다.
- 공고 변경·24시간 만료·식별 정보 불일치는 적용하지 않습니다. 원문·첨부·발췌 사본은 전달하지 않으며 참가 가능을 확정하지 않습니다.

### 관리자 설정 — 운영 담당자 전용

- 로컬 DB 방식의 기존 관리자 로그인은 유지합니다. 공개/API 방식은 계정 로그인(OIDC) 후 허용된 계정만 관리자 메뉴를 표시합니다.
- `dashboard/.streamlit/secrets.admin.example.toml`은 설정 양식입니다. 실제 값은 공개 Git·ZIP에 넣지 않습니다. 일반 사용자/강사님 열람에는 관리자 설정이 필요 없습니다.
- 로그인 공급자에 앱을 등록하고 `auth.redirect_uri`를 앱 주소의 `/oauth2callback`으로 맞춥니다. `client_id`, `client_secret`, `server_metadata_url`, 무작위 `cookie_secret`을 Cloud Secrets에 설정합니다.
- `admin.identities`에는 공급자가 검증한 `iss|sub`를 등록합니다. 이메일/이름이나 `is_admin` 값만으로 권한을 주지 않습니다.
- API PC의 비공개 설정에는 `admin_api.token`, Cloud에는 같은 키를 `admin.api_token`으로 설정합니다. 일반 `data_api.token`과 다른 32자 이상 키를 사용합니다. 같은 키면 API 시작을 거부합니다.
- 관리자 API는 운영 상태·기관 목록·요건 감사 조회와 자동 판별 검토 확정만 허용합니다. 임의 SQL·파일 경로·명령 실행은 받지 않습니다. 판정 대기 탭은 로컬과 같이 반영 명령 생성까지만 합니다.
- 실제 로그인·운영 조회·검토 저장은 설정 후 별도 검증합니다. 이번에는 설정/운영 대장/서버를 변경하지 않았습니다.

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
| 화면·계정 로그인 | Streamlit의 auth 추가 의존성(Authlib 등) |
| 데이터·전송 | pandas, pyarrow, requests |
| 그래프 | Plotly, Altair, matplotlib |
| PDF | pypdf, pypdfium2 |
| 문서 형식 처리 | openpyxl, xlrd, olefile |
| 시간대 | tzdata |

정확한 버전은 `dashboard/requirements.txt`를 따릅니다. MySQL 드라이버·SQLAlchemy·AWS 인증은 이 고객용 API 패키지의 필수 설치 항목이 아닙니다.

## 4. 다른 운영체제

macOS/Linux에서도 Python 3.14로 `python3 start_dashboard.py --setup` 후 `.venv/bin/python start_dashboard.py`를 사용합니다. 이 제출 작업의 실제 설치 검증은 Windows 기준이며 다른 운영체제의 신규 설치는 별도 검증이 필요합니다.

## 5. 기능 범위와 오류 대응

- 저장된 공고·면허/지역·일정/금액·첨부 링크를 표시합니다. 일반 목록의 공란과 상세·즐겨찾기의 미확인은 제한 없음이나 참가 가능을 뜻하지 않습니다.
- 상세/즐겨찾기에서 공개 원문·저장된 첨부 주소를 비동기로 확인합니다. 먼저 저장 정보를 표시하고 확인 중인 요건은 ‘찾는 중…’으로 표시합니다. 공식 API 보충 조회는 별도 조회키가 필요합니다. 이 제출본에는 키·조회 사본이 없으며 전체 공고 확인 완료를 보장하지 않습니다.
- OCR 모델은 포함하지만 Tesseract 엔진은 별도입니다. 기본 저장 정보 조회에는 필요 없으며 설치 조건·라이선스는 `dashboard/assets/ocr/README.md`를 확인합니다.
- API 오류: 제출자 PC의 API/HTTPS 연결과 DB PC 상태 확인 요청. 임시 HTTPS 주소 변경 시 `secrets.toml` 주소 갱신.
- 모듈 누락: ZIP 전체 해제 여부 확인 후 `setup.cmd` 다시 실행.
- Git·사이트 접근 제한: 제출자에게 공개 전환 상태 또는 권한 확인 요청.
- 신규·변경 공고의 10분 감시는 제출자 PC·DB·사용자 로그인 상태가 필요합니다. 로그아웃/전원 종료/임시 HTTPS 주소 변경은 자동 복구하지 않습니다. 정리된 결과의 인증 API 공유와 원문 사본 전송은 다릅니다. 원문 사본은 공유하지 않습니다.
- 전체 원문·ZIP·OCR 대조 및 실제 브라우저 다운로드 파일 수신은 완료 범위와 구분합니다. 제출 검증 결과는 `검증결과.md`를 확인합니다.
