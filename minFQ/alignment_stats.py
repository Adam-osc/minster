from dataclasses import dataclass, field
from multiprocessing import Value
from typing import Iterable

import mappy as mp
import pyfastx

from minFQ.nanopore_read import NanoporeRead
from minFQ.target_region import TargetRegion, Bed6


class AlignmentStats:
    _target_region: TargetRegion
    _aligner: mp.Aligner
    _total_aligned_length: Value[int]
    _read_count: Value[int]

    def __init__(self, sequence: pyfastx.Sequence, target_region: Bed6):
        # NOTE: comparing assigning an object versus creating an object
        # especially in container classes
        self._target_region = TargetRegion(sequence, target_region)
        # NOTE: think about writing files and then using these to save memory
        self._aligner = mp.Aligner(seq=self._target_region.get_sequence(), preset="map-ont")
        self._total_aligned_length = Value('i', 0)
        self._read_count = Value('i', 0)

    def update_stats(self, read: NanoporeRead) -> None:
        seq = read.get_sequence()

        if AlignmentStats.is_high_quality_mapping(self._aligner.map(seq)):
            with self._total_aligned_length.get_lock():
                self._total_aligned_length.value += len(seq)
            with self._read_count.get_lock():
                self._read_count.value += 1

    # NOTE: is the name correct?
    def get_mean_coverage(self) -> float:
        return round(self._total_aligned_length.value / self._target_region.get_region_length(), 2)

    # NOTE: ditto
    def get_mean_read_length(self) -> float:
        read_count = self._read_count.value
        return round(self._total_aligned_length.value / self._read_count.value, 2) if read_count > 0 else 0

    @staticmethod
    def is_high_quality_mapping(hits: Iterable[mp.Alignment]) -> bool:
        for hit in hits:
            if hit.is_primary and hit.mapq >= 20:
                return True

        return False

@dataclass
class AlignmentStatsContainer:
    # NOTE: think about changing the data type to a set
    _alignment_stats_plural: list[AlignmentStats] = field(default_factory=list)

    def add_alignment_stats(self, alignment_stats: AlignmentStats) -> None:
        self._alignment_stats_plural.append(alignment_stats)

    def get_all_alignment_stats(self) -> Iterable[AlignmentStats]:
        return self._alignment_stats_plural

    def update_all_alignment_stats(self, batch: Iterable[NanoporeRead]) -> None:
        for read in batch:
            for alignment_stats in self._alignment_stats_plural:
                alignment_stats.update_stats(read)
