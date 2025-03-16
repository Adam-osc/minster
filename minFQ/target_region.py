from typing import Optional

import pyfastx

type Bed6 = tuple[str, int, int, str, Optional[int], bool]


class TargetRegion:
    _sequence: pyfastx.Sequence
    _chrom: str
    _region_start: int
    _region_end: int
    _reverse_strand: bool

    def __init__(self, sequence: pyfastx.Sequence, target_region: Bed6):
        self._sequence = sequence

        (self._chrom,
         self._region_start,
         self._region_end,
         _,
         _,
         self._reverse_strand) = target_region

    def get_region_length(self) -> int:
        return self._region_end - self._region_start

    def get_sequence(self) -> str:
        seq = self._sequence[self._chrom][self._region_start:self._region_end]
        return seq.reverse if self._reverse_strand else seq