"""면허/지역과 분리한 기타 참가조건의 짧은 발췌와 접힌 원문 근거."""
import streamlit as st


def participation_panel(items):
    if not items:
        return
    st.markdown('**기타 참가조건 · 원문 검토 필요**')
    st.caption('확인된 참가자격 문장을 항목별로 분류했습니다. 면허와 별개이며 회사 조건과 자동 비교하지 않습니다.')
    for item in items:
        # 복잡한 예외/기준일을 확정 요약으로 바꾸지 않는다. 긴 요약의 축약은
        # 명시하고, 접힌 근거에서 모든 문장을 확인할 수 있게 한다.
        excerpt = item['summary']
        preview = excerpt if len(excerpt) <= 220 else excerpt[:220] + '… [전체 발췌 보기]'
        st.markdown('**' + item['category'] + '**')
        st.text(preview)
        if any(evidence['method'] == 'ocr' for evidence in item['evidence']):
            st.caption('이미지에서 읽은 내용 포함 · 원문 대조 필요')
        with st.expander(f"{item['category']} 근거·예외 보기 · {len(item['excerpts'])}개 문장"):
            for evidence in item['evidence']:
                st.caption(f"{evidence['source']} · {evidence['location']}")
                st.caption(f"근거 식별번호: {evidence['evidence_id']}")
                if evidence['method'] == 'ocr':
                    st.warning('이미지에서 읽은 내용입니다. 인식 오류가 있을 수 있어 원문 대조가 필요합니다.')
                if evidence['truncated']:
                    st.warning('저장 발췌가 잘려 있습니다. 원본 파일에서 뒷부분도 확인해야 합니다.')
                st.text(evidence['quote'])
