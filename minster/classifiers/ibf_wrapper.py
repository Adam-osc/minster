import threading
from typing import Optional

import pyfastx
from interleaved_bloom_filter import InterleavedBloomFilter
from math import exp, log, ceil

from minster.classifiers.classifier import Classifier
from minster.config import IBFSettings


class IBFWrapper(Classifier):
    def __init__(self, ibf_settings: IBFSettings, reference_files: list[str]):
        reference_containers = [(rf, pyfastx.Fasta(rf)) for rf in reference_files]

        self._ibf: InterleavedBloomFilter = InterleavedBloomFilter(
            ibf_settings.num_of_bins,
            IBFWrapper.calculate_sbf_size(
                max(len(container) for _, container in reference_containers),
                ibf_settings.w,
                ibf_settings.k,
                ibf_settings.hashes,
                ibf_settings.fp_rate
            ),
            ibf_settings.fragment_length,
            ibf_settings.w,
            ibf_settings.k,
            ibf_settings.hashes
        )
        self._lock: threading.Lock = threading.Lock()
        self._enabled_bins: dict[str, bool] = dict()

        for container_path, container in reference_containers:
            for sequence in container:
                self._ibf.insert_sequence(container_path, sequence.seq)
                self._enabled_bins[container_path] = False

    @staticmethod
    def calculate_sbf_size(max_genome_len: int, w: int, k: int, num_hashes: int, fp_rate: float):
        max_windows = max_genome_len - (w + k - 1) + 1
        return ceil(
                1.0 / (
                    1.0 - exp(log(1 - fp_rate ** (1.0 / num_hashes)) * (1.0 / (num_hashes * max_windows)))
            )
        )

    def activate_sequences(self, container_id: str) -> None:
        with self._lock:
            self._ibf.activate_filter(container_id)
            self._enabled_bins[container_id] = True

    def deactivate_sequences(self, container_id: str) -> None:
        with self._lock:
            self._enabled_bins[container_id] = False

            self._ibf.reset_filter()
            for (bin_id, active) in self._enabled_bins.items():
                if active:
                    self._ibf.activate_filter(bin_id)

    def is_sequence_present(self, sequence: str) -> Optional[str]:
        with self._lock:
            return self._ibf.is_sequence_present(sequence)
