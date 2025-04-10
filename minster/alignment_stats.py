from multiprocessing import Value
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from queue import Queue
from typing import Iterable

import mappy as mp
import pyfastx

from minster.nanopore_read import NanoporeRead


class AlignmentStats:
    def __init__(self, sequence: pyfastx.Sequence, min_coverage: int, min_read_length: int):
        self._sequence: pyfastx.Sequence = sequence
        self._aligner: mp.Aligner = mp.Aligner(seq=sequence.seq, preset="map-ont")
        self._aligned_length: Synchronized[int] = Value('i', 0)
        self._read_count: Synchronized[int] = Value('i', 0)
        self._min_coverage: int = min_coverage
        self._min_read_length: int = min_read_length

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


class AlignmentStatsContainer:
    def __init__(
            self,
            min_coverage: int,
            min_read_length: int,
            message_queue: Queue,
            reference_sequences: list[Path]
    ):
        self._min_coverage: int = min_coverage
        self._min_read_length: int = min_read_length
        self._alignment_stats_plural: dict[tuple[str, str], AlignmentStats] = dict()
        self._coverage_map: dict[tuple[str, str], bool] = dict()
        self._message_queue: Queue[str] = message_queue

        for reference_file in reference_sequences:
            for sequence in pyfastx.Fasta(str(reference_file)):
                self._alignment_stats_plural[(str(reference_file), sequence.name)] = AlignmentStats(
                    sequence,
                    self._min_coverage,
                    self._min_read_length
                )
                self._coverage_map[(str(reference_file), sequence.name)] = False

    def get_all_alignment_stats(self) -> Iterable[AlignmentStats]:
        return self._alignment_stats_plural.values()

    def are_all_covered(self) -> bool:
        return all(self._coverage_map.values())

    def update_all_alignment_stats(self, batch: Iterable[NanoporeRead]) -> Iterable[tuple[str, str]]:
        for read in batch:
            for seq_id, alignment_stats in self._alignment_stats_plural.items():
                if alignment_stats.update_stats(read):
                    yield seq_id

        # NOTE: info printing
        for seq_id, alignment_stats in self._alignment_stats_plural.items():
            self._message_queue.put(
                f"{seq_id}\tmean coverage: {alignment_stats.get_mean_coverage()}\tmean read length: {alignment_stats.get_mean_read_length()}")
