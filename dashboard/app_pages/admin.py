"""관리자 화면 — 로그인한 관리자만 보인다(streamlit_app.py에서 조건부로 등록).

Pending은 기존 judge 명령 안내를 유지한다. 자동판별 검토는 전용 S3 작업으로
수집기와 같은 임대 잠금을 잡고 반영한다. 사람이 원본 엑셀을 직접 편집하지 않는다.
"""

import re
import uuid

import pandas as pd
import streamlit as st

from service import data, admin_access
from service import automatic_review
from service import source
from service.operations import warning, WARNING_HOURS
from view.reference_table import reference_table
from view.loading import read

if not admin_access.authorized():
    st.error("관리자만 볼 수 있습니다.")
    st.stop()

st.markdown("### 관리자")
meta = read('관리자 데이터 기준을 확인하는 중…', data.metadata)
st.info(f"게시 데이터 기준 시각: {str(meta.get('data_as_of', '확인 필요'))[:16]}",
        icon=":material/science:")
tab_operations, tab_pending, tab_automatic = st.tabs(["운영 상태", "기관 판정 대기", "자동 판별 기관 검토"])

with tab_operations, st.container(border=True):
    st.markdown("**:material/sync: 데이터 새로고침**")
    st.caption(f"공고는 {data.NOTICE_TTL}, 통계는 {data.STATS_TTL}마다 저절로 다시 읽습니다. 게시 버전을 바꾼 직후 "
               "바로 반영하려면 누르세요.")
    if st.button("지금 다시 읽기", icon=":material/refresh:"):
        st.cache_data.clear()
        st.toast("다시 읽었습니다.", icon=":material/check:")

with tab_pending, st.container(border=True):
    st.markdown("**:material/rule: 기관 판정 대기**")
    st.caption("국방 여부를 자동으로 정하지 못한 기관입니다. 판정값을 선택하면 반영 명령을 생성합니다. 이 화면에서는 운영 기관 대장에 저장하지 않습니다.")
    pending = read('기관 판정 대기 목록을 확인하는 중…', data.pending_institutions)
    demo = st.toggle("예시 데이터로 화면 보기", value=pending.empty,
                     help="판정 대기 기관이 없을 때 화면 동작을 확인하는 용도입니다. 실제 기관이 아닙니다.")
    if demo:
        pending = pd.DataFrame([
            {"institution_code": "Z000001", "institution_name_raw": "(예시) 국군○○지원단",
             "institution_roles": "수요기관", "first_observed_date": "2026-09-28",
             "classification_reason": "규칙 불일치: 이름에 국방 키워드 있으나 상위기관 미상"},
            {"institution_code": "Z000002", "institution_name_raw": "(예시) ○○시 시설관리공단",
             "institution_roles": "공고기관", "first_observed_date": "2026-09-28",
             "classification_reason": "규칙 불일치: 계층 접두 없음"},
        ])
    if pending.empty:
        st.success("판정 대기 기관이 없습니다.", icon=":material/task_alt:")
    else:
        if "judgments" not in st.session_state:
            st.session_state.judgments = {}
        todo = pending[~pending["institution_code"].isin(st.session_state.judgments)]
        st.progress(1 - len(todo) / len(pending), text=f"{len(pending) - len(todo)} / {len(pending)} 판정")
        reviewer = st.text_input("판정자 이름", key="adm_reviewer")
        if len(todo):
            row = todo.iloc[0]
            # 기관이 바뀌면 별도 위젯으로 그려 이전 기관의 선택을 물려받지 않는다.
            judge_key = f"judge_{'demo' if demo else 'pending'}_{row['institution_code']}"
            with st.form(judge_key, border=True):
                st.markdown(f"**{row['institution_name_raw']}** `{row['institution_code']}`")
                st.caption(f"역할 {row.get('institution_roles', '–')} · 처음 관측 {row.get('first_observed_date', '–')}")
                st.caption(f"자동 판정 못 한 이유: {row.get('classification_reason', '–')}")
                verdict = st.segmented_control("국방 기관인가요?", ["Y", "N"], required=True, default=None,
                                               format_func={"Y": "예 (국방)", "N": "아니오"}.get,
                                               key=f"{judge_key}_verdict")
                if st.form_submit_button("반영 명령에 추가", type="primary"):
                    if verdict is None:
                        st.warning("예/아니오를 골라 주세요.")
                    else:
                        st.session_state.judgments[row["institution_code"]] = verdict
                        st.rerun()
        if st.session_state.judgments:
            decisions = ",".join(f"{c}={v}" for c, v in st.session_state.judgments.items())
            safe_reviewer = re.sub(r"[^\w가-힣 .-]", "", reviewer).strip() or "이름"
            st.markdown("아직 운영 기관 대장에 저장되지 않았습니다. 운영 담당자가 수집기 실행 환경에서 아래 명령을 실행하면 S3 운영 기관 대장에 반영됩니다.")
            st.code(f'python data/g2b_live/collector/run.py judge --backend s3 --decisions "{decisions}" '
                    f'--reviewer "{safe_reviewer}"', language="bash")
            if st.button("판정 다시 하기", icon=":material/undo:"):
                st.session_state.judgments = {}
                st.rerun()

