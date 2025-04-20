import pyfastx

from minster.nanopore_read import NanoporeRead


class AlignmentStats:
    def __init__(self, sequence_path: str):
        self._sequence_path: str = sequence_path
        self._sequences: pyfastx.Fasta = pyfastx.Fasta(sequence_path)
        self._aligned_length: int = 0
        self._read_count: int = 0

    def update_aligned_length(self, read: NanoporeRead) -> None:
        self._aligned_length += len(read.get_sequence())
        self._read_count += 1

    def get_aligned_length(self) -> int:
        return self._aligned_length

    def get_mean_coverage(self) -> float:
        return round(self._aligned_length / len(self._sequences), 2)

    def get_mean_read_length(self) -> float:
        read_count = self._read_count
        return round(self._aligned_length / self._read_count, 2) if read_count > 0 else 0