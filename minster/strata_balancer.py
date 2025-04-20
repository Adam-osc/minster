import random
import threading
from dataclasses import dataclass, field
from queue import Queue
from typing import Iterable, Optional

import mappy as mp

from alignment_stats import AlignmentStats
from minster.config import ReferenceSequence
from minster.metrics.command_processor import MetricCommand, RecordBasecalledReadCommand
from nanopore_read import NanoporeRead


@dataclass
class StrataRecord:
    _expected_ratio: int
    _aligner: mp.Aligner
    _alignment_stats: AlignmentStats

    @property
    def expected_ratio(self) -> int:
        return self._expected_ratio

    @property
    def aligner(self) -> mp.Aligner:
        return self._aligner

    @property
    def alignment_stats(self) -> AlignmentStats:
        return self._alignment_stats

@dataclass
class StrataManager:
    _records: dict[str, StrataRecord] = field(default_factory=dict)

    def insert_record(
            self,
            strata_id: str,
            expected_ratio: int,
            aligner: mp.Aligner
    ) -> None:
        self._records[strata_id] = StrataRecord(expected_ratio, aligner, AlignmentStats(strata_id))

    def get_total_aligned_length(self):
        return sum(record.alignment_stats.get_aligned_length() for record in self._records.values())

    def get_expected_ratio(self, strata_id: str) -> float:
        return self._records[strata_id].expected_ratio

    def get_aligner(self, strata_id: str) -> mp.Aligner:
        return self._records[strata_id].aligner

    def update_aligned_length(self, strata_id: str, nanopore_read: NanoporeRead) -> None:
        self._records[strata_id].alignment_stats.update_aligned_length(nanopore_read)

    def get_aligned_length(self, strata_id: str) -> int:
        return self._records[strata_id].alignment_stats.get_aligned_length()

    def get_all_strata(self) -> Iterable[str]:
        return self._records.keys()

class StrataBalancer:
    def __init__(
            self,
            reference_sequences: list[ReferenceSequence],
            aligners: dict[str, mp.Aligner],
            warn_up_theshold: int,
            command_queue: Queue[Optional[MetricCommand]]
    ):
        self._strata_manager: StrataManager = StrataManager()
        self._whole: int = sum(rs.expected_ratio for rs in reference_sequences)
        for rs in reference_sequences:
            self._strata_manager.insert_record(
                str(rs.path),
                rs.expected_ratio,
                aligners[str(rs.path)]
            )
        self._warm_up_threshold: int = warn_up_theshold
        self._consistent_algn_lock: threading.Lock = threading.Lock()
        self._thr_buf: mp.ThreadBuffer = mp.ThreadBuffer()
        self._command_queue: Queue[Optional[MetricCommand]] = command_queue

    def get_all_strata(self) -> Iterable[str]:
        return self._strata_manager.get_all_strata()

    def are_all_warmed_up_p(self) -> bool:
        # Decided to not keep the alignment state frozen during this method
        return all(
            self._strata_manager.get_aligned_length(strata_id) > self._warm_up_threshold
            for strata_id in self._strata_manager.get_all_strata()
        )

    def thin_out_p(self, strata_id: str) -> bool:
        # Decided to not keep the alignment state frozen during this method
        if not self.are_all_warmed_up_p():
            return False

        with self._consistent_algn_lock:
            temp_aligned_length = self._strata_manager.get_aligned_length(strata_id)
            temp_total_aligned_length = self._strata_manager.get_total_aligned_length()

        threshold = random.random()
        return min(
            (
                    (self._strata_manager.get_expected_ratio(strata_id) * temp_total_aligned_length) /
                    (temp_aligned_length * self._whole)
            ),
            1
        ) < threshold

    def update_alignments(self, reads: Iterable[NanoporeRead]) -> None:
        for read in reads:
            best_read: Optional[NanoporeRead] = None
            best_strata: Optional[str] = None
            best_algn_key: Optional[tuple[int, int, int, float]] = None

            for strata_id in self._strata_manager.get_all_strata():
                hits = self._strata_manager.get_aligner(strata_id).map(read.get_sequence(), buf=self._thr_buf)
                for hit in hits:
                    if not hit.is_primary:
                        continue

                    algn_key = (
                        hit.mapq,
                        hit.score,
                        -hit.NM,
                        hit.mlen / len(read.get_sequence())
                    )
                    if best_read is None or (best_algn_key is not None and algn_key > best_algn_key):
                        best_read = read
                        best_algn_key = algn_key
                        best_strata = strata_id

            if best_read is not None and best_strata is not None:
                with self._consistent_algn_lock:
                    self._strata_manager.update_aligned_length(best_strata, best_read)
                self._command_queue.put(
                    RecordBasecalledReadCommand(best_read.get_read_id(), best_strata, best_read.get_sequence_length())
                )
