from typing import Optional

import pyfastx

type Bed6 = tuple[str, int, int, str, Optional[int], bool]


class TargetRegion:
    def __init__(self, sequence: pyfastx.Sequence, target_region: Bed6):
        self._sequence: pyfastx.Sequence = sequence
        self._chrom: str
        self._region_start: int
        self._region_end: int
        self._region_strand: bool

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