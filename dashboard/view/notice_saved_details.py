"""저장된 공고 상세정보 표시. 조회·첨부 다운로드·OCR은 실행하지 않는다."""
import re

import streamlit as st


def _plain(value):
    """공고문에 Markdown 링크·지시문이 있어도 단순 텍스트로 표시한다."""
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|:~\-])", r"\\\1", str(value))


def saved_details_panel(details: dict):
    if not details:
        return
    with st.container(border=True, key="detail_saved_information", gap="small"):
        st.subheader("저장된 공고 상세정보", anchor=False)
        st.caption("현재 확인할 수 있는 공고 정보입니다. 면허·지역 요건 확인 진행 상황은 위에 표시합니다. ‘미제공’은 확인된 정보가 없다는 뜻입니다.")
        if not details.get("extra_available"):
            st.caption("현재는 기본 정보만 확인할 수 있습니다. 추가 정보는 나라장터 원문에서 확인해야 합니다.")
        for key, title in (("schedule", "입찰 일정"), ("price", "금액·낙찰 기준"),
                           ("participation", "입찰 방식·공동수급")):
            with st.expander(title, expanded=key == "schedule"):
                st.table({label: _plain(value) for label, value in details[key].items()}, border="horizontal")
                if key == "schedule":
                    st.caption("한국시간 기준. 저장된 예정 시각이며 실제 진행·완료 상태를 뜻하지 않습니다.")
                elif key == "price":
                    st.caption("배정예산과 추정가격은 서로 다른 금액입니다. 사업금액·기초금액을 계산해 채우지 않으며, "
                               "부가세 포함 여부는 저장된 필드만으로 단정하지 않습니다. 외자는 통화가 없으면 단위를 추정하지 않습니다.")
                else:
                    st.caption("공동수급·재입찰 값은 저장된 안내이며, 회사의 최종 참가자격 판정은 아닙니다.")
        with st.expander("첨부파일·관련 번호"):
            attachments = details.get("attachments", [])
            if not attachments:
                st.caption("첨부파일 목록 미제공. 첨부가 없다는 뜻은 아닙니다.")
            for index, attachment in enumerate(attachments):
                st.text(attachment["name"])
                if attachment["url"]:
                    st.link_button("나라장터 첨부파일 열기", attachment["url"], icon=":material/attach_file:",
                                   key=f"detail_saved_attachment_{index}")
                else:
                    st.caption(attachment["note"])
            st.caption("클릭한 파일만 나라장터에서 엽니다. 파일 내용·크기는 추가 조회하지 않습니다.")
            st.table({label: _plain(value) for label, value in details["related"].items()}, border="horizontal")
