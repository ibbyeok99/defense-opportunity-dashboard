"""브라우저별 즐겨찾기와 최대 4개 공고 비교. DB·대장에는 쓰지 않는다."""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from service import data, queries
from view.favorites import render_favorites
from service.filters import Profile
from service.eligibility import STATUS_OPTIONS
from view import store
from view.navigation import page_header
from view.notice_detail import show_detail
from service.notice_requirements import fetch_evidence, poll_detail_evidence
from view.fmt import STATUS_COLORS

page_header("favorites")
regions = st.session_state.get("pf_region") or []
regions = [regions] if isinstance(regions, str) else regions
profile = Profile(tuple(regions), tuple(st.session_state.get("pf_licenses") or []))
ids = store.favorites()
detail_id = st.session_state.pop('favorite_detail', None)
rows = data.favorite_notices(ids) if ids else pd.DataFrame(columns=['notice_id'])
render_favorites(rows, requirement_reader=lambda values: queries.favorite_requirement_rows(values, poll_detail_evidence),
                 detail_builder=lambda row: queries.notice_detail(row.notice_id, profile, notice=row))
notices = rows.set_index('notice_id', drop=False)

if detail_id and detail_id in notices.index:
    detail = queries.notice_detail(detail_id, profile, notice=notices.loc[detail_id],
                                   include_competition=False)
    if detail is not None:
        show_detail(detail, datetime.now(ZoneInfo("Asia/Seoul")).date(),
                    dict(zip(STATUS_OPTIONS, STATUS_COLORS)).get(detail["status"], "gray"),
                    evidence_checker=fetch_evidence,
                    evidence_reader=poll_detail_evidence,
                    detail_updater=lambda value, result: queries.update_detail_evidence(value, profile, result),
                    competition_loader=queries.notice_competition,
                    on_evidence_updated=lambda: st.session_state.update(favorite_detail=detail["notice"]["notice_id"]))
