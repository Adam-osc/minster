from dataclasses import dataclass
from typing import Iterable, Callable
from functools import partial

import mmh3
import pyfastx
from bitarray import bitarray


class IntervalBloomFilterBuilder:
    _seq: pyfastx.Sequence
    _seq_length: int
    _fragment_length: int
    _k: int
    _num_hashes: int

    def __init__(self, seq: pyfastx.Sequence, fragment_length: int, k: int, num_hashes: int):
        self._seq = seq
        self._seq_length = len(seq)
        self._fragment_length = fragment_length
        self._k = k
        self._num_hashes = num_hashes

    @staticmethod
    def _get_num_fragments(seq_length: int, fragment_length: int, k: int) -> int:
        return (seq_length // (fragment_length - k)) + (1 if seq_length % (fragment_length - k) else 0)

    @staticmethod
    def _get_size_per_vector(num_hashes: int, fragment_length: int, k: int) -> int:
        r = 0.01 ** (1 / num_hashes)
        max_k_mer = fragment_length - k + 1
        denominator = (1 - r) ** (1 / (num_hashes * max_k_mer)) - 1
        return round(-1 / denominator)

    @staticmethod
    def hashes(num_hashes: int, seq: str) -> Iterable[int]:
        for i in range(num_hashes):
            yield mmh3.hash(seq, i)

    def get_result(self) -> "IntervalBloomFilter":
        num_vectors = IntervalBloomFilterBuilder._get_num_fragments(self._seq_length, self._fragment_length, self._k)
        size_per_vector = IntervalBloomFilterBuilder._get_size_per_vector(self._num_hashes, self._fragment_length, self._k)

        bit_array: bitarray = bitarray(num_vectors * size_per_vector)
        bit_array.setall(False)

        for n, frag_start in enumerate(range(0, self._seq_length, self._fragment_length - self._k)):
            fragment = self._seq[frag_start:frag_start + self._fragment_length]
            num_k_mers = len(fragment) - self._k + 1

            for i in range(num_k_mers):
                for h in IntervalBloomFilterBuilder.hashes(self._num_hashes, fragment[i:i + self._k], ):
                    bit_array[n + h * num_vectors] = True

        return IntervalBloomFilter(num_vectors,
                                   size_per_vector,
                                   bit_array,
                                   partial(IntervalBloomFilterBuilder.hashes, self._num_hashes))

@dataclass
class IntervalBloomFilter:
    num_vectors: int
    size_per_vector: int
    bit_array: bitarray
    hashes: Callable[[str], Iterable[int]]

    def is_sequence_present(self, seq: str) -> bool:
        pass