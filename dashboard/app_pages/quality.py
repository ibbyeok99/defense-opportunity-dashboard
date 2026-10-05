import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from service import data, admin_access
from service import publish_status
from service import source
from service.requirement_audit import audit_requirements
from view.fmt import CAVEATS, pct
from view.quality import checks_for_display, csv_download
from view.reference_table import reference_table

if not admin_access.authorized():
    st.error('관리자만 볼 수 있습니다.')
    st.stop()

st.markdown("### 이 대시보드의 데이터 기준")
from view.loading import read
meta = read('게시 버전과 데이터 기준을 확인하는 중…', data.metadata)
with st.container(horizontal=True, border=True, key="card_quality_metadata"):
    st.metric("통계 게시 세대", (meta.get("snapshot_id") or "확인 필요")[:8] + ("…" if meta.get("snapshot_id") else ""),
              help=meta.get("run_id") or "활성 적재 이력을 확인하지 못했습니다.")
    low, high = meta.get("data_as_of_min"), meta.get("data_as_of_max")
    st.metric("통계 자료 기준", (f"{low[:10]} ~ {high[:10]}" if low and high and low[:10] != high[:10]
                                 else publish_status.short_time(high or meta.get("data_as_of"))[:10]),
              help=f"게시 통계 행의 자료 기준 시각 범위: {publish_status.data_range(meta)}. 변경된 부분만 갱신해 표마다 다를 수 있으며, "
                   "수집기의 마지막 성공 시각이 아닙니다.")
    st.metric("DB 최근 반영 확인", publish_status.applied_at(meta)[:16],
              help="완료된 DB 적재 이력의 마지막 시각입니다. 변경분이 없는 회차도 포함합니다. " + publish_status.applied_note(meta))
    # 확인되지 않은 값은 카드로 보여주지 않는다(점검 표와 세부 영역에는 그대로 남는다). 정상·실패만 카드로 표시한다.
    if publish_status.status_label(meta) in {"정상", "실패"}:
        st.metric("게시 상태", publish_status.status_label(meta),
                  help="통계표 행의 세대가 소유 대장·적재 이력과 맞는지 읽기 전용으로 대조한 결과입니다.")
    basis = str(meta.get("contract_population_basis") or "")
    if "ANALYTICAL_REPRESENTATIVES" in basis:
        st.metric("계약 집계 범위", "분석용 대표 계약",
                  help="전체 원천 계약이 아니라 분석 규칙을 통과한 대표 계약 기준입니다.")
if data.SOURCE in {'mysql', 'api'}:
    if not publish_status.has_detail(meta):
        st.info('게시 세대 정보를 제공하지 않는 구버전 응답입니다. 자료 기준 범위와 소유 대장 대조는 확인 필요로 둡니다.')
    else:
        if meta.get('mixed_generations'):
            st.info('변경된 부분만 갱신하므로 통계별 자료 기준 시각과 게시 세대는 표마다 다를 수 있습니다. 여러 세대가 함께 있는 것 자체는 오류가 아닙니다.')
        problems = publish_status.exception_tables(meta)
        hard = [t for t, (is_hard, _) in problems.items() if is_hard]
        if hard and publish_status.convention_verified(meta):   # 세대 대응 규약을 검증한 뒤에만 확정 문제로 올린다
            st.error('소유 대장 대조 예외: ' + ', '.join(sorted(hard)) + '. 소유 대장에 없거나 행 수가 다른 파티션이 있습니다.')
        ledger = meta.get('ledger') or {}
        if ledger.get('state') != '확인':
            st.info('활성 적재 이력을 확인하지 못했습니다: ' + (ledger.get('reason') or '사유 미상') + '. 게시 상태를 정상으로 표시하지 않습니다.')
        elif publish_status.applied_note(meta):
            st.caption(publish_status.applied_note(meta))
