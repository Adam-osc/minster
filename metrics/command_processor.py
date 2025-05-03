from abc import ABC, abstractmethod
from queue import Queue
from typing import Optional

from metrics.metrics_store import MetricsStore


class MetricCommand(ABC):
    @abstractmethod
    def execute(self, store: MetricsStore) -> None:
        pass

class RecordBasecalledReadCommand(MetricCommand):
    def __init__(self, read_id: str, final_class: Optional[str], length: int):
        self._read_id: str = read_id
        self._final_class: Optional[str] = final_class
        self._length: int = length

    def execute(self, store: MetricsStore) -> None:
        store.record_basecalled_reads(self._read_id, self._final_class, self._length)

class RecordClassifiedReadCommand(MetricCommand):
    def __init__(self, read_id: str, inferred_class: Optional[str]):
        self._read_id: str = read_id
        self._inferred_class: Optional[str] = inferred_class

    def execute(self, store: MetricsStore) -> None:
        store.record_classified_reads(self._read_id, self._inferred_class)

class CommandProcessor:
    def __init__(self, queue: Queue[Optional[MetricCommand]], store: MetricsStore):
        self._command_queue: Queue[Optional[MetricCommand]] = queue
        self._store: MetricsStore = store

    def run(self) -> None:
        while True:
            command = self._command_queue.get()
            if command is None:
                self._store.close()
                break
            command.execute(self._store)
