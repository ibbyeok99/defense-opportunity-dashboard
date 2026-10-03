"""물품분류번호 정확 일치 기반 표시 보정·대조. 분류키·DB·집계값은 변경하지 않는다."""

import re
import unicodedata

import pandas as pd


def official_record(row, reference):
    code = str(row.get("category_value", ""))
    if row.get("procurement_type") not in {"물품", "외자"} or row.get("classification_type") != "product8" or not re.fullmatch(r"\d{8}", code):
        return None
    record = reference.get("records", {}).get(code)
    if not isinstance(record, list) or len(record) != 3 or record[1] != "Y" or not isinstance(record[0], str) or not record[0].strip():
        return None
    return record


def apply_official_names(frame, reference):
    out = frame.copy(deep=True)
    if "display" not in out:
        return out
    out["name_display_source"] = "기존 카탈로그"
    for index, row in out.iterrows():
        record = official_record(row, reference)
        if record is not None:
            out.at[index, "display"] = f"{record[0]} ({row['category_value']})"
            out.at[index, "name_display_source"] = "조달청 공식 품명"
    return out


def catalog_audit(catalog, reference):
    """기존 카탈로그와 현재 공식 목록 사본의 차이. 미대응은 코드 오류를 뜻하지 않는다."""
    rows = []
    for row in catalog.to_dict("records"):
        code = str(row.get("category_value", ""))
        kind = row.get("classification_type", "")
        label = row.get("item_label", "")
        name = row.get("item_name")
        if pd.isna(name) or not str(name).strip():
            name = re.sub(r"\s*\(" + re.escape(code) + r"\)\s*$", "", str(label)) if pd.notna(label) else ""
        name = str(name).strip()
        record = official_record(row, reference)
        if row.get("procurement_type") not in {"물품", "외자"} or kind != "product8":
            status = "다른 분류체계 · 공식 대조 대상 아님"
        elif not re.fullmatch(r"\d{8}", code):
            status = "코드 형식 확인 필요"
        elif record is None:
            status = "공식 목록 미대응"
        elif unicodedata.normalize("NFC", name) == unicodedata.normalize("NFC", record[0].strip()):
            status = "일치"
        else:
            status = "명칭 차이"
        rows.append({"유형": row.get("procurement_type", ""), "분류 방식": kind,
                     "분류키": row.get("item_code", ""), "분류번호": code,
                     "기존 품명": name, "공식 품명": record[0] if record else "–",
                     "대조 결과": status, "기존 명칭 상태": row.get("item_name_status", ""),
                     "공식 변경일": record[2] if record else "–"})
    return pd.DataFrame(rows)
