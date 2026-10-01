"""대시보드 공통 레이아웃 보정.

색·글꼴·카드 모양은 ``.streamlit/config.toml``의 테마가 담당한다.
여기서는 사이드바 폭·본문 폭에 따른 열 재배치·관리자 버튼 배치를 보정한다.
"""

from __future__ import annotations

import streamlit as st

# 사이드바 필터 시작 위치. 사용자가 이 값만 바꿔 조정할 수 있다(단위: px).
SIDEBAR_FILTER_TOP_PX = 50

# 상단은 기존 테마색, 하단은 흰색을 12%만 덧입힌다. 위치·위젯 색에는 적용하지 않는다.
SIDEBAR_GRADIENT_BOTTOM_OPACITY = 0.12

# 공고 상세 제목 글자 크기만 조절한다(단위: rem). 카드 글자 크기와는 별개다.
NOTICE_DETAIL_TITLE_FONT_SIZE_REM = 2.0

# 제목·메뉴의 기존 좌측 정렬을 유지한다(단위: px).
APP_TITLE_OFFSET_X_PX = -21
APP_TITLE_OFFSET_Y_PX = 0
# 공통 상단 영역 시작점. 기존 3.75rem의 절반이며, 도구 모음 높이도 함께 맞춘다.
APP_HEADER_TOP_REM = 1.875

# 후보3 기준의 공통 카드 스타일. 사용자 글자 크기·필터 시작 위치는 보존한다.
SIDEBAR_WIDTH_PX = 288