if meta.get('table_version_states'):
    with st.expander('표별 게시 세대·자료 기준 확인 결과'):
        differing = publish_status.exception_tables(meta)
        if differing:
            st.caption('행 run_id와 적재 대장 run_id가 다른 파티션이 있는 표: ' + ', '.join(sorted(differing)) +
                       ' — 행의 run_id는 묶음을 계산한 실행(생성 세대), 적재 대장의 run_id는 DB에 적재한 실행(적재 세대)일 수 있어 '
                       '다르다는 것만으로 오류로 판단하지 않습니다. 매니페스트의 파일 참조·해시·행 수로 대응을 확인하기 전까지 정상/실패를 정하지 않고 확인 필요로 둡니다.')
        version_rows = []
        for table, state in meta['table_version_states'].items():
            summary = (meta.get('table_generations') or {}).get(table) or {}
            check = (meta.get('ownership_checks') or {}).get(table) or {}
            version_rows.append(dict(
                표=table, 확인=state, 세대수=summary.get('generations', '–'), 행수=summary.get('rows', '–'),
                자료기준_최소=publish_status.short_time(summary.get('as_of_min')) if summary else '–',
                자료기준_최대=publish_status.short_time(summary.get('as_of_max')) if summary else '–',
                대장_예외=(max(check.get('wrong_owner', 0), check.get('unverified_run', 0)) + check.get('missing_owner', 0) + check.get('wrong_count', 0)) if check.get('checked') else '–'))
        st.dataframe(pd.DataFrame(version_rows), hide_index=True)

with st.container(border=True, key="card_quality_rules"):
    st.markdown("**화면에서 꼭 지키는 해석 규칙**")
    for k in ("competition", "contract_amount", "new_supplier", "followup", "unknown_condition", "partial_year",
              "no_score"):
        st.markdown(f"- {CAVEATS[k]}")

with st.container(border=True, key="card_quality_links"):
    links = read('단계별 연결률을 불러오는 중…', data.link_quality)
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.markdown("**단계별 연결률** (공고 → 개찰 → 낙찰 → 계약)")
        csv_download(links, "단계별_연결률", "dq_csv_links")
    # 작은 정적 표는 셀 내용이 자연스럽게 줄바꿈되도록 표시한다.
    shown_links = links.rename(columns={"metric": "연결", "numerator": "연결됨", "denominator": "전체",
                                        "rate": "연결률", "note": "기준"})
    reference_table(shown_links, key="dq_links_table", label="단계별 연결률",
                    formats={"연결됨": "integer", "전체": "integer", "연결률": "percent"},
                    widths={"연결": 210, "연결됨": 110, "전체": 110, "연결률": 110, "기준": 320})

with st.container(border=True, key="card_quality_checks"):
    checks = read('DB 연결·게시 버전을 점검하는 중…', data.run_checks)
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.markdown("**DB 연결 및 게시 버전 점검**")
        csv_download(checks, "DB_게시버전_점검", "dq_csv_checks")
    st.caption("자동 점검 결과: 통과·실패·확인 필요")
    reference_table(checks_for_display(checks), key="dq_checks_table", label="DB 연결 및 게시 버전 점검",
                    badge_columns=("점검 결과",))

