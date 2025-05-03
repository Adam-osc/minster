import threading
from dataclasses import dataclass
from typing import Optional

import mappy as mp

from minster.classifiers.classifier import Classifier


@dataclass
class AlignerRecord:
    _aligner: mp.Aligner
    _active: bool = False

    @property
    def aligner(self) -> mp.Aligner:
        return self._aligner

    @property
    def active(self) -> bool:
        return self._active

    def toggle_active(self) -> None:
        self._active = not self.active

class MappyWrapper(Classifier):
    def __init__(self, aligners: dict[str, mp.Aligner]):
        self._thr_buf: mp.ThreadBuffer = mp.ThreadBuffer()
        self._all_aligners: dict[str, AlignerRecord] = {key:AlignerRecord(aligner) for (key, aligner) in aligners.items()}
        self._lock: threading.Lock = threading.Lock()

    def activate_sequences(self, container_id: str) -> None:
        with self._lock:
            if not self._all_aligners[container_id].active:
                self._all_aligners[container_id].toggle_active()

    def deactivate_sequences(self, container_id: str) -> None:
        with self._lock:
            if self._all_aligners[container_id].active:
                self._all_aligners[container_id].toggle_active()

    def is_sequence_present(self, sequence: str) -> Optional[str]:
        best_algn_key: Optional[tuple[int, int, int]] = None
        best_cont_id: Optional[str] = None

        with self._lock:
            for container_id, aligner_record in self._all_aligners.items():
                if not aligner_record.active:
                    continue

                for hit in aligner_record.aligner.map(sequence, buf=self._thr_buf):
                    if not hit.is_primary:
                        continue

                    algn_key = (
                        hit.mapq,
                        hit.mlen,
                        -hit.NM
                    )
                    if best_algn_key is None or algn_key > best_algn_key:
                        best_cont_id = container_id
                        best_algn_key = algn_key

        return best_cont_id
