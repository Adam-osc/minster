import threading
from collections import deque
from typing import Optional

from minster.classifiers.classifier import Classifier
from minster.config import ReadProcessorSettings
from minster.nanopore_read import NanoporeRead
from minster.strata_balancer import StrataBalancer


class ReadProcessor:
    def __init__(
            self,
            classifier: Classifier,
            strata_balancer: StrataBalancer,
            read_processor_settings: ReadProcessorSettings
    ):
        self._batch_size: int = read_processor_settings.batch_size
        self._target_base_count: int = read_processor_settings.target_base_count
        self._read_count: int = 0
        self._base_count: int = 0
        self._queue: deque[Optional[NanoporeRead]] = deque()
        self._condition: threading.Condition = threading.Condition()
        self._strata_balancer: StrataBalancer = strata_balancer
        self._classifier: Classifier = classifier
        for strata_id in self._strata_balancer.get_all_strata():
            self._classifier.activate_sequences(strata_id)

    def quit(self) -> None:
        with self._condition:
            self._queue.appendleft(None)
            self._condition.notify()

    def add_read(self, read: NanoporeRead) -> None:
        with self._condition:
            self._queue.append(read)

            self._base_count += read.get_sequence_length()
            self._read_count += 1

            if len(self._queue) >= self._batch_size or self._base_count >= self._target_base_count:
                self._condition.notify()

    def process(self) -> None:
        while True:
            with self._condition:
                self._condition.wait()

                breaking = False
                batch: list[NanoporeRead] = []

                while len(self._queue) > 0:
                    read = self._queue.popleft()
                    if read is None:
                        breaking = True
                        break

                    self._read_count -= 1
                    self._base_count -= read.get_sequence_length()

                    batch.append(read)

            if breaking:
                break
            self._strata_balancer.update_alignments(batch)
