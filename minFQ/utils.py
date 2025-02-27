class SequencingStatistics:
    """
    A class to store data about the sequencing
    """
    def __init__(self, watch_directories: set[str]):
        self._files_seen = 0
        self._files_processed = 0
        self._files_skipped = 0
        self._reads_seen = 0
        self._reads_saved = 0
        self._reads_skipped = 0
        self._watch_directories: frozenset[str] = frozenset(watch_directories)

    def increment_files_seen(self, by: int=1):
        self._files_seen += by

    def increment_files_processed(self, by: int=1):
        self._files_processed += by

    def increment_files_skipped(self, by: int=1):
        self._files_skipped += by

    def increment_reads_seen(self, by: int=1):
        self._reads_seen += by

    def increment_reads_saved(self, by: int=1):
        self._reads_saved += by

    def increment_reads_skipped(self, by: int=1):
        self._reads_skipped += by

    def get_watch_directories(self) -> frozenset[str]:
        return self._watch_directories