def apply(_page_title: str = ""):
    """화면과 무관하게 같은 탐색 구조를 유지한다.

    화면별 색을 바꾸지 않는다. 공고·품목·시장 개요는 회청색 중성 기반을 공유하고,
    강조색은 KPI 의미와 차트 계열을 구분하는 데 사용한다.
    """
    side = '[data-testid="stSidebar"]'
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
    st.html(f"""<style>
/* 사이드바 배경만 아래로 갈수록 미세하게 밝아진다. 두 모드에서 같은 효과를 사용한다. */
{side} {{
  background-image: linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, {SIDEBAR_GRADIENT_BOTTOM_OPACITY}) 100%);
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
{side} [data-testid="stSidebarHeader"] {{ display: none !important; }}
{side} [data-testid="stSidebarUserContent"] {{
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
{side} [data-testid="stExpanderDetails"] {{ padding-top: .35rem !important; padding-bottom: .5rem !important; }}
/* 입력·선택칸의 색도 사이드바의 기본 테마를 따른다. */
/* 고객용 화면에서 관리자 입구는 본문 맨 끝에만 둔다. */
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
  {side} [data-testid="stSidebarHeader"] {{ display: flex !important; height: 2.35rem !important; margin-bottom: 0 !important; }}
}}
/* 사이드바·브라우저 확대에 따라 달라지는 실제 본문 폭으로 열을 재배치한다. */
[data-testid="stMainBlockContainer"] {{
  padding-top: {APP_HEADER_TOP_REM}rem;
  container-type: inline-size;
  container-name: dashboard_main;
}}
/* native 도구 모음 아래부터 제목·메뉴·내보내기를 함께 유지한다. */
[data-testid="stHeader"], [data-testid="stToolbar"] {{ height: {APP_HEADER_TOP_REM}rem; min-height: 0; }}
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{
  position: sticky; top: {APP_HEADER_TOP_REM}rem; z-index: 100;
  background: {header_background};
  padding-inline: 21px; margin-inline: -21px; width: calc(100% + 42px); max-width: none;
}}
/* 높이를 고정하지 않아 좁은 화면에서 제목·메뉴가 줄바꿈해도 본문 공간을 확보한다. */
.st-key-page_heading_app h1 {{
  padding-top: 0;
  transform: translate({APP_TITLE_OFFSET_X_PX}px, {APP_TITLE_OFFSET_Y_PX}px);
  word-break: keep-all;
  overflow-wrap: normal;
}}
/* 상단 탐색 메뉴의 시작점도 공통 대제목의 왼쪽 이동값에 맞춘다. */
.st-key-page_menu {{ transform: translateX({APP_TITLE_OFFSET_X_PX}px); }}
/* 좁은 화면은 본문 왼쪽 여백이 17px이므로 제목 이동을 최대 8px로 제한한다. */
@media (max-width: 768px) {{
  [data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]:has(> .st-key-app_sticky_header) {{ padding-inline: 8px; margin-inline: -8px; width: calc(100% + 16px); }}
  .st-key-page_heading_app h1 {{
    transform: translate(max(-8px, {APP_TITLE_OFFSET_X_PX}px), {APP_TITLE_OFFSET_Y_PX}px);
  }}
  .st-key-page_menu {{ transform: translateX(max(-8px, {APP_TITLE_OFFSET_X_PX}px)); }}
}}
/* 사용자 승인: 버튼 박스 대신 웹 링크 메뉴, 활성 밑줄·hover·키보드 포커스. */
.st-key-page_menu a {{
  border-radius: 0; background: transparent !important;
  padding: .55rem .75rem; border-bottom: 3px solid transparent;
  color: inherit !important;
}}
.st-key-page_menu [class*="st-key-nav_active_"] a {{ border-bottom-color: currentColor; }}
.st-key-page_menu a:hover {{ border-bottom-color: currentColor; }}
.st-key-page_menu a:focus-visible {{ outline: 2px solid currentColor; outline-offset: 2px; }}
/* 상세 값 위의 제목 여백을 줄여 제목과 값을 붙인다. */
.st-key-notice_detail_title h2 {{
  font-size: {NOTICE_DETAIL_TITLE_FONT_SIZE_REM}rem;
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
.st-key-entry_summary {{ background: {surface}; border-color: {border} !important; border-radius: 12px; padding: 16px 20px !important; box-shadow: {shadow}; height: auto; flex: 0 0 auto; }}
.st-key-entry_summary > div,
.st-key-entry_summary [data-testid="stLayoutWrapper"],
.st-key-entry_summary [data-testid="stElementContainer"],
.st-key-entry_summary [data-testid="stVerticalBlock"] {{ height: auto !important; min-height: min-content; flex-shrink: 0; }}
.st-key-entry_summary > div {{ flex: 0 0 auto; }}
.st-key-entry_summary [data-testid="stMarkdownContainer"] {{ margin-block: 0 !important; }}
.st-key-entry_summary h3 {{ font-size: 1.25rem; font-weight: 700; padding-block: 0; margin: 0; }}
.st-key-entry_summary_grid {{ border-top: 1px solid {border}; }}
.st-key-entry_summary_half_1 {{ border-left: 1px solid {border}; }}
.st-key-entry_summary [class*="st-key-entry_row_"] {{ min-height: 54px; margin-block: 0 !important; padding: 12px 16px; border-bottom: 1px solid {border}; flex: 0 0 auto; }}
.st-key-entry_summary [class*="st-key-entry_label_"], .st-key-entry_summary [class*="st-key-entry_value_"] {{ min-width: 0; height: auto; }}
.st-key-entry_summary [class*="st-key-entry_label_"] p {{ font-weight: 500; color: {caption}; }}
.st-key-entry_summary [class*="st-key-entry_value_"] strong {{ font-weight: 600; }}
.st-key-entry_summary [class*="st-key-entry_value_"] [data-testid="stMarkdownContainer"] span {{ font-size: 1rem; font-weight: 600; }}
.st-key-entry_summary [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_label_"]) {{ flex: 0 0 190px; width: 190px; }}
.st-key-entry_summary [class*="st-key-entry_row_"] > div:has(> [class*="st-key-entry_value_"]) {{ flex: 1 1 0; min-width: 0; }}
.st-key-entry_summary [data-testid="stMarkdownContainer"] p {{ margin: 0; line-height: 1.5; word-break: keep-all; overflow-wrap: anywhere; }}
.st-key-entry_summary_half_0 > div:last-child [class*="st-key-entry_row_"],
.st-key-entry_summary_half_1 > div:last-child [class*="st-key-entry_row_"] {{ border-bottom: 0; }}
.st-key-entry_summary_agencies [class*="st-key-entry_row_"] {{ border-bottom: 0; }}
.st-key-entry_summary_agencies {{ border-top: 1px solid {border}; }}
.st-key-entry_summary_agencies [data-testid="stMarkdownContainer"] p {{ font-size: .92rem; }}
@container dashboard_main (max-width: 760px) {{
  .st-key-entry_summary_half_1 {{ border-left: 0; padding-left: 0; }}
  .st-key-entry_summary {{ padding: 14px !important; }}
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
[class*="st-key-chart_header_"] h3 {{ font-size: 1.2rem; line-height: 1.4; padding-block: 0; margin-block: 0; }}
[class*="st-key-card_"] [data-testid="stCaptionContainer"] p {{ color: {caption}; font-size: .9rem; line-height: 1.5; }}
[data-testid="stMainBlockContainer"] [data-testid="stTabs"] [role="tablist"] {{ gap: 1.5rem; border-bottom: 1px solid {border}; }}
[data-testid="stMainBlockContainer"] [data-testid="stTabs"] [role="tab"] {{ padding-inline: .35rem; font-weight: 600; }}
.st-key-it_go_notices button {{ min-height: 48px; border-radius: 10px; padding: .65rem 1rem; box-shadow: 0 6px 16px rgba(0,91,255,.12); background-image: linear-gradient(135deg, rgba(255,255,255,.2), rgba(255,255,255,0) 70%); }}
.st-key-it_go_notices button:disabled {{ background-image: none; }}
.st-key-it_go_notices button::after {{ content: "→"; font-size: 1.2rem; margin-left: .35rem; }}
.st-key-item_context h3 {{ font-size: 1.25rem; line-height: 1.5; padding-block: .2rem; }}
.st-key-item_context h3 span {{ border-radius: 8px; }}
.st-key-item_category_heading {{
  background: light-dark(#E7EEF8, #354155); border-radius: 8px;
  padding: .25rem .55rem; gap: .5rem; max-width: 100%;
}}
.st-key-item_category_heading [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; min-width: 0; }}
.st-key-item_category_heading > [data-testid="stLayoutWrapper"]:has(h3) {{ flex: 1 1 auto; min-width: 0; }}
.st-key-item_category_heading h3 {{ padding-block: 0; margin-block: 0; }}
.st-key-item_procurement_icon {{ width: 40px; flex-shrink: 0; border-radius: 6px; background: #E7EEF8; }}
.st-key-item_context {{ margin-bottom: -.5rem; }}
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
[data-testid="stVerticalBlock"][class*="st-key-kpi_"][class*="_nt_"]:not([class*="st-key-kpi_heading_"]) {{
  min-height: 146px !important;
}}
.st-key-notice_results_panel {{
  background: {surface}; border-color: {border} !important; border-radius: 12px;
  box-shadow: {shadow}; padding: 18px !important;
}}
.st-key-notice_results_heading p {{ margin: 0; font-size: 1.08rem; }}
.st-key-notice_results_panel [data-testid="stCaptionContainer"] p {{ font-size: .82rem; margin-block: 0; }}
@container dashboard_main (max-width: 600px) {{
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
  [class*="st-key-page_heading_"] > [data-testid="stLayoutWrapper"]:has(h1) {{
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
  [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) {{ flex-wrap: wrap !important; }}
  [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > div {{
    flex: 1 1 calc(50% - 1rem) !important;
    width: auto !important;
    max-width: 100% !important;
    min-width: 0 !important;
  }}
}}
@container dashboard_main (max-width: 440px) {{
  [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > div {{
    flex-basis: 100% !important;
    width: 100% !important;
  }}
}}
</style>""")
