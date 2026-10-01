"""공고 비교 표시: 공고 자체 조건과 분류 과거 지표를 구분하며, 누락 값을 0으로 바꾸지 않는다."""

import pandas as pd

from view.fmt import notice_identifier, notice_status_label, num, pct, region_display


def compare_notices(details: list[dict]) -> pd.DataFrame:
    if len(details) > 4:
        raise ValueError("공고 비교는 최대 4개입니다.")
    columns = {}
    for i, det in enumerate(details, 1):
        n = det["notice"]
        def date_value(key):
            value = n.get(key)
            return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M") if pd.notna(value) else "미확인"
        entries = {
            "공고명": n["notice_name"], "공고번호·차수": notice_identifier(n),
            "조달 유형": n["procurement_type"], "분류": det["category"],
            "수요기관": n["demand_agency_name"], "공고기관": n["notice_agency_name"],
            "공고일": date_value("notice_date"), "마감": date_value("bid_close_date"),
            "금액 확인": "원문에서 배정예산·추정가격 확인 (비교 화면 미연결)",
            "내 회사 조건 비교": notice_status_label(det["status"]),
        }
        for _, condition in det["conditions"].iterrows():
            required = condition["요구 조건"]
            if condition["구분"] == "지역":
                required = ", ".join(region_display(p) for p in required.split(", "))
            entries[f"{condition['구분']} 요구 조건"] = required
        c = det.get("competition")
        entries["과거 경쟁 기준"] = f"{int(c['year'])}년 · 분류 전체" if c is not None else "자료 없음"
        entries["참가업체 중앙값 (분류)"] = f"{num(c['median_bidders'], 1)}곳" if c is not None else "자료 없음"
        entries["단독입찰 비율 (분류)"] = pct(c["single_bid_rate"]) if c is not None else "자료 없음"
        entries["상위 3개 업체 점유 (분류)"] = pct(c["top3_share_count"]) if c is not None else "자료 없음"
        days = det.get("contract_days")
        entries["계약 소요일 중앙값 (분류)"] = f"{days:.0f}일" if days is not None else "자료 없음"
        columns[f"공고 {i}"] = entries
    return pd.DataFrame(columns).fillna("미확인")
