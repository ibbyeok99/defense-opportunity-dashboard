"""영상 홈 전용 스타일. 기존 대시보드의 글꼴·배치·검색 동작은 변경하지 않는다."""

from pathlib import Path
from functools import lru_cache

import streamlit as st
from PIL import Image


HERO_VIDEO = Path(__file__).resolve().parents[1] / "assets" / "videos" / "frontline_hero.mp4"
HERO_LOGO = Path(__file__).resolve().parents[1] / "assets" / "icons" / "logo_black.png"

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
    background: #DCE6EF; border: 0; border-radius: 0; color-scheme: light;
}
.st-key-home_video {
    position: absolute; inset: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: -2;
}
.st-key-home_video video {
    position: absolute; inset: 0; width: 100% !important;
    height: 100vh !important; height: 100dvh !important;
    object-fit: cover; object-position: right center; border-radius: 0;
}
.st-key-home_video video::-webkit-media-controls { display: none !important; }
.st-key-home_screen::before {
    content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
    background: linear-gradient(90deg, rgba(255,255,255,.72) 0%, rgba(255,255,255,.46) 32%,
                                rgba(255,255,255,.08) 61%, rgba(255,255,255,0) 80%);
}
.st-key-home_content {
    position: absolute; top: clamp(64px, 15.1vh, 170px);
    left: max(clamp(24px, 7.3vw, 140px), env(safe-area-inset-left));
    right: max(clamp(24px, 7.3vw, 140px), env(safe-area-inset-right));
    width: auto !important; max-width: 800px; z-index: 1; gap: 0;
}
.st-key-home_logo {
    position: relative; overflow: hidden; display: block; flex: 0 0 auto;
    width: clamp(190px, 15.4vw, 290px) !important; max-width: 100%;
    aspect-ratio: var(--home-logo-aspect, 4.46); margin-bottom: clamp(26px, 4.6vh, 40px);
    animation: frontline-fade-up .8s ease-out both;
}
.st-key-home_logo [data-testid="stImage"] {
    position: absolute; left: var(--home-logo-left, 0%); top: var(--home-logo-top, 0%);
    width: var(--home-logo-width, 100%) !important; max-width: none;
}
.st-key-home_logo [data-testid="stImage"] img { width: 100% !important; height: auto; }
.st-key-home_logo [data-testid="stElementContainer"],
.st-key-home_logo [data-testid="stFullScreenFrame"] > div { position: static; width: 100%; }
.st-key-home_logo [data-testid="stElementToolbar"] { display: none; }
.frontline-home-copy { color: #070E1C; }
.frontline-home-copy::before {
    content: ""; display: block; width: 42px; height: 2px; background: #DCE8F5;
    margin-bottom: 25px;
}
.frontline-home-copy h1 {
    color: #071A3B !important; margin: 0 0 16px; padding: 0;
    font-size: clamp(42px, 4.5vw, 82px); font-weight: 700;
    line-height: 1.16; letter-spacing: -.035em; word-break: keep-all;
    animation: frontline-fade-up .8s ease-out .12s both;
}
.frontline-home-brand-fallback {
    font-size: clamp(38px, 5vw, 72px); font-weight: 800; margin: 0 0 36px;
}
.frontline-home-description {
    margin: 0; color: #405571; font-size: clamp(20px, 1.8vw, 33px);
    line-height: 1.45; word-break: keep-all;
    animation: frontline-fade-up .8s ease-out .24s both;
}
.st-key-home_enter { animation: frontline-fade-up .8s ease-out .36s both; }
.st-key-home_enter button {
    color: #fff !important; background: #005BFF !important;
    border: 1px solid #005BFF !important; border-radius: 8px !important;
    min-height: clamp(58px, 8.9vh, 77px); min-width: clamp(240px, 16.2vw, 310px);
    padding: 16px 32px !important; margin-top: 30px;
    font-weight: 600; box-shadow: 0 5px 12px #102C5026;
    transition: background-color .2s ease, border-color .2s ease;
}
.st-key-home_enter button:hover {
    background: #0047CC !important; border-color: #0047CC !important;
}
.st-key-home_enter button:focus-visible { outline: 3px solid #fff; outline-offset: 5px; }
.st-key-home_enter button p { color: inherit !important; font-size: clamp(18px, 1.45vw, 24px) !important; font-weight: 600; }
@keyframes frontline-fade-up {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
}
@media (max-width: 600px) {
    .st-key-home_content { top: max(56px, 12vh); }
    .st-key-home_logo { width: min(60%, 220px) !important; margin-bottom: 28px; }
    .frontline-home-copy h1 { font-size: clamp(32px, 8.3vw, 42px); }
    .frontline-home-description { font-size: clamp(20px, 5.1vw, 25px); }
    .st-key-home_enter button { min-height: 58px; padding: 14px 24px !important; margin-top: 26px; }
    .st-key-home_screen::before {
        background: linear-gradient(90deg, rgba(255,255,255,.78), rgba(255,255,255,.18));
    }
}
@media (max-height: 600px) {
    .st-key-home_content { top: 32px; padding-bottom: 28px; }
    .st-key-home_logo { width: clamp(170px, 15.4vw, 250px) !important; margin-bottom: 16px; }
    .frontline-home-copy::before { margin-bottom: 16px; }
    .frontline-home-copy h1 { font-size: clamp(30px, 3.6vw, 44px); }
    .frontline-home-description { font-size: 22px; }
    .st-key-home_enter button { margin-top: 22px; min-height: 54px; padding-block: 12px !important; }
}
@media (prefers-reduced-motion: reduce) {
    .frontline-home-copy h1, .st-key-home_logo,
    .frontline-home-description, .st-key-home_enter { animation: none; }
    .st-key-home_enter button { transition: none; }
    .st-key-home_video { display: none; }
}
</style>
"""


@lru_cache(maxsize=4)
def _logo_crop_css(path: str, modified_ns: int) -> str:
    """투명 여백의 좌표만 읽고 native 이미지의 화면 배치를 보정한다. PNG 원본은 유지한다."""
    with Image.open(path) as image:
        bbox = image.getchannel("A").getbbox() if "A" in image.getbands() else None
        left, top, right, bottom = bbox or (0, 0, *image.size)
        width, height = right - left, bottom - top
        return ("<style>.st-key-home_logo {"
                f"--home-logo-aspect:{width}/{height};--home-logo-width:{image.width / width * 100:.6f}%;"
                f"--home-logo-left:{-left / width * 100:.6f}%;--home-logo-top:{-top / height * 100:.6f}%;"
                "}</style>")


def apply_home_style():
    crop = _logo_crop_css(str(HERO_LOGO), HERO_LOGO.stat().st_mtime_ns) if HERO_LOGO.is_file() else ""
    st.html(HOME_CSS + crop)


def home_copy() -> str:
    return """<section class="frontline-home-copy" aria-label="FRONTLINE DATA 소개">
    <h1>국방의 오늘,<br>기회의 내일</h1>
    <p class="frontline-home-description">데이터로 보는 국방 조달 시장</p>
    </section>"""
