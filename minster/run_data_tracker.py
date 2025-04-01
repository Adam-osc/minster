import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional

from minster.alignment_stats import AlignmentStatsContainer
from minster.nanopore_read import NanoporeRead
from minster.read_until_analysis import IBFWrapper


class ReadQueue:
    def __init__(self,
                 depletion_ibf: IBFWrapper,
                 alignment_stats_container: AlignmentStatsContainer):
        self._batch_size: int = 5000
        self._target_base_count: int = 1000000
        self._read_count: int = 0
        self._base_count: int = 0
        self._queue: deque[Optional[NanoporeRead]] = deque()
        self._condition: threading.Condition = threading.Condition()
        self._alignment_stats_container: AlignmentStatsContainer = alignment_stats_container
        self._depletion_ibf: IBFWrapper = depletion_ibf

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
                self._depletion_ibf.active_filter(seq_id)

@dataclass
class RunDataTracker:
    _read_queue: ReadQueue

    @staticmethod
    def _check_1d2(read_id: str) -> bool:
        return len(read_id) > 64

    def add_read(self, fastq_read: NanoporeRead) -> None:
        assert not self._check_1d2(fastq_read.get_read_id())

        if not fastq_read.get_is_pass():
            return None
        self._read_queue.add_read(fastq_read)

class DataTrackerContainer:
    def __init__(self,
                 read_queue: ReadQueue,
                 alignment_stats_container: AlignmentStatsContainer):
        self._read_queue: ReadQueue = read_queue
        self._alignment_stats_container: AlignmentStatsContainer = alignment_stats_container
        self._run_dict: dict[str, RunDataTracker] = dict()

    def get_run_collection(self, run_id: str) -> RunDataTracker:
        if run_id not in self._run_dict:
            self._run_dict[run_id] = RunDataTracker(self._read_queue)
        return self._run_dict[run_id]

    def stop_run_p(self) -> bool:
        return self._alignment_stats_container.are_all_covered()
