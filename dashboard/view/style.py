"""대시보드 공통 레이아웃 보정.

색·글꼴·카드 모양은 ``.streamlit/config.toml``의 테마가 담당한다.
여기서는 사이드바 폭·본문 폭에 따른 열 재배치·관리자 버튼 배치를 보정한다.
"""

from __future__ import annotations

import streamlit as st

from view.assets import header_background_url

# 사이드바 필터 시작 위치. 사용자가 이 값만 바꿔 조정할 수 있다(단위: px).
SIDEBAR_FILTER_TOP_PX = 75

# 상단은 기존 테마색, 하단은 흰색을 12%만 덧입힌다. 위치·위젯 색에는 적용하지 않는다.
SIDEBAR_GRADIENT_BOTTOM_OPACITY = 0.12

# 공고 상세 제목 글자 크기만 조절한다(단위: rem). 카드 글자 크기와는 별개다.
NOTICE_DETAIL_TITLE_FONT_SIZE_REM = 2.2

# 제목·메뉴의 기존 좌측 정렬을 유지한다(단위: px).
APP_TITLE_OFFSET_X_PX = -21
APP_TITLE_OFFSET_Y_PX = -18
# 양수는 아래로, 음수는 위로. 배경 이미지 유무와 관계없이 각각 적용한다.
APP_SUBTITLE_OFFSET_Y_PX = -8
# 부제목의 미세한 들여쓰기(px). 제목·메뉴 위치와 독립적으로 적용한다.
APP_SUBTITLE_INDENT_PX = 5
APP_TITLE_FONT_SIZE_PX = 40
APP_SUBTITLE_FONT_SIZE_PX = 20
# CSV/PDF: 제목 행의 우측 상단 기준(px). TOP 양수는 아래, RIGHT 양수는 왼쪽.
# 좁은 본문에서는 별도 행으로 배치되므로 이 이동값을 적용하지 않는다.
APP_EXPORT_TOP_PX = -25
APP_EXPORT_RIGHT_PX = 5
# 분야별 분석의 진행 중 공고 버튼 위치(px). X 양수는 오른쪽, Y 양수는 아래.
# 위치만 이동하므로 큰 값은 주변 내용과 겹칠 수 있다.
ITEM_OPEN_NOTICE_OFFSET_X_PX = -5
ITEM_OPEN_NOTICE_OFFSET_Y_PX = -13
# 하단 문구/본문 이동(px). 양수는 아래, 음수는 위. 상단 문구는 고정한다.
# -8px부터 확인한다. 큰 음수는 상단 문구 및 고정된 버튼과 카드를 겹치게 할 수 있다.
# 넓은 화면은 버튼 기준을 상단에 분리하고, 좁은 화면은 자연스러운 줄바꿈을 우선한다.
ITEM_CONTEXT_TEXT_EXTRA_GAP_PX = -10
# 공통 상단 영역 시작점. 기존 3.75rem의 절반이며, 도구 모음 높이도 함께 맞춘다.
APP_HEADER_TOP_REM = 1.875

# 사용자 제공 이미지의 장식 레이어만 흐리게 한다. 제목·메뉴의 불투명도는 유지한다.
APP_HEADER_ART_OPACITY = 0.62

# 후보3 기준의 공통 카드 스타일. 사용자 글자 크기·필터 시작 위치는 보존한다.
SIDEBAR_WIDTH_PX = 345.6  # 기존288px의1.2배. 본문 폭/중앙 이동도 이 값을 공유한다.
# 사이드바와 본문의 전환 시간·가속/감속을 한 값으로 관리한다.
SIDEBAR_MOTION = ".3s cubic-bezier(.22, 1, .36, 1)"


