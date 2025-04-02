import threading
from collections import deque
from typing import Optional

from minster.alignment_stats import AlignmentStatsContainer
from minster.nanopore_read import NanoporeRead
from minster.classifiers.classifier import Classifier


class ReadProcessor:
    def __init__(self,
                 classifier: Classifier,
                 alignment_stats_container: AlignmentStatsContainer):
        self._batch_size: int = 5000
        self._target_base_count: int = 1000000
        self._read_count: int = 0
        self._base_count: int = 0
        self._queue: deque[Optional[NanoporeRead]] = deque()
        self._condition: threading.Condition = threading.Condition()
        self._alignment_stats_container: AlignmentStatsContainer = alignment_stats_container
        self._classifier: Classifier = classifier

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
                batched_reads = 0
                batched_bases = 0

                while batched_bases < self._target_base_count and batched_reads < self._batch_size:
                    read = self._queue.popleft()
                    if read is None:
                        breaking = True
                        break

                    batched_reads += 1
                    self._read_count -= 1

                    batched_bases += read.get_sequence_length()
                    self._base_count -= read.get_sequence_length()

                    batch.append(read)

            if breaking:
                break

            for seq_id in self._alignment_stats_container.update_all_alignment_stats(batch):
                self._classifier.activate_sequence(seq_id)
