"""
A class to handle the collection of run statistics and information 
from fastq files.
"""
import logging

from minFQ.my_types import NanoporeRead, AlignmentStatsContainer

from dataclasses import dataclass
from collections import deque
import threading

log = logging.getLogger(__name__)


class ReadQueue:
    _batch_size: int
    _target_base_count: int
    _read_count: int
    _base_count: int
    _queue: deque[NanoporeRead]
    _condition: threading.Condition
    _processing_thread: threading.Thread
    _alignment_stats_container: AlignmentStatsContainer

    def __init__(self, alignment_stats_container: AlignmentStatsContainer):
        self._batch_size = 5000
        self._target_base_count = 1000000
        self._read_count = 0
        self._base_count = 0
        self._queue = deque()
        self._condition = threading.Condition()
        self._processing_thread = threading.Thread(target=self._process_batch)
        self._processing_thread.start()
        self._alignment_stats_container = alignment_stats_container

    def add_read(self, read: NanoporeRead):
        with self._condition:
            self._queue.append(read)

            self._base_count += read.get_sequence_length()
            self._read_count += 1

            if len(self._queue) >= self._batch_size or self._base_count >= self._target_base_count:
                self._condition.notify()

    def _process_batch(self) -> None:
        log.debug("Processing thread started.")

        while True:
            with self._condition:
                self._condition.wait()

                batch = []
                batched_reads = 0
                batched_bases = 0

                while batched_bases < self._target_base_count and batched_reads < self._batch_size:
                    read = self._queue.popleft()

                    batched_reads += 1
                    self._read_count -= 1

                    batched_bases += read.get_sequence_length()
                    self._base_count -= read.get_sequence_length()

                    batch.append(read)
                self._alignment_stats_container.update_all_alignment_stats(batch)

# REVIEW: refactor using the builder pattern
class RunDataTracker:
    _read_queue: ReadQueue

    def __init__(self, read_queue: ReadQueue):
        log.debug("Initialising RunDataTracker")

        self._read_queue = read_queue

    @staticmethod
    def _check_1d2(read_id):
        return len(read_id) > 64

    def add_read(self, fastq_read: NanoporeRead) -> None:
        assert not self._check_1d2(fastq_read.get_read_id())

        if not fastq_read.get_is_pass():
            return None
        self._read_queue.add_read(fastq_read)

@dataclass
class RunDataContainer:
    _alignment_stats_container: AlignmentStatsContainer
    _read_queue: ReadQueue
    _run_dict: dict[str, RunDataTracker]

    def __init__(self):
        self._alignment_stats_container = AlignmentStatsContainer()
        self._read_queue = ReadQueue(self._alignment_stats_container)
        self._run_dict = dict()

    def get_run_collection(self, run_id: str) -> RunDataTracker:
        if run_id not in self._run_dict:
            self._run_dict[run_id] = RunDataTracker(self._read_queue)
        return self._run_dict[run_id]
