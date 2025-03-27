from dataclasses import dataclass, field
from functools import partial
from typing import Iterable, Callable

import mmh3
import pyfastx
from bitarray import bitarray
from math import floor, ceil, sqrt
from scipy.stats import norm


class InterleavedBloomFilterBuilder:
    _seq: pyfastx.Sequence
    _seq_length: int
    _fragment_length: int
    _k: int
    _num_hashes: int
    _error_rate: float
    _confidence: float

    def __init__(self, seq: pyfastx.Sequence, fragment_length: int, k: int, num_hashes: int, error_rate: float, confidence: float):
        self._seq = seq
        self._seq_length = len(seq)
        self._fragment_length = fragment_length
        self._k = k
        self._num_hashes = num_hashes
        self._error_rate = error_rate
        self._confidence = confidence

    @staticmethod
    def _get_num_fragments(seq_length: int, fragment_length: int, k: int) -> int:
        return (seq_length // (fragment_length - k)) + (0 if seq_length % (fragment_length - k) == 0 else 1)

    # TODO: verify this with a calculator
    @staticmethod
    def _get_size_per_vector(num_hashes: int, fragment_length: int, k: int) -> int:
        r = 0.01 ** (1 / num_hashes)
        max_k_mer = fragment_length - k + 1
        denominator = (1 - r) ** (1 / (num_hashes * max_k_mer)) - 1
        return ceil(-1 / denominator)

    @staticmethod
    def hashes(num_hashes: int, seq: str) -> Iterable[int]:
        for i in range(num_hashes):
            yield mmh3.hash(seq, i)

    def get_result(self) -> "InterleavedBloomFilter":
        num_vectors = InterleavedBloomFilterBuilder._get_num_fragments(self._seq_length, self._fragment_length, self._k)
        size_per_vector = InterleavedBloomFilterBuilder._get_size_per_vector(self._num_hashes, self._fragment_length, self._k)

        bit_array: bitarray = bitarray(num_vectors * size_per_vector)
        bit_array.setall(False)

        for n, frag_start in enumerate(range(0, self._seq_length, self._fragment_length - self._k)):
            fragment = self._seq[frag_start:frag_start + self._fragment_length]
            num_k_mers = len(fragment) - self._k + 1

            for i in range(num_k_mers):
                for h in InterleavedBloomFilterBuilder.hashes(self._num_hashes, fragment[i:i + self._k], ):
                    bit_array[n + (h % num_vectors) * size_per_vector] = True

        return InterleavedBloomFilter(num_vectors,
                                      size_per_vector,
                                      bit_array,
                                      self._k,
                                      partial(InterleavedBloomFilterBuilder.hashes, self._num_hashes),
                                      self._error_rate,
                                      self._confidence)

@dataclass
class InterleavedBloomFilter:
    _num_vectors: int
    _size_per_vector: int
    _bit_array: bitarray
    _k: int
    _hashes: Callable[[str], Iterable[int]]
    _error_rate: float
    _confidence: float

    @staticmethod
    def _reverse_complement(seq: str) -> str:
        reverse_dict: dict[str, str] = {
            "A": "T",
            "T": "A",
            "G": "C",
            "C": "G"
        }
        return "".join(reverse_dict[char] for char in reversed(seq))

    # TODO: can't error rate and alpha be of a different type than a float
    # TODO: manually check with a calculator for (0.1, 13, 400, 0.95)
    @staticmethod
    def _calculate_ci(error_rate: float, k: int, seq_length: int, confidence: float) -> tuple[int, int]:
        q = 1 - (1 - error_rate) ** k
        num_k_mers = seq_length - k + 1
        variance = (num_k_mers * (1 - q) * (q * (2 * k + (2 / error_rate) - 1) - 2 * k)
                    + k * (k - 1) * (1 - q) ** 2
                    + ((2 * (1 - q)) / error_rate ** 2) * ((1 + (k - 1) * (1 - q)) * error_rate - q))
        alpha = 1 - confidence
        z = norm.ppf(1 - alpha / 2)

        return floor(num_k_mers * q - z * sqrt(variance)), ceil(num_k_mers * q + z * sqrt(variance))

    def is_sequence_present(self, seq: str) -> bool:
        _, upper = InterleavedBloomFilter._calculate_ci(self._error_rate, self._k, len(seq), self._confidence)

        return (self._is_sequence_present(seq, upper) or
                self._is_sequence_present(InterleavedBloomFilter._reverse_complement(seq), upper))

    def _is_sequence_present(self, seq: str, threshold: int) -> bool:
        max_count = 0
        result: list[int] = [0 for _ in range(self._size_per_vector)]
        num_k_mers = len(seq) - self._k + 1

        for i in range(num_k_mers):
            bit_result = bitarray(self._size_per_vector)
            bit_result.setall(True)

            for digest in self._hashes(seq[i:i + self._k]):
                bit_start = (digest % self._num_vectors) * self._size_per_vector
                bit_end = bit_start + self._size_per_vector
                bit_result = bit_result & self._bit_array[bit_start:bit_end]

            for j, bit in enumerate(bit_result):
                if bit:
                    result[j] += 1
                    max_count = max(max_count, result[j])
                if max_count >= threshold:
                    return True
                # TODO: verify correctness
                if threshold - max_count > num_k_mers - i - 1:
                    return False
        return False

@dataclass
class InterleavedBloomFilterCollection:
    _fragment_length: int
    _k: int
    _num_hashes: int
    _error_rate: float
    _confidence: float

    _ib_filters: dict[str, tuple[InterleavedBloomFilter, bool]] = field(default_factory=dict)

    # TODO: maybe this shouldn't be a sequence but a iterable of sequences
    def add_genome(self, seq_path: str, seq: pyfastx.Sequence) -> None:
        ibf_builder = InterleavedBloomFilterBuilder(seq,
                                                    self._fragment_length,
                                                    self._k,
                                                    self._num_hashes,
                                                    self._error_rate,
                                                    self._confidence)
        self._ib_filters[seq_path] = (ibf_builder.get_result(), True)

    def deactivate_genome(self, seq_path: str) -> None:
        self._ib_filters[seq_path] = (self._ib_filters[seq_path][0], False)

    def _is_sequence_present(self, chunk: str) -> bool:
        for ib_filter, active in self._ib_filters.values():
            if active and ib_filter.is_sequence_present(chunk):
                return True
        return False

class TargetedIBFs(InterleavedBloomFilterCollection):
    def is_sequence_accepted(self, chunk: str) -> bool:
        return self._is_sequence_present(chunk)
