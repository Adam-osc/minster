import threading
from pathlib import Path

import pyfastx
from interleaved_bloom_filter import InterleavedBloomFilter

from minster.classifiers.classifier import Classifier
from minster.config import IBFSettings


class IBFWrapper(Classifier):
    def __init__(self, ibf_settings: IBFSettings, reference_files: list[Path]):
        reference_sequences = [(str(path), ref_seq) for path in reference_files for ref_seq in pyfastx.Fasta(str(path))]

        self._ibf: InterleavedBloomFilter = InterleavedBloomFilter(
            max(len(ref_seq) for _, ref_seq in reference_sequences),
            ibf_settings.fragment_length,
            ibf_settings.k,
            ibf_settings.k,
            ibf_settings.hashes,
            ibf_settings.error_rate,
            ibf_settings.confidence)
        self._lock: threading.Lock = threading.Lock()

        for container_path, ref_seq in reference_sequences:
            self._ibf.insert_sequence((container_path, ref_seq.name), ref_seq.seq)

    def activate_sequence(self, sequence_id: tuple[str, str]) -> None:
        with self._lock:
            self._ibf.activate_filter(sequence_id)

    def is_sequence_present(self, sequence: str) -> bool:
        with self._lock:
            return self._ibf.is_sequence_present(sequence)