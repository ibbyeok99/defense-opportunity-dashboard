"""자동 기관 검토 관측 ID. 수집기 계약과 같은 순수 계산·AWS 의존 없음."""
import hashlib
import json

FIELDS = ('institution_code', 'institution_name_raw', 'institution_name_std', 'role', 'operation',
          'first_observed_at', 'is_defense', 'tier', 'classification_reason', 'defense_group',
          'parent_institution', 'source_file')


def observation_id(row):
    value = {k: str(row.get(k) or '').strip() for k in FIELDS}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
