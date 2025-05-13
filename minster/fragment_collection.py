import threading


class FragmentCollection:
    def __init__(self) -> None:
        self._ejected_ids: set[str] = set()
        self._lock: threading.Lock = threading.Lock()

    def add_ejected(self, read_id: str) -> None:
        with self._lock:
            self._ejected_ids.add(read_id)

    def was_ejected(self, read_id: str) -> bool:
        with self._lock:
            return read_id in self._ejected_ids