with tab_automatic:
    st.caption(f"검토 범위: 과거 검토 완료 목록에 없는 기관 중 {automatic_review.LIVE_REVIEW_START:%Y-%m-%d} 이후 처음 수집된 기관입니다.")
    st.caption("수정할 기관만 선택해 국방 여부와 메모를 입력해 주세요. 선택하지 않은 기관은 기존 자동 판별을 유지합니다. "
               "‘이번 검토 확정’을 누르면 목록 전체의 검토 결과를 S3 운영 기관 대장에 저장합니다.")
    connected = True
    baseline = None
    try:
        baseline = automatic_review.historical_codes()
        automatic, receipts = automatic_review.snapshot()
        automatic = automatic_review.live_new_rows(automatic, baseline)
        existing_batch = st.session_state.get("adm_auto_batch")
        if existing_batch and existing_batch["batch_id"] in receipts["batches"]:
            for key in ("adm_auto_batch", "adm_auto_selection", "adm_auto_drafts"):
                st.session_state.pop(key, None)
        if "adm_auto_batch" not in st.session_state and receipts.get("pending_requests"):
            saved = receipts["pending_requests"][0]
            st.session_state.adm_auto_batch = {"batch_id": saved["batch_id"], "rows": saved["rows"],
                                               "attempt": {"decisions": saved["decisions"], "reviewer": saved["reviewer"]}}
            st.session_state.adm_auto_selection = list(saved["decisions"])
            st.session_state.adm_auto_drafts = saved["decisions"]
            st.info("S3의 미완료 검토를 복원했습니다. 기존 내용으로 재확인해야 새 검토를 시작할 수 있습니다.")
    except Exception as exc:
        connected = False
        automatic = (automatic_review.live_new_rows(data.automatic_institutions(), baseline)
                     if baseline is not None else pd.DataFrame())
        # 비밀값/서버 응답을 그대로 출력하지 않는다. 판정은 실패 폐쇄한다.
        st.warning("S3 운영 기관 대장을 읽지 못했습니다. 연결·접근 권한을 확인한 후 다시 읽어 주세요. 참고 목록만 표시하며, 검토 확정은 할 수 없습니다.")
        if baseline is None:
            st.error("과거 검토 기준을 읽지 못해 신규 기관 범위를 확인할 수 없습니다. 목록 표시와 확정을 막았습니다.")
    existing_batch = st.session_state.get("adm_auto_batch")
    if existing_batch and baseline is not None:
        scoped, valid = automatic_review.scope_batch(existing_batch, baseline)
        st.session_state.adm_auto_batch = scoped
        if not valid:
            connected = False
            st.error("이전 제출 목록에 현재 검토 대상이 아닌 기관이 있습니다. 제출 기록은 보존했습니다. 운영 담당자가 대상 목록을 확인하기 전에는 다시 확정할 수 없습니다.")
        elif not scoped["rows"]:
            for key in ("adm_auto_batch", "adm_auto_selection", "adm_auto_drafts"):
                st.session_state.pop(key, None)
        elif not scoped.get("attempt"):
            allowed = {row["_review_id"] for row in scoped["rows"]}
            if "adm_auto_selection" in st.session_state:
                st.session_state.adm_auto_selection = [i for i in st.session_state.adm_auto_selection if i in allowed]
            if "adm_auto_drafts" in st.session_state:
                st.session_state.adm_auto_drafts = {i: d for i, d in st.session_state.adm_auto_drafts.items() if i in allowed}
    flash = st.session_state.pop("adm_auto_success", None)
    if flash:
        st.success(f"이번 검토 {flash['count']}건을 확정했습니다. 수정한 {flash['changed']}건의 국방 여부·메모를 S3 운영 기관 대장에 반영했습니다.")
    failed = st.session_state.pop("adm_auto_error", None)
    if failed:
        st.error(failed)
    if baseline is None:
        st.info("신규 기관 검토 범위를 확인한 뒤 목록을 표시합니다.")
    elif automatic.empty and "adm_auto_batch" not in st.session_state:
        st.info("새로 검토할 자동 판별 기관이 없습니다.")
    else:
        if "_review_id" not in automatic:
            automatic = automatic.copy()
            automatic["_review_id"] = [automatic_review.protocol.observation_id(r) for r in automatic.to_dict("records")]
        if "adm_auto_batch" not in st.session_state:
            st.session_state.adm_auto_batch = {"batch_id": uuid.uuid4().hex, "rows": automatic.to_dict("records")}
        batch = st.session_state.adm_auto_batch
        rows = batch["rows"]
        by_id = {r["_review_id"]: r for r in rows}
        attempt = batch.get("attempt")
        st.caption(f"이번 검토 대상 {len(rows)}건 · 검토 중 새로 들어온 기관은 다음 목록에서 표시합니다.")
        shown = pd.DataFrame(rows).rename(columns={"institution_code": "기관코드", "institution_name_raw": "기관명",
                                                   "is_defense": "자동 판별", "classification_reason": "포함·제외 근거"})
        shown['자동 판별'] = shown['자동 판별'].map(lambda value: {'Y': '예 (국방)', 'N': '아니오'}.get(value, value))
        reference_table(shown[["기관코드", "기관명", "자동 판별", "포함·제외 근거"]],
                        key="adm_automatic_table", label="자동 판별 기관 검토", height=400,
                        widths={"기관코드": 112, "기관명": 240, "자동 판별": 100, "포함·제외 근거": 400})
        reviewer = st.text_input("검토자 이름", key="adm_auto_reviewer")
        st.markdown("#### 수정할 기관")
        selected = st.multiselect("수정할 기관", list(by_id), key="adm_auto_selection", disabled=bool(attempt),
                                  label_visibility="collapsed",
                                  format_func=lambda i: f"{by_id[i]['institution_name_raw']} ({by_id[i]['institution_code']}) · { {'Y': '예 (국방)', 'N': '아니오'}.get(by_id[i]['is_defense'], by_id[i]['is_defense']) }")
        drafts = st.session_state.setdefault("adm_auto_drafts", {})

        def remember_review(identity, field, widget_key):
            st.session_state.adm_auto_drafts.setdefault(identity, {})[field] = st.session_state[widget_key]

        for identity in selected:
            row = by_id[identity]
            saved = drafts.get(identity, {})
            with st.container(border=True):
                st.markdown(f"**{row['institution_name_raw']}** · `{row['institution_code']}`")
                st.caption(f"자동 판별: { {'Y': '예 (국방)', 'N': '아니오'}.get(row['is_defense'], row['is_defense']) } · 근거: {row.get('classification_reason', '미확인')}")
                verdict_key, note_key = f"adm_auto_{identity}_verdict", f"adm_auto_{identity}_note"
                st.segmented_control("국방 기관 판정", ["Y", "N"], default=saved.get("verdict"), disabled=bool(attempt),
                                     format_func={'Y': '예 (국방)', 'N': '아니오'}.get,
                                     key=verdict_key, on_change=remember_review, args=(identity, "verdict", verdict_key))
                st.text_area("검토 메모", value=saved.get("note", ""), max_chars=2000, disabled=bool(attempt),
                             key=note_key, on_change=remember_review, args=(identity, "note", note_key))
        if attempt:
            st.info("이전 제출 내용으로 재확인합니다. 이미 반영된 내용을 덮어쓰지 않도록 국방 여부·메모는 수정할 수 없습니다.")
        if st.button("이번 검토 확정" if not attempt else "같은 검토 다시 확인", type="primary", key="adm_auto_confirm",
                     disabled=not connected or (not attempt and not reviewer.strip())):
            decisions = {i: dict(drafts.get(i, {})) for i in selected}
            if not attempt and any(d.get("verdict") not in ("Y", "N") for d in decisions.values()):
                st.warning("선택한 기관 모두 국방 여부를 골라 주세요.")
            else:
                if attempt is None:
                    for decision in decisions.values():
                        decision.setdefault("note", "")
                    attempt = {"decisions": decisions, "reviewer": reviewer.strip()}
                    batch["attempt"] = attempt
                try:
                    with st.spinner("S3 운영 기관 대장에 검토 결과를 반영하고 있습니다."):
                        result = automatic_review.confirm(rows, attempt["decisions"], attempt["reviewer"], batch["batch_id"])
                    automatic_review.snapshot.clear()
                    st.session_state.adm_auto_success = {"count": len(rows), "changed": result["changed"]}
                    for key in ("adm_auto_batch", "adm_auto_selection", "adm_auto_drafts"):
                        st.session_state.pop(key, None)
                    st.rerun()
                except ValueError as exc:
                    st.session_state.adm_auto_error = str(exc)
                    st.rerun()
                except Exception as exc:
                    st.session_state.adm_auto_error = f"S3 검토 처리 오류 ({type(exc).__name__}). 완료 기록을 재조회합니다. 미완료면 같은 내용으로 다시 확인하세요."
                    automatic_review.snapshot.clear()
                    st.rerun()

