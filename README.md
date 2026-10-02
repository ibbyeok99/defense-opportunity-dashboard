# 국방조달 기회 찾기

작성: Codex · 2026-10-02

Streamlit Community Cloud 고객 화면 전용 저장소.

## 배포

- Repository: `ibbyeok99/defense-opportunity-dashboard`
- Branch: `codex/community-cloud`
- Main file path: `dashboard/streamlit_app.py`
- Python: `3.14`
- Secrets: `dashboard/.streamlit/secrets.community.example.toml` 형식에 실제 API 주소·인증키만 입력.
- DB 암호·AWS 자격증명·관리자 암호는 Cloud/Git에 입력하지 않는다.
- API·DB PC와 HTTPS 터널을 계속 실행해야 한다. 임시 터널 주소가 바뀌면 Cloud Secrets URL도 변경한다.

## 수정 반영

- 작업 원본: `C:\frontline_data\dashboard`.
- 배포 사본: `C:\frontline_data\deployment\community-cloud`.
- 원본만 수정하거나 팀 저장소 `DAUN`에만 push하면 이 Cloud 앱은 갱신되지 않는다.
- 변경한 고객 화면 파일을 배포 사본에 동기화하고 검증한 뒤 이 저장소의 `codex/community-cloud`에 commit/push한다.
- 코드·아이콘·테마·고객용 의존성만 포함한다. 실데이터·비밀값·관리자/S3/AWS·팀 저장소의 과거 커밋은 포함하지 않는다.

## 원천·범위

- `SOURCE_SNAPSHOT.json`에 최초 가져온 커밋과 코드 파일 SHA256을 기록한다.
- 데이터는 인증 HTTPS 읽기 API를 통해 기존 로컬 MySQL에서 조회한다. 데이터 사본을 Git에 저장하지 않는다.
- 관리자 화면은 API 모드에서 등록하지 않는다. 로컬 기관 판정은 기존 프로젝트에서만 수행한다.
- 공개 화면 설정과 비공개 코드 저장소 설정은 별개다.

## 고객 화면 갱신 (Codex · 2026-10-02)

- 최신 홈 영상·검정 로고, 대시보드 배경·흰 로고, 제목/부제/메뉴 배치와 카드 복원.
- 상세 모달·즐겨찾기 비교 표/상세 이동·시장 계약기관 집계/유형 그래프·필터 기본값/초기화 보정.
- 공식 분류명/기관명 표시용 공개 코드 사전만 포함. 공고·계약 원본 데이터, 기관 대장과 API 키는 저장하지 않는다.
- 관리자 로그인 함수·화면 등록·진입 버튼은 전용 진입 파일에서 제거. 로컬 관리자 구현은 변경하지 않는다.
- 앱 주소·Cloud Secrets·비공개 공유 설정은 유지한다. 갱신은 전용 브랜치 업로드로 반영한다.
