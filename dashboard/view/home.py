"""영상 홈 전용 스타일. 기존 대시보드의 글꼴·배치·검색 동작은 변경하지 않는다."""

from pathlib import Path

import streamlit as st


HERO_VIDEO = Path(__file__).resolve().parents[1] / "assets" / "videos" / "frontline_hero.mp4"

HOME_CSS = """
<style>
body:has(.st-key-home_screen) [data-testid="stSidebar"],
body:has(.st-key-home_screen) [data-testid="stSidebarCollapsedControl"],
body:has(.st-key-home_screen) [data-testid="stHeader"],
body:has(.st-key-home_screen) footer { display: none !important; }
body:has(.st-key-home_screen) [data-testid="stMainBlockContainer"] {
    padding: 0 !important; max-width: none !important;
}
.st-key-home_screen {
    position: fixed; inset: 0; width: 100%; height: 100vh; height: 100dvh;
    margin: 0; padding: 0; overflow: auto; isolation: isolate;
    background: #0b1726; border: 0; border-radius: 0;
}
.st-key-home_video {
    position: absolute; inset: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: -2;
}
.st-key-home_video video {
    position: absolute; inset: 0; width: 100% !important;
    height: 100vh !important; height: 100dvh !important;
    object-fit: cover; object-position: center; border-radius: 0;
}
.st-key-home_video video::-webkit-media-controls { display: none !important; }
.st-key-home_screen::before {
    content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
    background: linear-gradient(90deg, rgba(5, 13, 24, .75), rgba(5, 13, 24, .25));
}
.st-key-home_content {
    position: absolute; top: 50%; transform: translateY(-50%);
    left: max(clamp(24px, 7vw, 120px), env(safe-area-inset-left));
    right: max(clamp(24px, 7vw, 120px), env(safe-area-inset-right));
    width: auto !important; max-width: 1080px; z-index: 1;
}
.frontline-home-copy { color: #fff; }
.frontline-home-copy h1 {
    color: #fff !important; margin: 0 0 22px; padding: 0;
    font-size: clamp(34px, 6.3vw, 88px); font-weight: 700;
    line-height: 1.08; letter-spacing: -.045em; text-wrap: balance;
    animation: frontline-fade-up .8s ease-out both;
}
.frontline-home-slogan {
    margin: 0 0 14px; color: #fff; font-size: clamp(22px, 3vw, 40px);
    line-height: 1.4; font-weight: 600; word-break: keep-all; text-wrap: balance;
    animation: frontline-fade-up .8s ease-out .12s both;
}
.frontline-home-description {
    margin: 0; color: #e2e8f0; font-size: clamp(15px, 1.45vw, 21px);
    line-height: 1.6; word-break: keep-all;
    animation: frontline-fade-up .8s ease-out .24s both;
}
.st-key-home_enter { animation: frontline-fade-up .8s ease-out .36s both; }
.st-key-home_enter button {
    color: #172235 !important; background: #FFB340 !important;
    border: 1px solid #FFB340 !important; border-radius: 8px !important;
    min-height: 52px; padding: 12px 26px !important; margin-top: 10px;
    font-weight: 600; transition: background-color .2s ease, border-color .2s ease;
}
.st-key-home_enter button:hover {
    background: #ffc66e !important; border-color: #ffc66e !important;
}
.st-key-home_enter button:focus-visible { outline: 3px solid #fff; outline-offset: 5px; }
.st-key-home_enter button p { color: inherit !important; font-size: 17px !important; font-weight: 600; }
@keyframes frontline-fade-up {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
}
@media (max-width: 600px) {
    .frontline-home-copy h1 { font-size: clamp(30px, 8.8vw, 48px); letter-spacing: -.04em; }
    .frontline-home-slogan { font-size: clamp(21px, 5.4vw, 28px); }
    .st-key-home_enter button { padding: 12px 20px !important; }
}
@media (max-height: 450px) {
    .st-key-home_content { top: 0; transform: none; padding-top: 28px; padding-bottom: 28px; }
    .frontline-home-copy h1 { font-size: clamp(30px, 5vw, 54px); margin-bottom: 14px; }
    .frontline-home-slogan { font-size: 23px; }
}
@media (prefers-reduced-motion: reduce) {
    .frontline-home-copy h1, .frontline-home-slogan,
    .frontline-home-description, .st-key-home_enter { animation: none; }
    .st-key-home_enter button { transition: none; }
    .st-key-home_video { display: none; }
}
</style>
"""


def apply_home_style():
    st.html(HOME_CSS)


def home_copy() -> str:
    return """<section class="frontline-home-copy" aria-label="FRONTLINE DATA 소개">
    <h1>FRONTLINE DATA</h1>
    <p class="frontline-home-slogan">국방의 오늘, 기회의 내일</p>
    <p class="frontline-home-description">데이터로 보는 국방 조달 시장</p>
    </section>"""
