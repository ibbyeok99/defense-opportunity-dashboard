"""브라우저 저장(localStorage) — 내 회사 조건·마지막 공고 필터·저장한 검색을 다음 접속 때 되살린다.

- 저장 위치는 **사용자의 브라우저**뿐이다(서버·다른 사람에게 저장되지 않음). 같은 PC·같은 브라우저에서만 유지된다.
- 흐름: 첫 실행 때 JS가 저장값을 한 번 올려 보냄(trigger 'loaded') → 콜백이 위젯 값으로 넣음 →
  그 뒤 매 실행 끝에 현재 값을 내려보내 JS가 저장.
- 브라우저가 저장을 막으면(사생활 보호 모드 등) 그 접속 동안만 유지된다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, timedelta

import streamlit as st
from view.favorite_snapshot import clean as clean_snapshots, snapshot

STORAGE_KEY = "frontline_dashboard_prefs_v1"
COMPONENT_KEY = "_browser_store"
PROFILE_KEYS = ("pf_region", "pf_licenses")
FILTER_KEYS = ("nt_kw", "nt_when", "nt_types", "nt_agency_role", "nt_agency_수요기관", "nt_agency_공고기관",
               "nt_scope", "nt_dates", "nt_open_only")

# 목록 범위(2026-09-29: 사이드바 '참여 판단' 여러 개 선택 → 목록 위 두 개 선택)
SCOPE_ALL = "모든 공고"
SCOPE_COMPANY = "내 회사 조건에 맞는 공고"
SCOPE_OPTIONS = [SCOPE_ALL]  # 회사 전용 목록은 일반 탐색으로 통합. 입력/상세 비교는 유지.


def initial_notice_filters(today: date, types: list[str]) -> dict:
    """첫 접속·필터 초기화: 오늘을 포함한 최근 7일, 전체 유형. 저장값은 별도 복원한다."""
    return {"nt_kw": "", "nt_when": WHEN_DEFAULT, "nt_types": list(types),
            "nt_agency_role": "수요기관", "nt_agency_수요기관": [], "nt_agency_공고기관": [],
            "nt_scope": SCOPE_ALL, "nt_item": None, "nt_dates": (today - timedelta(days=6), today),
            "nt_open_only": False}

# '공고 기간' 선택 1개 = 예전 '진행 상태' + '마감까지' 두 칸(2026-09-29 사이드바 정리, 문구는 같은 날 피드백).
# 값 → service 필터의 (status, deadline)
WHEN_TO_FILTER = {"마감 전 전체": ("마감 전", "전체"), "7일 이내 마감": ("마감 전", "7일 안"),
                  "30일 이내 마감": ("마감 전", "30일 안"), "최근 1개월 공고 (마감 포함)": ("최근 1개월", "전체")}
WHEN_OPTIONS = list(WHEN_TO_FILTER)
WHEN_DEFAULT = "마감 전 전체"
_WHEN_RENAMED = {"마감 7일 안": "7일 이내 마감", "마감 30일 안": "30일 이내 마감",
                 "최근 1개월 공고": "최근 1개월 공고 (마감 포함)"}


def _upgrade(filters: dict) -> dict:
    """예전 저장값(nt_status·nt_deadline)을 nt_when으로 바꾼다. 브라우저 저장·저장한 검색 호환용."""
    filters = dict(filters)
    if "nt_scope" in filters:
        filters["nt_scope"] = SCOPE_ALL
    if filters.get("nt_when") in _WHEN_RENAMED:
        filters["nt_when"] = _WHEN_RENAMED[filters["nt_when"]]
    if "nt_when" not in filters and ("nt_status" in filters or "nt_deadline" in filters):
        if filters.get("nt_status") == "최근 1개월":
            filters["nt_when"] = "최근 1개월 공고 (마감 포함)"
        else:
            filters["nt_when"] = {"7일 안": "7일 이내 마감", "30일 안": "30일 이내 마감"}.get(
                filters.get("nt_deadline"), WHEN_DEFAULT)
    filters.pop("nt_status", None)
    filters.pop("nt_deadline", None)
    filters.pop("nt_judge", None)      # 예전 '참여 판단' 여러 개 선택은 쓰지 않는다
    if "nt_dates" in filters:
        try:
            values = filters["nt_dates"]
            filters["nt_dates"] = tuple(date.fromisoformat(v) if isinstance(v, str) else v for v in values)
            if len(filters["nt_dates"]) > 2 or not all(isinstance(v, date) for v in filters["nt_dates"]):
                filters.pop("nt_dates")
        except (TypeError, ValueError):
            filters.pop("nt_dates", None)
    if "nt_open_only" not in filters and "nt_when" in filters:
        filters["nt_open_only"] = filters["nt_when"] != "최근 1개월 공고 (마감 포함)"
    return filters
MAX_PRESETS = 8
MAX_FAVORITES = 10


def clean_favorites(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(v for v in value if isinstance(v, str) and 0 < len(v) <= 512))[:MAX_FAVORITES]


def favorites() -> list[str]:
    return clean_favorites(st.session_state.setdefault("favorite_notices", []))


def toggle_favorite(notice_id: str):
    items = favorites()
    if notice_id in items:
        items.remove(notice_id)
        st.session_state.setdefault('favorite_snapshots', {}).pop(notice_id, None)
        st.session_state.setdefault('_favorite_request_sources', {}).pop(notice_id, None)
    elif len(items) < MAX_FAVORITES:
        items.append(notice_id)
    else:
        st.toast("즐겨찾기는 최대 10개입니다. 기존 공고를 해제한 뒤 추가하세요.")
        return
    st.session_state.favorite_notices = items
    if notice_id in items:
        row = st.session_state.get('_favorite_available_sources', {}).get(notice_id)
        if row is not None:
            st.session_state.setdefault('_favorite_request_sources', {})[notice_id] = row.copy()
            remember_favorite(row)


def remember_sources(rows):
    """표시 중인 최대20건과 저장된10건만 유지. 저장 버튼에서 참조한다."""
    available = st.session_state.setdefault('_favorite_available_sources', {})
    for row in rows.to_dict('records'):
        available[row['notice_id']] = row
        if row['notice_id'] in favorites():
            st.session_state.setdefault('_favorite_request_sources', {})[row['notice_id']] = row.copy()
    keep = set(favorites()) | set(rows.notice_id.tolist()[-20:])
    st.session_state['_favorite_available_sources'] = {k: v for k, v in available.items() if k in keep}


def remember_favorite(row):
    notice_id = row.get('notice_id')
    if notice_id in favorites():
        records = st.session_state.setdefault('favorite_snapshots', {})
        old = records.get(notice_id, {}).get('row', {})
        unchanged = all(str(row.get(k, '')) == old.get(k, '') for k in ('notice_name', 'bid_close_date'))
        if unchanged and old.get('requirement_checked_at') and not row.get('requirement_checked_at'):
            return  # 확인 중인 기본 행으로 완료 사본을 덮지 않는다.
        candidate = snapshot(row)
        if old == candidate['row']:
            return  # 동일한 결과를 2초마다 다시 저장하지 않는다.
        records[notice_id] = candidate
        st.session_state.favorite_snapshots = clean_snapshots(records, favorites())


def favorite_snapshots():
    return clean_snapshots(st.session_state.get('favorite_snapshots', {}), favorites())


def profile_changed():
    """공유 회사 입력 변경. 공고별 원문 확인 결과는 유지하고 이전 회사 판단만 무효화한다."""
    st.session_state['_favorite_profile_revision'] = st.session_state.get('_favorite_profile_revision', 0) + 1
    st.session_state.pop('_favorite_company_comparisons', None)

_JS = """
export default function (component) {
  const { data, setTriggerValue } = component
  const key = data.storage_key
  window.__frontlineStoreLoaded = window.__frontlineStoreLoaded || {}
  window.__frontlineStoreLastPayload = window.__frontlineStoreLastPayload || {}
  window.__frontlineStoreBaseline = window.__frontlineStoreBaseline || {}
  const writer = key + ':' + data.writer_key
  const parse = value => {
    try {
      const result = JSON.parse(value)
      return result && typeof result === 'object' && !Array.isArray(result) ? result : {}
    } catch (e) { return {} }
  }
  let stored = null
  try { stored = window.localStorage.getItem(key) } catch (e) { stored = null }
  if (!window.__frontlineStoreLoaded[key]) {
    window.__frontlineStoreLoaded[key] = true
    window.__frontlineStoreBaseline[key] = parse(stored)
    setTriggerValue("loaded", stored === null ? "" : stored)
    return
  }
  if (typeof data.save === "string" && window.__frontlineStoreLastPayload[writer] !== data.save) {
    // 실제 바뀐 항목만 합친다. 다른 탭에서 해제한 공고를 오래된 세션이 복구하지 않는다.
    try {
      const next = parse(data.save)
      const previous = writer in window.__frontlineStoreLastPayload
        ? parse(window.__frontlineStoreLastPayload[writer]) : window.__frontlineStoreBaseline[key] || {}
      const merged = parse(stored)
      const different = (a, b) => JSON.stringify(a) !== JSON.stringify(b)
      for (const field of ['profile', 'last', 'presets']) {
        if (different(next[field], previous[field])) merged[field] = next[field]
      }
      const ids = value => Array.isArray(value) ? value.filter(v => typeof v === 'string' && v.length <= 512) : []
      const before = ids(previous.favorites), after = ids(next.favorites)
      const removed = before.filter(id => !after.includes(id))
      const added = after.filter(id => !before.includes(id))
      merged.favorites = [...new Set([...ids(merged.favorites).filter(id => !removed.includes(id)), ...added])].slice(0, 10)
      const saved = Object.assign(Object.create(null), parse(JSON.stringify(merged.favorite_snapshots)))
      for (const [id, record] of Object.entries(next.favorite_snapshots || {})) {
        if (different(record, (previous.favorite_snapshots || {})[id])) saved[id] = record
      }
      merged.favorite_snapshots = Object.fromEntries(Object.entries(saved).filter(([id]) => merged.favorites.includes(id)))
      const output = JSON.stringify(merged)
      if (output !== stored) window.localStorage.setItem(key, output)
      window.__frontlineStoreLastPayload[writer] = data.save
    } catch (e) {}
  }
}
"""



def _component():
    # 같은 정의를 다시 등록해도 경고 없이 덮어쓴다. 실행마다 등록하면 등록부가 초기화되는 환경(AppTest)에서도 동작.
    return st.components.v2.component("frontline_browser_store", html="<div></div>", js=_JS)


def _valid(key: str, value, options: dict[str, list]) -> bool:
    if key in PROFILE_KEYS and key not in options:
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if key in options:
        allowed = options[key]
        if isinstance(value, list):
            return all(v in allowed for v in value)
        return value in allowed
    return isinstance(value, (str, bool, list, tuple))


def upgrade_profile(profile: dict) -> dict:
    """기존 단일 소재지 저장값과 새 복수 소재지 저장값을 모두 지원한다."""
    profile = dict(profile)
    if "pf_region" in profile:
        region = profile["pf_region"]
        profile["pf_region"] = [region] if isinstance(region, str) else (region or [])
    return profile


def _on_loaded(options: dict[str, list]):
    if st.session_state.get("prefs_loaded"):
        return
    st.session_state["prefs_loaded"] = True
    state = st.session_state.get(COMPONENT_KEY)
    raw = state.get("loaded") if isinstance(state, Mapping) else getattr(state, "loaded", None)
    if raw is not None and (not isinstance(raw, str) or len(raw) > 1_000_000):
        return
    try:
        prefs = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return
    if not isinstance(prefs, dict):
        return
    for key, value in {**upgrade_profile(prefs.get("profile", {})), **_upgrade(prefs.get("last", {}))}.items():
        if key in PROFILE_KEYS + FILTER_KEYS and _valid(key, value, options):
            st.session_state[key] = value
    presets = [p for p in prefs.get("presets", []) if isinstance(p, dict) and "name" in p and "filters" in p]
    st.session_state["saved_presets"] = presets[:MAX_PRESETS]
    st.session_state["favorite_notices"] = clean_favorites(prefs.get("favorites", []))
    st.session_state['favorite_snapshots'] = clean_snapshots(prefs.get('favorite_snapshots', {}), favorites())


def current_filters() -> dict:
    return {k: st.session_state[k] for k in FILTER_KEYS if k in st.session_state}


def presets() -> list[dict]:
    return st.session_state.setdefault("saved_presets", [])


def save_preset(name: str):
    """저장한 검색 = 공고 필터 + 내 회사 조건(소재지·면허)까지(사용자 지시 2026-09-28)."""
    name = name.strip()[:30]
    if not name:
        return
    items = [p for p in presets() if p["name"] != name]
    profile = {k: st.session_state.get(k) for k in PROFILE_KEYS}
    st.session_state.saved_presets = ([{"name": name, "filters": current_filters(), "profile": profile}]
                                      + items)[:MAX_PRESETS]


def apply_preset(name: str):
    """콜백에서 부른다(위젯이 그려지기 전에 값을 바꿔야 하므로). 회사 조건이 함께 저장돼 있으면 그것도 되살린다."""
    for p in presets():
        if p["name"] == name:
            for k, v in _upgrade(p["filters"]).items():
                if k in FILTER_KEYS:
                    st.session_state[k] = v
            for k, v in upgrade_profile(p.get("profile") or {}).items():
                if k in PROFILE_KEYS:
                    st.session_state[k] = v if v is not None or k != "pf_licenses" else []


def delete_preset(name: str):
    st.session_state.saved_presets = [p for p in presets() if p["name"] != name]


def mount(options: dict[str, list], *, key=COMPONENT_KEY):
    """앱 맨 끝에서 한 번 부른다. options: 선택형 위젯의 허용 값(잘못된 저장값은 버림)."""
    save = None
    if st.session_state.get("prefs_loaded"):
        save = json.dumps({
            "profile": {k: st.session_state[k] for k in PROFILE_KEYS if k in st.session_state},
            "last": current_filters(),
            "presets": presets(),
            "favorites": favorites(),
            "favorite_snapshots": favorite_snapshots(),
        }, ensure_ascii=False, default=str)
    _component()(key=key, data={"storage_key": STORAGE_KEY, "writer_key": key, "save": save},
           on_loaded_change=lambda: _on_loaded(options))
