# Frontline Data 대시보드 — 강사님 전달본

국방 입찰공고를 찾고, 우리 회사가 참여할 수 있는지 판단하고, 분야별 경쟁과 후보를 비교하는 대시보드입니다.

| 방법 | 필요한 것 | 걸리는 시간 |
|---|---|---|
| **A. 설치 없이 보기** | 인터넷, 브라우저 | 바로 |
| **B. 내 PC에 설치하기** | Windows, Python 3.14, API 주소·인증키(제출자가 별도 전달) | 설치에 수 분 |

---

## A. 설치 없이 보기

1. 브라우저에서 아래 주소를 엽니다.
   **https://defense-opportunity-dashboard-doadt6mmhedzmntzqsg8oj.streamlit.app/**
2. 첫 화면에서 **대시보드 바로 가기 →**를 누릅니다.
3. 상단 메뉴: `국방 입찰공고 찾기` · `분야별 입찰 분석` · `국방 조달 시장 동향` · `즐겨찾기`

| 상황 | 조치 |
|---|---|
| 처음 열 때 화면이 한참 돌아감 | 휴면 상태에서 깨어나는 중입니다. 1~2분 기다립니다. |
| "데이터 API가 응답하지 않습니다" | 데이터를 주는 제출자 PC가 꺼져 있습니다. 제출자에게 알려 주세요. |
| 관리자 화면 | 화면 맨 아래 `관리` → Google 로그인. **사전 등록된 계정만** 열립니다. 강사님 Gmail은 등록되어 있습니다. |

---

## B. 내 PC에 설치하기 (Windows)

### 준비

| 항목 | 내용 |
|---|---|
| Python | **3.14 64비트**. [python.org/downloads/windows](https://www.python.org/downloads/windows/)에서 설치 (설치 화면에서 `Add python.exe to PATH` 체크) |
| 인터넷 | 패키지 설치와 데이터 조회에 필요 |
| API 주소·인증키 | 제출자가 별도로 전달 (이 ZIP과 README에는 없음) |

### 설치 순서

1. ZIP을 **짧은 경로의 새 폴더(예: `C:\Frontline`)에 전체 해제**합니다. 압축 파일 안에서 실행하지 않습니다. 경로가 길면(약 150자 이상) 설치 중 `Long Path` 오류가 날 수 있습니다.
2. `setup.cmd`를 실행합니다. 전용 `.venv`를 만들고 패키지를 설치합니다. `설치 완료`가 나오면 끝입니다.
3. 아래 **로컬 연결 설정**을 합니다.
4. `run_dashboard.cmd`를 실행하고 브라우저에서 **http://127.0.0.1:8501** 을 엽니다.
5. 끝낼 때는 실행 창에서 `Ctrl+C`.

### 로컬 연결 설정

1. `dashboard\.streamlit\secrets.community.example.toml`을 복사해 같은 폴더에 **`secrets.toml`** 이름으로 저장합니다.
2. 메모장으로 열어 두 값만 바꿉니다. (제출자가 전달한 값)

```toml
[dashboard]
data_source = "api"

[data_api]
url = "https://YOUR-API-HOST"
token = "REPLACE_WITH_RANDOM_TOKEN_AT_LEAST_32_CHARACTERS"
```

3. 설정 확인 (선택):

```powershell
.venv\Scripts\python.exe start_dashboard.py --check       # 설정 서식 점검
.venv\Scripts\python.exe start_dashboard.py --check-api   # 실제 API 연결 확인
```

### 문제가 생기면

| 증상 | 조치 |
|---|---|
| `Python 3.14로 검증합니다` | Python 3.14 64비트를 설치하고 `setup.cmd`를 다시 실행 |
| `API 연결 설정이 없습니다` | 위 **로컬 연결 설정**의 `secrets.toml`을 만들기 |
| `HTTPS API 기본 주소를 설정하세요` / `인증키를 설정하세요` | `secrets.toml`의 `url`·`token`을 전달받은 값으로 교체 |
| `필수 패키지 누락` | ZIP 전체를 해제했는지 확인하고 `setup.cmd` 다시 실행 |
| `Long Path` 또는 `No such file or directory` (설치 중) | 압축 푼 폴더를 `C:\Frontline`처럼 짧은 경로로 옮겨 `.venv` 폴더를 지우고 `setup.cmd` 다시 실행 |
| `포트는 사용 중입니다` | `run_dashboard.cmd --port 8505` → http://127.0.0.1:8505 |
| `API 연결 실패` / 데이터가 안 나옴 | 제출자 PC의 서버가 꺼져 있거나 임시 HTTPS 주소가 바뀐 경우. 제출자에게 문의 후 `secrets.toml`의 `url` 갱신 |

---

## 안내 · 참고

### ZIP 구성

| 항목 | 내용 |
|---|---|
| 포함 | 고객 화면 4개, 관리자 화면 코드, 설치·실행 스크립트 |
| 미포함 | 데이터 수집기, API 서버, DB 원본, 인증키, 원문·첨부 사본 |
| `소스코드_안내.md` | 폴더 구조와 모듈별 용도, 소스 파일 링크 |
| `검증결과.md` | 제출 시점의 검증 기록 |
| `RELEASE_MANIFEST.json` | 코드 기준 커밋과 파일별 SHA-256 (README는 ZIP 밖에 제공) |

### 소스코드

- 공개 Git: https://github.com/ibbyeok99/defense-opportunity-dashboard

### 화면 사용 시 알아둘 점

| 항목 | 설명 |
|---|---|
| 참여 판단 | 면허·지역 조건만 비교한 **보조 판단**입니다. 상세 화면의 `충족 / 미충족 / 원문 확인 필요`로 표시합니다. **최종 참가 자격은 나라장터 공고 원문에서 확인**합니다. |
| `조건을 확인하지 못함` · 목록의 빈칸 | 제한이 없다는 뜻이 아닙니다. 아직 확인된 조건이 없다는 뜻입니다. |
| 회사 조건 입력 | 사이드바 `내 회사 조건`(소재지·보유 면허). 입력하면 일치하는 공고가 목록 위에 먼저 나옵니다. |
| 즐겨찾기 | 최대 10개 저장, 4개까지 비교. 같은 브라우저에만 저장되고 다른 기기와 동기화되지 않습니다. |
| 분야 통계 | 같은 유형·분류의 과거 통계이며 개별 공고의 경쟁을 예측하지 않습니다. |
| 데이터 갱신 | 화면 데이터는 공고 약 10분, 통계 약 1시간 단위로 다시 읽습니다. |

### 제한 사항

- 데이터는 제출자 PC의 API·DB 서버에서 옵니다. 서버가 꺼져 있으면 A·B 모두 데이터가 나오지 않습니다.
- 공개 사이트(A)는 제출자 PC 서버와 임시 HTTPS 주소에 의존합니다. 주소가 바뀌면 제출자가 갱신합니다.
- 설치 검증은 Windows 기준입니다. macOS·Linux는 `python3 start_dashboard.py --setup` 후 `.venv/bin/python start_dashboard.py`로 실행할 수 있으나 별도 검증하지 않았습니다.
- 사진 속 글자 인식(OCR) 엔진(Tesseract)은 포함하지 않습니다. 기본 조회에는 필요 없습니다.

---

Frontline Data 팀이 만들었습니다.