with tab_operations, st.container(border=True):
    st.markdown("**:material/monitor_heart: 수집·게시 상태**")
    meta = data.metadata()
    st.markdown(f"- 통계 게시 버전: `{meta.get('run_id', '–')}` (기준 {str(meta.get('data_as_of', '–'))[:16]})")
    status = read('수집기의 최근 성공과 대기 건수를 확인하는 중…', source.read_collector_operations)
    with st.container(horizontal=True):
        success = status.get('last_success')
        st.metric('수집기 마지막 성공', success[:16].replace('T',' ') if success else '확인 실패' if status.get('errors') else '24시간 내 기록 없음')
        for field, label in (('repair_pending','보정 대기'), ('judgment_pending','기관 판정 대기')):
            count = status.get(field)
            st.metric(label, f'{count:,}건' if count is not None else '확인 실패')
    issue = warning(status)
    if issue:
        st.badge(issue, color='orange')
    st.caption(f"마지막 확인: {status['checked_at'][:16].replace('T',' ')} 한국시간 · 60초 캐시 · 수집 지연 경고 기준 {WARNING_HOURS}시간")
    st.caption('성공 시각은 최근24시간 최종 종료 로그(RUN00·exit0), 대기 수는 S3 운영 대장 기준입니다. 게시 데이터 기준 시각과 다릅니다. 조회만 하며 수집·판정·보정은 실행하지 않습니다.')
    if status.get('repair_given_up'):
        st.caption(f"별도 원인 확인 대상(보정 포기): {status['repair_given_up']:,}건")
    for message in status.get('errors', []):
        st.caption(message)
    st.markdown("- 다음 통계 게시 시각: 확인된 일정이 없습니다.")
