"""한 사용자의 같은 검색 결과를 짧게 재사용한다. 원천·조건 변경은 별도로 확인한다."""
from service.notice_list_refresh import refresh_deadline


class NoticeListCache:
    def __init__(self):
        self.key = self.frame = self.loaded_at = self.valid_until = None

    def read(self, key, now, loader):
        if self.frame is not None and self.key == key and self.loaded_at <= now < self.valid_until:
            return self.frame.copy(deep=True), self.loaded_at
        frame = loader()
        self.key, self.loaded_at = key, now
        self.valid_until = refresh_deadline(frame, now)
        self.frame = frame.copy(deep=True)
        return frame, now


def source_version():
    """새 사본·최신 포인터의 원자적 저장과 명시적 데이터 새로고침을 감지한다."""
    from service import source, data, notice_requirements
    directory = source.requirement_evidence_directory()
    def stamp(path):
        try:
            return path.stat().st_mtime_ns
        except FileNotFoundError:
            return None
    return (source.SOURCE, str(directory), stamp(directory), stamp(directory / 'latest'),
            data.NOTICE_CACHE_EPOCH, notice_requirements.SCHEMA)
