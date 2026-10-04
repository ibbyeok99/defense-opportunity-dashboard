"""준비된 화면은 유지하고, 기다리는 조회에만 로딩 상태를 표시한다."""
from contextlib import contextmanager

import streamlit as st


@contextmanager
def loading(label="자료를 불러오는 중…", *, height=None):
    """조회 전 피드백을 전송한다. 조회 실패를 빈 자료/0건으로 바꾸지 않는다."""
    with st.spinner(label, show_time=True), st.skeleton(height=height):
        yield


def read(label, reader, *args, **kwargs):
    with loading(label):
        return reader(*args, **kwargs)
