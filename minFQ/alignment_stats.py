from dataclasses import dataclass, field
from multiprocessing import Value
from typing import Iterable

import mappy as mp
import pyfastx

from minFQ.nanopore_read import NanoporeRead


class AlignmentStats:
    def __init__(self, sequence_file: str, sequence: pyfastx.Sequence):
        # NOTE: comparing assigning an object versus creating an object
        # especially in container classes
        self._sequence_file: str = sequence_file
        self._sequence = sequence
        self._aligner: mp.Aligner = mp.Aligner(seq=sequence.seq, preset="map-ont")
        self._aligned_length: Value[int] = Value('i', 0)
        self._read_count: Value[int] = Value('i', 0)
        self._min_coverage: int = ...
        self._min_read_length: int = ...

    def update_stats(self, read: NanoporeRead) -> bool:
        seq = read.get_sequence()

        if AlignmentStats._is_high_quality_mapping(self._aligner.map(seq)):
            with self._aligned_length.get_lock():
                self._aligned_length.value += len(seq)
            with self._read_count.get_lock():
                self._read_count.value += 1

        return (self.get_mean_coverage() >= self._min_coverage and
                    self.get_mean_read_length() >= self._min_read_length)

    def get_mean_coverage(self) -> float:
        return round(self._aligned_length.value / len(self._sequence), 2)

    def get_mean_read_length(self) -> float:
        read_count = self._read_count.value
        return round(self._aligned_length.value / self._read_count.value, 2) if read_count > 0 else 0

    @staticmethod
    def _is_high_quality_mapping(hits: Iterable[mp.Alignment]) -> bool:
        for hit in hits:
            if hit.is_primary and hit.mapq >= 20:
                return True

        return False

@dataclass
class AlignmentStatsContainer:
    _alignment_stats_plural: dict[tuple[str, str], AlignmentStats] = field(default_factory=list)

    def add_alignment_stats(self, sequence_file: str, sequence: pyfastx.Sequence) -> None:
        self._alignment_stats_plural[sequence_file, sequence.name] = AlignmentStats(sequence_file, sequence)

    def get_all_alignment_stats(self) -> Iterable[AlignmentStats]:
        return self._alignment_stats_plural.values()

    def update_all_alignment_stats(self, batch: Iterable[NanoporeRead]) -> Iterable[tuple[str, str]]:
        for read in batch:
            for seq_id, alignment_stats in self._alignment_stats_plural.items():
                if alignment_stats.update_stats(read):
                    yield seq_id