with st.container(border=True, key="card_quality_requirements"):
    now = datetime.now(ZoneInfo('Asia/Seoul')).replace(tzinfo=None)
    audit = None
    if data.SOURCE == 'api':
        from service.admin_transport import client
        from service.api_transport import DataAPIError
        try:
            audit = client().read('requirement-audit')
            now = datetime.fromisoformat(audit['checked_at']).replace(tzinfo=None)
        except (DataAPIError, ValueError, TypeError, KeyError):
            st.error('공고 요건 조회 상태 확인 실패. 관리자 API 연결을 확인하세요. 실패를 0건으로 표시하지 않습니다.')
    else:
        audit = audit_requirements(data._base_notices(), source.read_requirement_evidence(include_expired=True),
                                  now, source.read_requirement_failures())
    if audit is not None:
        st.markdown("**마감 전 공고의 면허·지역 요건 조회 상태**")
        st.caption(f"{now:%Y-%m-%d %H:%M} KST · 원본에서 면허 또는 지역이 미확인인 {audit['target']:,}건. "
                   "저장된 조회 이력만 점검하며 공식 API를 자동 호출하지 않습니다. 조회 완료는 참가 자격 확정을 뜻하지 않습니다.")
        stages = pd.DataFrame(list(audit['stages'].items()), columns=['조회 상태', '공고 수'])
        csv_download(stages, '공고_요건_조회상태', 'dq_csv_requirement_stages')
        reference_table(stages, key='dq_requirement_stages', label='공고 요건 조회 상태', formats={'공고 수': 'integer'})
        reasons = pd.DataFrame([{'요건': {'license': '면허', 'region': '지역'}[kind], '보완 상태': status, '공고 수': count}
                               for kind, statuses in audit['reasons'].items() for status, count in statuses.items()])
        csv_download(reasons, '공고_요건_보완상태', 'dq_csv_requirement_reasons')
        reference_table(reasons, key='dq_requirement_reasons', label='공고 요건 보완 상태', formats={'공고 수': 'integer'})
        st.caption("‘확인 자료에서 근거 미탐지’·자료 미제공·추출 실패·이미지 원문 대조 필요는 제한 없음이 아닙니다. "
                   "자료 버전 불일치는 공고 제목·마감이 공식 조회 결과와 달라 보완값을 적용하지 않은 상태입니다.")

with st.container(border=True, key="card_quality_details"):
    cov = read('계약 상세 연결 범위를 불러오는 중…', data.detail_coverage).dropna(subset=["year"])
    shown_cov = cov[["procurement_type", "year", "contract_count", "contracts_with_linked_details",
                     "detail_contract_coverage", "period_status"]]
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.markdown("**계약상세(실제 구매 품목) 연결 범위**")
        csv_download(shown_cov, "계약상세_연결범위", "dq_csv_details")
    reference_table(shown_cov.rename(columns={"procurement_type": "유형", "year": "연도", "contract_count": "계약",
                    "contracts_with_linked_details": "상세 연결", "detail_contract_coverage": "상세 연결률", "period_status": "범위 상태"}),
                    key="dq_details_table", label="계약상세 연결 범위", height=400,
                    formats={"연도": "plain_integer", "계약": "integer", "상세 연결": "integer", "상세 연결률": "percent"},
                    progress_columns=("상세 연결률",))
    st.caption("상세가 연결되지 않은 계약은 품목 금액에 포함되지 않습니다. 표시된 금액은 전체 시장규모가 아닙니다.")

with st.container(border=True, key="card_quality_availability"), st.expander(
        "원천 자료 가용성 (수집 항목·연도별)", icon=":material/table_view:"):
    dq = read('원천 자료 가용성을 불러오는 중…', data.data_quality)
    if "status" in dq.columns:
        status = st.multiselect("상태", sorted(dq["status"].dropna().unique()), key="dq_status")
        shown_quality = dq[dq["status"].isin(status)] if status else dq
    else:
        areas = sorted(dq["area"].dropna().unique()) if "area" in dq.columns else []
        selected_areas = st.multiselect("영역", areas, key="dq_area") if areas else []
        shown_quality = dq[dq["area"].isin(selected_areas)] if selected_areas else dq
    csv_download(shown_quality, "원천자료_가용성", "dq_csv_availability")
    reference_table(shown_quality, key="dq_availability_table", label="원천 자료 가용성", height=400,
                    formats={"year": "plain_integer"} if "year" in shown_quality else {})

st.caption(f"현재 저장된 전체 공고 중 면허 조건 미확인 비율: {pct((data.notices()['license_state'] == '미확인').mean())}. "
           "수집기 마지막 성공 시각은 관리자 → 운영 상태에서 확인할 수 있습니다.")
