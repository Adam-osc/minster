import random
from dataclasses import dataclass, field
from queue import Queue
from typing import Iterable, Optional

import mappy as mp

from metrics.command_processor import MetricCommand, RecordBasecalledReadCommand, PrintMessageCommand
from minster.alignment_stats import AlignmentStats
from minster.config import ReferenceSequence
from minster.estimator_manager import EstimatorManager
from minster.nanopore_read import NanoporeRead


@dataclass
class StrataRecord:
    _aligner: mp.Aligner
    _alignment_stats: AlignmentStats

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
            aligner: mp.Aligner
    ) -> None:
        self._records[strata_id] = StrataRecord(aligner, AlignmentStats(strata_id))

    def get_total_aligned_length(self):
        return sum(record.alignment_stats.get_aligned_length() for record in self._records.values())

    def get_aligner(self, strata_id: str) -> mp.Aligner:
        return self._records[strata_id].aligner

    def update_aligned_length(self, strata_id: str, nanopore_read: NanoporeRead) -> None:
        self._records[strata_id].alignment_stats.update_aligned_length(nanopore_read)

    def get_aligned_length(self, strata_id: str) -> int:
        return self._records[strata_id].alignment_stats.get_aligned_length()

    def get_aligned_read_count(self, strata_id: str) -> int:
        return self._records[strata_id].alignment_stats.get_read_count()

    def get_all_strata(self) -> Iterable[str]:
        return self._records.keys()

class StrataBalancer:
    def __init__(
            self,
            reference_sequences: list[ReferenceSequence],
            aligners: dict[str, mp.Aligner],
            minimum_mapped_bases: int,
            minimum_reads_for_parameter_estimation: int,
            minimum_fragments_for_ratio_estimation: int,
            thinning_accelerator: int,
            command_queue: Queue[Optional[MetricCommand]]
    ):
        self._strata_manager: StrataManager = StrataManager()
        for rs in reference_sequences:
            self._strata_manager.insert_record(
                str(rs.path),
                aligners[str(rs.path)]
            )
        self._estimator_manager: EstimatorManager = EstimatorManager(
            reference_sequences,
            minimum_fragments_for_ratio_estimation,
            thinning_accelerator,
            command_queue
        )
        self._minimum_mapped_bases: int = minimum_mapped_bases
        self._minimum_reads_for_parameter_estimation: int = minimum_reads_for_parameter_estimation
        self._all_warmed_up: bool = False
        self._thr_buf: mp.ThreadBuffer = mp.ThreadBuffer()
        self._command_queue: Queue[Optional[MetricCommand]] = command_queue

    def get_all_strata(self) -> Iterable[str]:
        return self._strata_manager.get_all_strata()

    def is_warmed_up(self, strata_id: str) -> bool:
        # Decided to not keep the alignment state frozen during this entire method
        return (
                self._strata_manager.get_aligned_length(strata_id) >= self._minimum_mapped_bases and
                self._strata_manager.get_aligned_read_count(strata_id) >= self._minimum_reads_for_parameter_estimation
        )

    def are_all_warmed_up(self) -> bool:
        # Decided to not keep the alignment state frozen during this entire method
        if self._all_warmed_up:
            return True

        all_warmed_up = all(
            self.is_warmed_up(strata_id)
            for strata_id in self._strata_manager.get_all_strata()
        )
        if all_warmed_up:
            self._all_warmed_up = True
        self._command_queue.put(PrintMessageCommand(f"Warm up stage of all strata: {all_warmed_up}"))
        return all_warmed_up

    def thin_out_p(self, strata_id: str) -> bool:
        # Decided to not keep the alignment state frozen during this entire method
        if not self.are_all_warmed_up() or not self._estimator_manager.are_all_warmed_up():
            return False

        self._command_queue.put(
            PrintMessageCommand(f"Thinning a read from {strata_id} with probability {self._estimator_manager.get_acceptance_rate(strata_id)}.")
        )

        draw = random.random()
        return draw > self._estimator_manager.get_acceptance_rate(strata_id)

    def update_estimated_received_bases(self, category: str) -> None:
        if not self.are_all_warmed_up():
            return

        self._estimator_manager.update_estimated_received_bases(category)

    def update_alignments(self, reads: Iterable[NanoporeRead]) -> None:
        for read in reads:
            best_read: Optional[NanoporeRead] = None
            best_strata: Optional[str] = None
            best_algn_key: Optional[tuple[int, int, int]] = None

            for strata_id in self._strata_manager.get_all_strata():
                hits = self._strata_manager.get_aligner(strata_id).map(read.get_sequence(), buf=self._thr_buf)
                for hit in hits:
                    if not hit.is_primary:
                        continue

                    algn_key = (
                        hit.mapq,
                        hit.mlen,
                        -hit.NM
                    )
                    if best_algn_key is None or algn_key > best_algn_key:
                        best_read = read
                        best_algn_key = algn_key
                        best_strata = strata_id

            if best_read is not None and best_strata is not None:
                self._strata_manager.update_aligned_length(best_strata, best_read)
                self._estimator_manager.add_entire_read(best_strata, best_read)
                self._command_queue.put(
                    RecordBasecalledReadCommand(best_read.get_read_id(), best_strata, best_read.get_sequence_length())
                )