def apply(_page_title: str = ""):
    """화면과 무관하게 같은 탐색 구조를 유지한다.

    화면별 색을 바꾸지 않는다. 공고·품목·시장 개요는 회청색 중성 기반을 공유하고,
    강조색은 KPI 의미와 차트 계열을 구분하는 데 사용한다.
    """
    side = '[data-testid="stSidebar"]'
    item_context_extra_gap = ITEM_CONTEXT_TEXT_EXTRA_GAP_PX
    mode = "dark" if st.context.theme.type == "dark" else "light"
    sidebar_accent = (st.get_option(f"theme.{mode}.sidebar.primaryColor")
                      or st.get_option("theme.sidebar.primaryColor") or "#FFB340")
    sidebar_text = (st.get_option(f"theme.{mode}.sidebar.textColor")
                    or st.get_option("theme.sidebar.textColor") or "#F7F8FA")
    # Streamlit의 color-scheme은 브라우저 테마 전환 즉시 바뀐다. Python 재실행을 기다리지 않는다.
    surface = "light-dark(#FFFFFF, #292E36)"
    border = "light-dark(#D5E0EE, #46566C)"
    caption = "light-dark(#64748B, #B7C4D7)"
    header_background = f"light-dark({st.get_option('theme.light.backgroundColor') or '#F3F7FC'}, {st.get_option('theme.dark.backgroundColor') or '#20242B'})"
    shadow = "0 6px 20px light-dark(rgba(39,70,111,.045), rgba(0,0,0,.12))"
    header_art = header_background_url()
    header_art_css = f"""
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{
  margin-inline: 0 !important; width: 100% !important; padding-inline: .4rem !important;
}}
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header)::before {{
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background-image: url("{header_art}"); background-size: cover; background-position: right center;
  opacity: {APP_HEADER_ART_OPACITY};
  mask-image: linear-gradient(90deg, transparent 0%, rgba(0,0,0,.25) 32%, #000 65%), linear-gradient(180deg, transparent 0%, #000 12%);
  mask-composite: intersect;
}}
.st-key-app_sticky_header {{ position: relative; min-height: 190px; padding-top: 38px; gap: 0; justify-content: space-between; border-bottom: 1px solid {border}; }}
.st-key-app_sticky_header .st-key-app_title_link {{ transform: translateY({APP_TITLE_OFFSET_Y_PX}px); }}
.st-key-app_sticky_header .st-key-page_menu {{ transform: none; }}
@media (max-width: 768px) {{
  [data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{
    margin-inline: 0 !important; width: 100% !important; padding-inline: 0 !important;
  }}
  .st-key-app_sticky_header {{ min-height: 170px; padding-top: 14px; gap: .5rem; }}
}}
""" if header_art else ""
    st.html(f"""<style>
/* 사이드바 배경만 아래로 갈수록 미세하게 밝아진다. 두 모드에서 같은 효과를 사용한다. */
{side} {{
  background-image: linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, {SIDEBAR_GRADIENT_BOTTOM_OPACITY}) 100%);
  transition: transform {SIDEBAR_MOTION}, min-width {SIDEBAR_MOTION}, max-width {SIDEBAR_MOTION} !important;
}}
/* 넓은 화면에서 필터가 내용을 압도하지 않도록 폭을 제한한다. */
{side}[aria-expanded="true"] {{
  width: {SIDEBAR_WIDTH_PX}px !important; min-width: {SIDEBAR_WIDTH_PX}px !important; max-width: {SIDEBAR_WIDTH_PX}px !important; flex: 0 0 {SIDEBAR_WIDTH_PX}px !important;
}}
{side} div[style*="cursor: col-resize"] {{ display: none !important; pointer-events: none !important; }}
/* 필터 본문만 스크롤하고 하단 액션은 같은 화면 안에 남긴다. */
{side} [data-testid="stSidebarContent"] {{
  display: flex; flex-direction: column; height: 100dvh; overflow: hidden;
}}
/* 닫기는 sidebar 오른쪽 끝, 열기는 화면 왼쪽. 높이·크기와 native 동작은 같다. */
{side} [data-testid="stSidebarHeader"] {{
  display: flex !important; position: absolute; top: 8px; right: .35rem; left: auto;
  align-items: flex-start; width: 32px; height: 32px !important; padding: 0; margin: 0; z-index: 2;
}}
{side} [data-testid="stLogoSpacer"] {{ display: none; }}
{side} [data-testid="stSidebarCollapseButton"] {{ visibility: visible !important; opacity: 1 !important; margin: 0; }}
{side} [data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] {{ width: 32px !important; height: 32px !important; padding: 0 !important; margin: 0; }}
[data-testid="stExpandSidebarButton"] {{ position: fixed; top: 8px; bottom: auto; }}
{side} [data-testid="stSidebarCollapseButton"] button {{ position: absolute; top: 0; left: 0; right: auto; }}
[data-testid="stExpandSidebarButton"] {{ left: 12px; right: auto; }}
{side} [data-testid="stSidebarUserContent"] {{
  position: relative;
  padding-top: {SIDEBAR_FILTER_TOP_PX}px !important; padding-bottom: 1rem !important;
  margin-block: 0; flex: 1; min-height: 0; overflow: hidden;
}}
{side} [data-testid="stSidebarUserContent"] > div {{
  height: 100%; min-height: 0; display: flex; flex-direction: column;
}}
{side} [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > .st-key-sidebar_filter_body) {{
  flex: 1; min-height: 0; height: 100%; gap: .5rem;
}}
{side} [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_filter_body) {{
  flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column;
}}
/* 조건의 펼침 여부와 무관하게 같은 상단 위치에서 시작한다. */
{side} .st-key-sidebar_filter_body {{ margin-block: 0; flex: 0 0 auto; height: auto; }}
{side} [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_actions) {{ flex: 0 0 auto; }}
{side} [data-testid="stExpander"] summary {{ min-height: 2.4rem !important; }}
/* 상세·회사 조건: 제목·아이콘은 흰색, 실제 열림 상태의 ▲/▼만 주황색. */
{side} :is([class*="st-key-"][class*="_detail_box"], .st-key-pf_box) summary {{
  color: {sidebar_text}; list-style: none;
}}
{side} :is([class*="st-key-"][class*="_detail_box"], .st-key-pf_box) summary::-webkit-details-marker {{ display: none; }}
/* 기본 hover 화살표만 숨긴다. 제목 안의 tune 아이콘은 그대로 표시한다. */
{side} :is([class*="st-key-"][class*="_detail_box"], .st-key-pf_box) summary > span > span {{ display: none; }}
{side} :is([class*="st-key-"][class*="_detail_box"], .st-key-pf_box) summary::after {{
  content: "▼"; color: {sidebar_accent}; margin-left: auto; flex: 0 0 auto;
  background: none; font-size: .9rem;
}}
{side} :is([class*="st-key-"][class*="_detail_box"], .st-key-pf_box) details[open] > summary::after {{ content: "▲"; }}
/* 동작 보정용 컴포넌트는 화면·필터 시작 위치에 공간을 차지하지 않는다. */
.st-key-sidebar_dropdown_guard {{ display: none; }}
.st-key-plotly_donut_guard {{ display: none; }}
.st-key-plotly_bar_gradient_guard {{ display: none; }}
.st-key-table_menu_guard {{ display: none; }}
.st-key-body_scroll_guard {{ display: none; }}
{side} [data-testid="stExpanderDetails"] {{ padding-top: .35rem !important; padding-bottom: .5rem !important; }}
/* 입력·선택칸의 색도 사이드바의 기본 테마를 따른다. */
/* 고객용 화면에서 관리자 입구는 본문 맨 끝에만 둔다. */
/* native 토글 높이 변화에 따른 브라우저 자동 스크롤 보정을 끈다. */
[data-testid="stMain"] {{ overflow-anchor: none; }}
/* 고정 높이/내부 스크롤 없이 본문은 최소 한 화면, 긴 내용은 자연스럽게 늘어난다. */
.st-key-dashboard_page_content {{
  min-height: max(100vh, var(--frontline-body-scroll-floor, 0px));
  min-height: max(100dvh, var(--frontline-body-scroll-floor, 0px));
}}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :has(> .st-key-admin_foot),
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > .st-key-admin_foot {{ order: 9999; }}
.st-key-admin_foot {{ align-items: flex-end; margin-top: 2.5rem; opacity: .45; }}
.st-key-admin_foot button {{ min-height: 0; padding: 0 .2rem; }}
.st-key-admin_foot button p {{ font-size: .68rem; }}
/* 자체 표·차트 도구 메뉴는 페이지 내보내기와 상세보기로 대체한다. */
[data-testid="stElementToolbar"] {{ display: none !important; }}
/* canvas 본문·헤더 동작은 유지하고, 컬럼 설정 팝업만 접근 차단한다. */
[data-testid="stDataFrameColumnMenu"] {{ display: none !important; pointer-events: none !important; }}
.st-key-table_scroll_hint {{ display: none; }}
@media (max-width: 768px) {{
  {side}[aria-expanded="true"] {{ width: 90vw !important; min-width: 90vw !important; max-width: 90vw !important; }}
}}
/* 사이드바·브라우저 확대에 따라 달라지는 실제 본문 폭으로 열을 재배치한다. */
[data-testid="stMainBlockContainer"] {{
  padding-top: {APP_HEADER_TOP_REM}rem;
  container-type: inline-size;
  container-name: dashboard_main;
}}
/* 데스크톱에서는 같은 스크롤 영역·본문 폭을 유지하고 위치만 이동한다.
   접기 중 부모 폭 변화로 차트가 재배치되지 않게 sidebar를 문서 흐름에서 분리한다. */
@media (min-width: 769px) {{
  {side} {{ position: absolute !important; top: 0; left: 0; }}
  [data-testid="stMain"] {{ width: 100% !important; scrollbar-gutter: stable; }}
  [data-testid="stMainBlockContainer"] {{
    max-width: calc(100% - {SIDEBAR_WIDTH_PX}px) !important; margin-inline: auto;
    transform: translateX({SIDEBAR_WIDTH_PX / 2:g}px);
    transition: transform {SIDEBAR_MOTION};
  }}
  body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMainBlockContainer"] {{
    transform: translateX(0);
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  [data-testid="stMainBlockContainer"], {side} {{ transition: none !important; }}
}}
/* native 도구 모음 아래부터 제목·메뉴·내보내기를 함께 유지한다. */
[data-testid="stHeader"], [data-testid="stToolbar"] {{ height: {APP_HEADER_TOP_REM}rem; min-height: 0; }}
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{
  position: sticky; top: {APP_HEADER_TOP_REM}rem; z-index: 100;
  background: {header_background};
  padding-inline: 21px; margin-inline: -21px; width: calc(100% + 42px); max-width: none;
}}
{header_art_css}
/* 내보내기의 기준점은 제목 행이다. 제목 글자 이동값·배경 유무에 종속되지 않는다. */
.st-key-page_heading_app {{ position: relative; padding-right: 156px; }}
.st-key-page_heading_app > [data-testid="stLayoutWrapper"]:has(> .st-key-exports_app) {{
  position: absolute; right: {APP_EXPORT_RIGHT_PX}px; top: {APP_EXPORT_TOP_PX}px; z-index: 2;
}}
.st-key-app_title_link {{ transform: translate({APP_TITLE_OFFSET_X_PX}px, {APP_TITLE_OFFSET_Y_PX}px); }}
/* 공통 제목·부제는 같은 글꼴을 사용하고 굵기만 한 단계 구분한다. */
.st-key-app_title_link a, .st-key-app_subtitle p {{ font-family: var(--st-heading-font); }}
.st-key-app_title_link a {{
  color: inherit !important; background: transparent !important; border: 0; padding: 0;
  font-size: {APP_TITLE_FONT_SIZE_PX}px; font-weight: 700; line-height: 1.2;
  text-decoration: none; border-radius: 0; white-space: normal;
}}
.st-key-app_title_link a [data-testid="stMarkdownContainer"],
.st-key-app_title_link a p {{ font: inherit !important; margin: 0; white-space: normal; word-break: keep-all; }}
.st-key-app_title_link a:focus-visible {{ outline: 2px solid currentColor; outline-offset: 3px; }}
/* 높이를 고정하지 않아 좁은 화면에서 제목·메뉴가 줄바꿈해도 본문 공간을 확보한다. */
.st-key-app_title_block {{ gap: 0; }}
.st-key-app_title_block h1 {{ padding-bottom: 0; }}
.st-key-app_title_block [data-testid="stMarkdownContainer"] {{ margin-block: 0 !important; }}
.st-key-app_title_block, .st-key-app_subtitle {{ height: auto !important; }}
.st-key-app_title_block > [data-testid="stElementContainer"],
.st-key-app_title_block > [data-testid="stLayoutWrapper"] {{ flex: 0 0 auto; min-height: min-content; }}
.st-key-app_subtitle {{ padding-top: 0; transform: translateY({APP_SUBTITLE_OFFSET_Y_PX}px); }}
.st-key-app_subtitle p {{ font-size: {APP_SUBTITLE_FONT_SIZE_PX}px; line-height: 1.4; font-weight: 400; color: light-dark(#48617F, #B7C4D7) !important; margin-block: 0; padding-inline-start: {APP_SUBTITLE_INDENT_PX}px; }}
/* 상단 탐색 메뉴의 시작점도 공통 대제목의 왼쪽 이동값에 맞춘다. */
.st-key-page_menu {{ transform: translateX({APP_TITLE_OFFSET_X_PX}px); }}
/* 좁은 화면은 본문 왼쪽 여백이 17px이므로 제목 이동을 최대 8px로 제한한다. */
@media (max-width: 768px) {{
  [data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{ padding-inline: 8px; margin-inline: -8px; width: calc(100% + 16px); }}
  .st-key-app_title_link a {{ font-size: clamp(1.3rem, 5.2vw, 2rem); }}
  .st-key-app_subtitle p {{ font-size: clamp(.9rem, 3.6vw, 1.2rem); }}
  .st-key-card_quality_metadata [data-testid="stMetricValue"] {{ font-size: 1.15rem; line-height: 1.4; overflow-wrap: anywhere; }}
  .st-key-page_menu {{ transform: translateX(max(-8px, {APP_TITLE_OFFSET_X_PX}px)); }}
  .st-key-app_title_link {{ transform: translate(max(-8px, {APP_TITLE_OFFSET_X_PX}px), {APP_TITLE_OFFSET_Y_PX}px); }}
}}
/* 사용자 승인: 버튼 박스 대신 웹 링크 메뉴, 활성 밑줄·hover·키보드 포커스. */
.st-key-page_menu a {{
  border-radius: 0;
  padding: .55rem .75rem; border-bottom: 3px solid transparent;
  color: inherit !important;
}}
.st-key-page_menu_public a {{ background: transparent !important; }}
.st-key-page_menu [class*="st-key-nav_active_"] a {{ border-bottom-color: currentColor; }}
.st-key-page_menu a:hover {{ border-bottom-color: currentColor; }}
.st-key-page_menu a:focus-visible {{ outline: 2px solid currentColor; outline-offset: 2px; }}
/* 상세 값 위의 제목 여백을 줄여 제목과 값을 붙인다. */
.st-key-notice_detail_title h2 {{
  font-size: {NOTICE_DETAIL_TITLE_FONT_SIZE_REM}rem;
  padding-block: 0;
  margin-block: 0;
  line-height: 1.3;
  word-break: keep-all;
  overflow-wrap: break-word;
  text-wrap: balance;
}}
/* 긴 한국어 설명은 어절 단위로 줄바꿈한다. 날짜·번호가 길 때만 강제 줄바꿈을 허용한다. */
[data-testid="stTable"] {{ overflow-x: auto; }}
[data-testid="stTable"] table {{ min-width: 32rem; }}
[data-testid="stTable"] th, [data-testid="stTable"] td {{
  min-width: 5.5rem;
  word-break: keep-all;
  overflow-wrap: break-word;
}}
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] p,
[class*="st-key-info_"] h3, [class*="st-key-info_"] h4,
[class*="st-key-chart_header_"] h3 {{
  word-break: keep-all;
  overflow-wrap: break-word;
  text-wrap: pretty;
}}
[class*="st-key-info_"] h3, [class*="st-key-info_"] h4 {{ padding-block: 0; margin-block: 0; }}
[class*="st-key-info_"] [data-testid="stMarkdownContainer"],
[class*="st-key-info_"] [data-testid="stCaptionContainer"] {{ margin-block: 0 !important; }}
[class*="st-key-info_"] [data-testid="stCaptionContainer"] p {{ margin-block: 0; }}
[class*="st-key-info_"] h4 {{ font-size: 1.15rem; }}
[class*="st-key-info_"] h3 {{ font-size: 1.6rem; line-height: 1.35; overflow-wrap: break-word; }}
[class*="st-key-info_"] > [data-testid="stElementContainer"] {{ flex: 0 0 auto; min-height: min-content; }}
/* 사용자 변경 승인: 분류명·기간 설명도 검색 조건·지표 카드의 왼쪽 축에 맞춘다. */
.st-key-item_context {{ margin-left: 0; width: 100%; }}
/* 사용자 승인: 진입 요약만 이미지처럼 2단·가로 구분선. 설명은 i 도움말에 보존한다. */
.st-key-entry_summary {{ background: {surface}; border-color: {border} !important; border-radius: 12px; padding: 22px 20px !important; box-shadow: {shadow}; height: auto; flex: 0 0 auto; }}
.st-key-entry_summary > div,
.st-key-entry_summary [data-testid="stLayoutWrapper"],
.st-key-entry_summary [data-testid="stElementContainer"],
.st-key-entry_summary [data-testid="stVerticalBlock"] {{ height: auto !important; min-height: min-content; flex-shrink: 0; }}
.st-key-entry_summary > div {{ flex: 0 0 auto; }}
.st-key-entry_summary [data-testid="stMarkdownContainer"] {{ margin-block: 0 !important; }}
.st-key-entry_summary h3 {{ font-size: 1.25rem; font-weight: 700; padding-block: 0; margin: 0; }}
.st-key-entry_summary_grid {{ border-top: 1px solid {border}; margin-top: 8px; }}
.st-key-entry_summary_half_1 {{ border-left: 1px solid {border}; }}
.st-key-entry_summary [class*="st-key-entry_row_"] {{ min-height: 58px; margin-block: 0 !important; padding: 14px 16px; border-bottom: 1px solid {border}; flex: 0 0 auto; }}
.st-key-entry_summary [class*="st-key-entry_label_"], .st-key-entry_summary [class*="st-key-entry_value_"] {{ min-width: 0; height: auto; }}
.st-key-entry_summary [class*="st-key-entry_label_"] p {{ font-weight: 500; color: {caption}; }}
.st-key-entry_summary [class*="st-key-entry_value_"] strong {{ font-weight: 600; }}
.st-key-entry_summary [class*="st-key-entry_value_"] [data-testid="stMarkdownContainer"] span {{ font-size: 1rem; font-weight: 600; }}
.st-key-entry_summary [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_label_"]) {{ flex: 0 0 190px; width: 190px; }}
.st-key-entry_summary [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_value_"]) {{ flex: 1 1 0; min-width: 0; }}
.st-key-entry_summary [data-testid="stMarkdownContainer"] p {{ margin: 0; line-height: 1.5; word-break: keep-all; overflow-wrap: anywhere; }}
.st-key-entry_summary_half_0 > div:last-child [class*="st-key-entry_row_"],
.st-key-entry_summary_half_1 > div:last-child [class*="st-key-entry_row_"] {{ border-bottom: 0; }}
.st-key-entry_summary_agencies [class*="st-key-entry_row_"] {{ border-bottom: 0; min-height: 51px; padding-bottom: 7px; }}
.st-key-entry_summary_agencies {{ border-top: 1px solid {border}; }}
.st-key-entry_summary_agencies [data-testid="stMarkdownContainer"] p {{ font-size: .92rem; }}
@container dashboard_main (max-width: 760px) {{
  .st-key-entry_summary_half_1 {{ border-left: 0; padding-left: 0; }}
  .st-key-entry_summary {{ padding: 20px 14px !important; }}
  .st-key-entry_summary [class*="st-key-entry_row_"] {{ padding-inline: 8px; }}
  .st-key-entry_summary [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_label_"]) {{ flex-basis: 145px; width: 145px; }}
  .st-key-entry_summary_half_1 {{ border-top: 1px solid {border}; }}
  .st-key-entry_summary_agencies [class*="st-key-entry_row_"] {{ flex-wrap: wrap !important; }}
  .st-key-entry_summary_agencies [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_value_"]) {{ flex-basis: 100%; }}
}}
/* 후보3: 데이터는 유지하고 공통 카드·메뉴·여백만 정돈한다. */
[data-testid="stMainBlockContainer"] {{ padding-inline: 3.1rem; }}
.st-key-page_menu {{ border-bottom: 1px solid {border}; padding-bottom: 0; margin-bottom: 0; }}
.st-key-page_menu a p {{ font-size: .95rem; }}
/* 사용자 탐색은 왼쪽, 관리자·데이터 기준 링크는 오른쪽 끝에 한 묶음으로 유지한다. */
.st-key-page_menu > div:has(> .st-key-page_menu_management) {{ margin-left: auto; }}
/* 관리자 전용 두 메뉴만 배경 이미지와 분리한다. 활성 밑줄/포커스 표시는 유지한다. */
.st-key-page_menu .st-key-page_menu_management a {{
  background: light-dark(rgba(243, 247, 252, .90), rgba(32, 36, 43, .90)) !important;
  color: light-dark(#0D1930, #F7F8FA) !important; font-weight: 500;
  border-radius: 4px;
}}
.st-key-page_menu_management a > span {{ color: inherit !important; }}
/* 데이터 기준의 정적 연결률 표는 긴 기준 문구를 자르지 않고 줄바꿈한다. */
.st-key-card_quality_links table {{ width: 100%; }}
.st-key-card_quality_links :is(th, td) {{ white-space: normal; word-break: keep-all; overflow-wrap: anywhere; }}
.st-key-card_quality_checks table {{ width: 100%; }}
/* 조달 유형만 반투명 선택 채움으로 통일. 단일·복수 선택의 접근성 속성 모두 처리한다. */
{side} :is(.st-key-nt_types, .st-key-it_type, .st-key-ov_types) button[data-variant="pills"]:is([aria-checked="true"], [aria-pressed="true"]) {{
  background: color-mix(in srgb, {sidebar_accent} 15%, transparent); color: {sidebar_accent}; border-color: {sidebar_accent}; font-weight: 600;
}}
{side} :is(.st-key-nt_types, .st-key-it_type, .st-key-ov_types) button[data-variant="pills"]:is([aria-checked="true"], [aria-pressed="true"]) p {{ color: {sidebar_accent}; }}
[data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] {{ opacity: 1; color: {caption}; }}
.st-key-page_content_heading h2 {{ padding-block: 0; margin-block: 0; }}
.st-key-page_content_heading {{ gap: .3rem; }}
.st-key-page_content_heading [data-testid="stMarkdownContainer"],
[class*="st-key-chart_header_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}
.st-key-page_content_heading [data-testid="stCaptionContainer"],
[class*="st-key-chart_header_"] [data-testid="stCaptionContainer"] {{ margin-block: 0; }}
.st-key-page_content_heading [data-testid="stCaptionContainer"] p,
[class*="st-key-chart_header_"] [data-testid="stCaptionContainer"] p {{ margin-block: 0; }}
.st-key-page_menu a {{ padding: .55rem .65rem .7rem; }}
.st-key-page_menu [class*="st-key-nav_active_"] a {{ border-bottom-color: #005BFF; }}
.st-key-page_menu a:hover {{ border-bottom-color: #005BFF; }}
.st-key-exports_app button {{ min-height: 30px; padding: .1rem .35rem; }}
.st-key-exports_app button p {{ font-size: .85rem; }}
[class*="st-key-kpi_"]:not([class*="st-key-kpi_heading_"]):not([class*="st-key-kpi_symbol_"]) {{
  background: {surface}; border-color: {border} !important;
  border-radius: 12px; box-shadow: {shadow}; padding: 16px 18px !important;
  min-height: 170px; gap: .55rem;
}}
[class*="st-key-card_"] {{
  background: {surface}; border-color: {border} !important;
  border-radius: 12px; box-shadow: {shadow}; padding: 20px !important;
}}
[class*="st-key-kpi_heading_"] {{ min-height: 48px; flex-wrap: nowrap !important; gap: .7rem; }}
[class*="st-key-kpi_heading_"] [data-testid="stMarkdownContainer"] p {{ font-size: 1.045rem; font-weight: 600; line-height: 1.35; }}
[class*="st-key-kpi_heading_"] [data-testid="stLayoutWrapper"] {{ min-width: 0; }}
.dashboard-kpi-icon {{ width: 38px; height: 38px; border-radius: 10px; overflow: hidden; flex-shrink: 0; }}
.dashboard-kpi-icon img {{ width: 38px; height: 38px; display: block; transform: scale(1.6); }}
[class*="st-key-kpi_symbol_"] {{
  width: 48px; height: 48px; min-height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, {surface} 92%, #005BFF);
}}
[class*="st-key-kpi_symbol_"] [data-testid="stMarkdownContainer"] p {{ margin: 0; font-size: 24px; line-height: 1; }}
[class*="st-key-kpi_"] [data-testid="stMetricValue"] {{ font-size: 2.15rem; font-weight: 700; line-height: 1.2; }}
[class*="st-key-kpi_"] [data-testid="stMetricDelta"] {{ font-size: .9rem; border-radius: 999px; }}
[class*="st-key-kpi_"][class*="_it_"] [data-testid="stMetricDelta"] {{ margin-top: 4px; }}
/* 사용자 승인: 분야별 분석의 네 지표 카드 안쪽 여백만 기존의 1.5배. */
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]:is(.st-key-kpi_blue_it_0, .st-key-kpi_orange_it_1, .st-key-kpi_violet_it_2, .st-key-kpi_green_it_3) {{ padding: 24px 27px !important; }}
[class*="st-key-chart_header_"] h3 {{ font-size: 1.2rem; line-height: 1.4; padding-block: 0; margin-block: 0; }}
[class*="st-key-card_"] [data-testid="stCaptionContainer"] p {{ color: {caption}; font-size: .9rem; line-height: 1.5; }}
[data-testid="stMainBlockContainer"] [data-testid="stTabs"] [role="tablist"] {{ gap: 1.5rem; border-bottom: 1px solid {border}; }}
[data-testid="stMainBlockContainer"] [data-testid="stTabs"] [role="tab"] {{ padding-inline: .35rem; font-weight: 600; }}
.st-key-item_context_action {{ transform: translateX({ITEM_OPEN_NOTICE_OFFSET_X_PX}px) translateY({ITEM_OPEN_NOTICE_OFFSET_Y_PX}px); }}
.st-key-it_go_notices button {{ min-height: 43.2px; border-radius: 10px; padding: .5rem 1.75rem; box-shadow: 0 6px 16px rgba(0,91,255,.12); background-image: linear-gradient(135deg, rgba(255,255,255,.2), rgba(255,255,255,0) 70%); }}
@supports (width: calc-size(max-content, size * 1.1)) {{
  .st-key-it_go_notices button {{ width: calc-size(max-content, size * 1.1); max-width: 100%; padding-inline: 1rem; }}
}}
.st-key-it_go_notices button:disabled {{ background-image: none; }}
.st-key-it_go_notices button::after {{ content: "→"; font-size: 1.2rem; margin-left: .35rem; }}
.st-key-item_context h3 {{ font-size: 1.25rem; line-height: 1.5; padding-block: .2rem; }}
.st-key-item_context h3 span {{ border-radius: 8px; }}
.st-key-item_category_heading {{
  background: light-dark(#E1EBF9, #354155); border-radius: 8px;
  padding: .4rem .85rem; gap: .65rem; max-width: 100%; align-items: center; overflow: visible;
}}
.st-key-item_category_heading [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; min-width: 0; }}
.st-key-item_category_heading > [data-testid="stLayoutWrapper"]:has(h3) {{ flex: 1 1 auto; min-width: 0; }}
.st-key-item_category_heading h3 {{ font-size: 1.35rem; font-weight: 600; line-height: 1.4; padding-block: 0; margin-block: 0; word-break: keep-all; overflow-wrap: anywhere; }}
.st-key-item_procurement_icon {{ width: 36px !important; flex-shrink: 0; border-radius: 6px; background: light-dark(#E1EBF9, #354155); }}
.st-key-item_procurement_icon img {{ width: 36px; height: 36px; }}
.st-key-item_procurement_icon .procurement-type-hover {{ position: relative; display: block; width: 36px; height: 36px; cursor: help; border-radius: 4px; }}
.st-key-item_procurement_icon .procurement-type-hover:focus-visible {{ outline: 2px solid var(--st-primary-color); outline-offset: 2px; }}
.st-key-item_procurement_icon .procurement-type-tooltip {{ display: none; position: absolute; bottom: calc(100% + 6px); right: 0; z-index: 1000; padding: 4px 8px; border: 1px solid var(--st-border-color); border-radius: 6px; background: var(--st-secondary-background-color); color: var(--st-text-color); font: 14px/1.4 var(--st-font); white-space: nowrap; box-shadow: 0 3px 10px #0002; pointer-events: none; }}
.st-key-item_procurement_icon .procurement-type-hover:is(:hover, :focus) .procurement-type-tooltip {{ display: block; }}
.st-key-item_context {{ margin-top: -12px; margin-bottom: -.5rem; }}
.st-key-item_context_row {{ margin-top: 4px; }}
/* 상단 문구는 고정하고 하단 문구/아래 본문을 실제 간격만큼 이동한다.
   하단 문구가 없는 빈 개찰 결과에는 적용하지 않는다. */
.st-key-item_context_text > [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {{
  margin-top: {item_context_extra_gap}px !important;
}}
/* 넓은 본문에서는 버튼 높이를 행 계산에서 분리하고 상단 기준으로 고정한다.
   기존 버튼 위치의 상단 간격(기본 글자17px에서 약23.15px)을 유지한다.
   좁은 화면은 버튼이 별도 행으로 내려가므로 기존 자연스러운 배치를 보존한다. */
@container dashboard_main (min-width: 601px) {{
  .st-key-item_context_row:has(.st-key-item_context_text > [data-testid="stElementContainer"] [data-testid="stCaptionContainer"]) > [data-testid="stLayoutWrapper"]:has(> .st-key-item_context_action) {{
    align-self: flex-start; height: 0 !important; min-height: 0 !important;
    margin-top: 1.362rem; overflow: visible;
  }}
}}
/* 검색 조건만 보조 정보로 부드럽게 표시. opacity/filter는 자식 글씨까지 흐려져 사용하지 않는다. */
.st-key-notice_filter_summary, [class*="st-key-search_filter_summary_"] {{
  background: light-dark(rgba(235,243,255,.55), rgba(41,55,77,.55));
  border-color: light-dark(#C7DCFF, #465D7B) !important; border-radius: 12px;
  box-shadow: 0 3px 12px light-dark(rgba(39,70,111,.025), rgba(0,0,0,.06)); padding: 16px 18px !important;
}}
/* 공고1 참고 시안: 공고 페이지에서만 조건·목록·KPI를 정돈한다. */
.st-key-notice_filter_summary {{
  background: light-dark(rgba(235,243,255,.55), rgba(41,55,77,.55));
  border-color: light-dark(#C7DCFF, #465D7B) !important;
}}
.st-key-notice_summary_heading, [class*="st-key-filter_summary_heading_"] {{ gap: .85rem; min-height: 60px; }}
.st-key-notice_summary_icon, [class*="st-key-filter_summary_icon_"] {{
  width: 48px; height: 48px; min-height: 48px; border-radius: 12px; flex-shrink: 0;
  background: light-dark(#DAE8FF, #354B70); display: flex; align-items: center; justify-content: center;
}}
.st-key-notice_summary_icon p, [class*="st-key-filter_summary_icon_"] p {{
  margin: 0; line-height: 1; display: flex; align-items: center; justify-content: center;
}}
.st-key-notice_summary_icon [role="img"], [class*="st-key-filter_summary_icon_"] [role="img"] {{ font-size: 28px; line-height: 1; }}
.st-key-notice_summary_text, [class*="st-key-filter_summary_text_"] {{ min-width: 0; gap: .3rem; height: auto !important; }}
.st-key-notice_summary_text > [data-testid="stElementContainer"],
[class*="st-key-filter_summary_text_"] > [data-testid="stElementContainer"] {{ flex: 0 0 auto; min-height: min-content; }}
.st-key-notice_summary_text p, [class*="st-key-filter_summary_text_"] p {{ margin-block: 0; }}
.st-key-notice_filter_summary [data-testid="stMarkdownContainer"],
.st-key-notice_filter_summary [data-testid="stCaptionContainer"],
[class*="st-key-search_filter_summary_"] [data-testid="stMarkdownContainer"],
[class*="st-key-search_filter_summary_"] [data-testid="stCaptionContainer"],
.st-key-notice_results_panel [data-testid="stMarkdownContainer"],
.st-key-notice_results_panel [data-testid="stCaptionContainer"] {{ margin-block: 0 !important; }}
[data-testid="stVerticalBlock"][class*="st-key-kpi_"]:is([class*="_nt_"], [class*="_ov_"]):not([class*="st-key-kpi_heading_"]) {{
  min-height: 146px !important;
}}
/* 시장 규모의 첫 두 그래프만 90% 폭. 카드 경계·제목 위치는 유지한다. */
:is(.st-key-ov_size_plot_left, .st-key-ov_size_plot_right) {{
  width: 90%; max-width: 90%; margin-inline: auto;
}}
.st-key-notice_results_panel {{
  background: {surface}; border-color: {border} !important; border-radius: 12px;
  box-shadow: {shadow}; padding: 18px !important;
}}
.st-key-notice_results_heading p {{ margin: 0; font-size: 1.08rem; }}
.st-key-notice_results_panel [data-testid="stCaptionContainer"] p {{ font-size: .82rem; margin-block: 0; }}
/* 빈 결과 안내만 세로 중앙 정렬. Markdown의 마지막 문단 여백을 제거한다. */
.st-key-notice_empty_state [data-testid="stAlertContainer"] {{ min-height: 76px; display: flex; align-items: center; }}
.st-key-notice_empty_state [data-testid="stAlertContentInfo"] {{ width: 100%; }}
.st-key-notice_empty_state [data-testid="stAlertContentInfo"] > div {{ align-items: center; }}
.st-key-notice_empty_state [data-testid="stAlertContentInfo"] > div > div:first-child {{ display: flex; align-items: center; height: auto; top: 0; }}
.st-key-notice_empty_state [data-testid="stMarkdownContainer"] p:last-child {{ margin-bottom: 0; }}
@container dashboard_main (max-width: 600px) {{
  .st-key-item_context_row {{ margin-top: 13px; }}
  .st-key-notice_summary_heading > [data-testid="stLayoutWrapper"]:has(> .st-key-notice_summary_text) {{ flex-basis: calc(100% - 65px); }}
  [class*="st-key-filter_summary_heading_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-filter_summary_text_"]) {{ flex-basis: calc(100% - 65px); }}
  .st-key-notice_results_panel {{ padding: 12px !important; }}
}}
@media (max-width: 768px) {{
  [data-testid="stMainBlockContainer"] {{ padding-inline: 1rem; }}
  [class*="st-key-card_"] {{ padding: 16px !important; }}
}}
/* Markdown 제목에도 생성되는 본문 바로가기 아이콘은 사용하지 않는다. */
[data-testid="stHeaderActionElements"] {{ display: none !important; }}
/* 제목 아래 고정 예약 공간을 없앤다. 카드 외곽 높이는 native stretch로 유지한다. */
[class*="st-key-chart_header_"] {{ min-height: 0; }}
@container dashboard_main (max-width: 760px) {{
  [class*="st-key-page_heading_"] {{ flex-wrap: wrap; gap: .25rem; }}
  .st-key-page_heading_app {{ padding-right: 0; }}
  /* 좁은 본문에서는 내보내기를 별도 행으로 예약해 제목과도 겹치지 않는다. */
  .st-key-page_heading_app > [data-testid="stLayoutWrapper"]:has(> .st-key-exports_app) {{ position: static; }}
  [class*="st-key-page_heading_"] > [data-testid="stLayoutWrapper"]:has(.st-key-app_title_link) {{
    flex: 1 1 100%; order: 1;
  }}
  [class*="st-key-page_heading_"] > [data-testid="stLayoutWrapper"]:has([class*="st-key-exports_"]) {{
    order: 0; margin-left: auto;
  }}
  [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{
    flex-wrap: wrap !important;
  }}
  [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    flex: 1 1 100% !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
  }}
}}
@container dashboard_main (max-width: 760px) {{
  [class*="st-key-chart_header_"] {{ min-height: 0; }}
}}
@container dashboard_main (max-width: 900px) {{
  .st-key-table_scroll_hint {{ display: block; }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-kpi_"]) {{ flex-wrap: wrap !important; }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-kpi_"]) > [data-testid="stColumn"] {{
    flex: 1 1 calc(50% - 1rem) !important;
    width: auto !important;
    max-width: 100% !important;
    min-width: 0 !important;
  }}
}}
@container dashboard_main (max-width: 440px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-kpi_"]) > [data-testid="stColumn"] {{
    flex-basis: 100% !important;
    width: 100% !important;
  }}
}}
</style>""")
