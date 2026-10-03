"""상세 창의 제한된 백그라운드 작업. worker는 화면/세션을 조작하지 않는다."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from time import monotonic


class RequirementJobs:
    def __init__(self, max_workers=2, max_entries=32, ttl=86400):
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='notice-requirements')
        self.lock = RLock()
        self.jobs = {}
        self.max_entries, self.ttl = max_entries, ttl

    def peek(self, key):
        with self.lock:
            value = self.jobs.get(key)
            if value and value['phase'] != 'running' and monotonic() - value['started'] >= self.ttl:
                del self.jobs[key]
                value = None
            return deepcopy(value['snapshot']) if value else None

    def start(self, key, work, *, force=False):
        with self.lock:
            current = self.peek(key)
            if current and (current['phase'] == 'running' or not force):
                return current
            if key not in self.jobs and len(self.jobs) >= self.max_entries:
                done = next((k for k, v in self.jobs.items() if v['phase'] != 'running'), None)
                if done is None:
                    return {'phase': 'busy', 'message': '확인 작업이 많아 대기 중입니다. 잠시 후 다시 확인하세요.'}
                del self.jobs[done]
            value = {'phase': 'running', 'started': monotonic(),
                     'snapshot': {'phase': 'running', 'message': '확인 순서를 기다리는 중…'}}
            self.jobs[key] = value

            def progress(message):
                with self.lock:
                    value['snapshot']['message'] = message

            def run():
                try:
                    result = work(progress)
                    if result.get('error'):
                        raise ValueError('조회 실패')
                    snapshot = {'phase': 'done', 'result': result, 'message': '조회 종료'}
                except Exception:
                    # 네트워크 예외/키/주소를 그대로 화면에 전달하지 않는다.
                    snapshot = {'phase': 'failed', 'message': '요건을 확인하지 못했습니다. 상세 페이지에서 다시 확인하거나 나라장터 원문을 확인해 주세요.'}
                with self.lock:
                    value['phase'], value['snapshot'] = snapshot['phase'], snapshot

            self.pool.submit(run)
            return deepcopy(value['snapshot'])

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
