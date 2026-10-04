"""상세 창의 요청 시 요건 확인. 키·원본 파일은 화면·캐시·기록에 저장하지 않는다."""
import streamlit as st
from datetime import datetime, timedelta, timezone
from view.copy import evidence_label, korean_time, review_label, api_condition_records


def evidence_panel(notice, checker=None, on_updated=None, *, async_status=None, retry=None):
    number, order = notice.get("bidNtceNo"), notice.get("bidNtceOrd")
    if not isinstance(number, str) or not isinstance(order, str):
        parts = str(notice.get("notice_id", "")).split("|")
        number, order = parts[-2:] if len(parts) >= 3 else ("", "")
    order = order.zfill(3)
    identity = f"{number}-{order}"
    state_key = f"requirement_evidence_{notice.get('procurement_type', '')}_{identity}"
    if async_status:
        if async_status['phase'] == 'running':
            st.info('찾는 중… · ' + async_status['message'], icon=':material/autorenew:')
        elif async_status['phase'] not in {'done'}:
            st.warning(async_status['message'])
    with st.expander("원문·첨부에서 면허·지역 요건 확인", icon=":material/manage_search:"):
        st.caption("나라장터 등록정보 → 공고 원문 → 첨부파일 순서로 확인합니다. 확인된 조건은 목록·상세에 표시하며, 해석이 필요한 문장은 회사 조건과 자동 비교하지 않습니다.")
        if st.button("요건 다시 확인" if async_status else "요건 근거 확인", icon=":material/search:",
                     disabled=bool(async_status and async_status['phase'] == 'running'), key=f"check_requirements_{identity}"):
            if async_status and retry:
                retry()
                st.rerun(scope='fragment')
            elif checker is None:
                st.session_state[state_key] = {"error": "자동 확인을 이용할 수 없습니다. 나라장터 원문에서 직접 확인해 주세요."}
            else:
                with st.spinner("공식 조건과 공개 첨부를 확인 중입니다. 최대 약 90초 소요됩니다."):
                    try:
                        st.session_state[state_key] = checker(number, order, str(notice.get("procurement_type", "")))
                    except Exception:
                        st.session_state[state_key] = {"error": "요건 확인 실패. 제한 없음으로 판단하지 말고 원문을 직접 확인하세요."}
                if not st.session_state[state_key].get("error") and on_updated:
                    on_updated()
                    st.rerun()
        # 시각이 같으면 현재 규칙으로 검증한 목록 사본을 이전 세션 결과보다 우선한다.
        candidates = [r for r in (notice.get("requirement_evidence"), st.session_state.get(state_key)) if r]
        result = max(candidates, key=lambda r: r.get("checked_at", "")) if candidates else None
        if not async_status and st.session_state.get(state_key, {}).get("error"):
            result = st.session_state[state_key]
        if not result:
            return
        if result.get("error"):
            st.warning(evidence_label(result["error"]))
            return
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(result["checked_at"])
            current = timedelta(0) <= age < timedelta(hours=24)
        except (KeyError, ValueError, TypeError):
            current = False
        if not current:
            st.warning("근거 확인 후 24시간이 지났거나 확인 시각이 유효하지 않습니다. 이전 결과는 표·검색에 쓰지 않으며 다시 조회해야 합니다.")
            return
        st.caption(f"확인 공고: {identity} · 확인 시각: {korean_time(result['checked_at'])} · 재확인 주기 24시간")
        # 읽기 범위 계산은 service에서 수행한다. view는 전달받은 결과만 표시한다.
        checked_scope = result.get('coverage', dict(status='자료 확인 미완료',
            gaps=['자료 확인 범위 미기록·다시 조회 필요'], attachments_listed='미기록', attachments_read='미기록'))
        st.markdown(f"**자료 확인 범위: {review_label(checked_scope['status'])}**")
        st.caption(f"목록에 기록된 첨부 {checked_scope['attachments_listed']}개 / 텍스트를 읽은 첨부 {checked_scope['attachments_read']}개. 조회 완료는 모든 요건 확인 완료가 아닙니다.")
        if checked_scope['gaps']:
            st.warning(" · ".join(evidence_label(gap) for gap in checked_scope['gaps']))
        if result.get("resolved"):
            for kind, label in (("license", "면허"), ("region", "지역")):
                resolved = result["resolved"][kind]
                st.markdown(f"**{label}: {review_label(resolved['review'])}**" + (f" — {resolved['values']}" if resolved['values'] else ""))
            st.caption("확인 결과는 요건 표·검색에 반영됩니다. 24시간이 지나면 다시 확인합니다.")
        for kind in ("면허", "지역", "참가자격", "기타 참가조건"):
            items = [e for e in result["evidence"] if e["kind"] == kind and e.get("relevant", True)]
            direct = [e for e in items if e.get("scope") in {"공식 API", "참가자격 구역", "공개 화면 구조화 조건"}]
            related = [e for e in items if e not in direct]
            if kind in {"참가자격", "기타 참가조건"} and not items:
                continue
            st.markdown(f"**{kind} {'원문 발췌' if kind == '참가자격' else '요건 근거'}**")
            if not direct:
                st.info("읽은 자료에서 해당 조건을 찾지 못했습니다. 아직 읽지 못한 자료가 있을 수 있습니다.")
            if direct:
                with st.expander(f"{kind} 전체 발췌 보기 · {len(direct)}개 근거"):
                    for e in direct:
                        st.caption(f"{evidence_label(e['source'])} · {evidence_label(e['location'])} · {evidence_label(e['status'])}"
                                   + (f" · 조건 묶음 {e['group']} / 순번 {e['sequence']}" if e.get("group") else ""))
                        if e.get('excerpt_truncated'):
                            st.warning('저장 발췌가 잘려 있습니다. 원본 파일에서 뒷부분도 확인하세요.')
                        st.text(e.get('display_excerpt', e['excerpt']))
            if related:
                with st.expander(f"{kind} 참고 언급 {len(related)}개 · 실제 제한인지 추가 검토 필요"):
                    for e in related:
                        st.caption(f"{evidence_label(e['source'])} · {evidence_label(e['location'])} · {evidence_label(e['status'])}")
                        st.text(e.get('display_excerpt', e['excerpt']))
        with st.expander("출처·읽기 결과"):
            for source in result["sources"]:
                st.markdown(f"**{evidence_label(source['name'])}** — {evidence_label(source['status'])}")
                if source.get("url"):
                    st.link_button("공식 출처 열기", source["url"], icon=":material/open_in_new:")
                for member in source.get('archive_inventory', []):
                    st.text(f"압축파일 내부: {member['name']} — {evidence_label(member['status'])}")
                for gap in source.get('document_gaps', []):
                    st.text(f"추가 확인이 필요한 부분: {evidence_label(gap)}")
            if result["api_license_rows"]:
                st.markdown("**나라장터 등록 면허 조건 상세 기록**")
                st.json(api_condition_records(result["api_license_rows"]), expanded=False)
            if result["api_region_rows"]:
                st.markdown("**나라장터 등록 참가 가능 지역 상세 기록**")
                st.json(api_condition_records(result["api_region_rows"]), expanded=False)
        clauses = result.get("structured", {}).get("clauses", [])
        if clauses:
            with st.expander("문맥별 요건·예외·기준일", icon=":material/account_tree:"):
                st.caption("명시된 요소를 근거 문장에 연결한 검토용 결과입니다. 모두/하나 충족은 문장 단위이며 전체 참가 자격 판정이 아닙니다.")
                for clause in clauses:
                    st.caption(f"{evidence_label(clause['source'])} · {evidence_label(clause['location'])}")
                    st.caption(f"근거 식별번호: {clause['evidence_id']}")
                    fields = {"면허명·코드": ", ".join(f"{v['name']} ({v['code'] or '코드 미제공'})" for v in clause['licenses']),
                              "허용 지역 후보": ", ".join(clause['allowed_regions']), "충족 방식": clause['logic'],
                              "공동수급": clause['joint_bidding'], "공동수급 방식 후보": clause.get('joint_rule', ''), "예외": clause['exceptions'],
                              "기준일": ", ".join(clause['reference_dates'])}
                    fields["기타 참가조건 후보"] = " · ".join(v['category'] for v in clause.get('other_requirements', []))
                    fields["공장등록 산업분류·코드"] = " · ".join(f"{v['name']} ({v['code']})" for v in clause.get('factory_registrations', []))
                    st.json({k: v for k, v in fields.items() if v}, expanded=False)
                    st.text(clause['quote'])
        st.warning("모든 조건을 갖춰야 하는지, 한 조건만 갖추면 되는지와 공동수급·예외·기준일은 원문에서 확인해야 합니다. 읽지 못한 자료가 있거나 조건을 찾지 못한 경우에도 제한 없음으로 판단하지 않습니다.")
        for warning in result["warnings"]:
            st.caption(evidence_label(warning))
