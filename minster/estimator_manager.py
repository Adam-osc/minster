import random
import threading
from dataclasses import dataclass, field
from math import log, log10, sqrt

import numpy as np

from minster.config import ReferenceSequence
from minster.nanopore_read import NanoporeRead


@dataclass
class EstimatorRecord:
    _minimum_fragments_for_ratio_estimation: int
    _mean_length: float = 0.0
    _squared_difference: float = 0.0
    _read_count: int = 0
    _estimated_bases: int = 0
    _estimated_on_count_reads: int = 0
    _consistency_lock: threading.Lock = field(default_factory=threading.Lock)

    def add_entire_read(self, read: NanoporeRead) -> None:
        with self._consistency_lock:
            # https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
            self._read_count += 1
            delta = read.get_sequence_length() - self._mean_length

            self._mean_length += delta / self._read_count

            delta_2 = read.get_sequence_length() - self._mean_length
            self._squared_difference += delta * delta_2

    def get_mean(self):
        return self._mean_length

    def get_std(self):
        return sqrt(self._squared_difference / (self._read_count - 1)) if self._read_count > 1 else 0.0

    def get_estimated_received_bases(self) -> int:
        return self._estimated_bases

    def get_estimated_on_count_reads(self) -> int:
        return self._estimated_on_count_reads

    def update_estimated_received_bases(self) -> None:
        self._estimated_bases += self._draw_read_length()
        self._estimated_on_count_reads += 1

    def _draw_read_length(self) -> int:
        with self._consistency_lock:
            return round(10 ** random.normalvariate(mu=log10(self.get_mean()), sigma=log10(self.get_std())))

class EstimatorManager:
    def __init__(
            self,
            reference_sequences: list[ReferenceSequence],
            minimum_fragments_for_ratio_estimation: int,
            beta: int
    ):
        self._target_ratios: dict[str, int] = {str(rs.path):rs.expected_ratio for rs in reference_sequences}
        self._beta: int = beta
        self._observed_bases: dict[str, int] = {str(rs.path):0 for rs in reference_sequences}
        self._estimator_records: dict[str, EstimatorRecord] = {
            str(rs.path):EstimatorRecord(minimum_fragments_for_ratio_estimation)
            for rs in reference_sequences
        }

    def are_all_warmed_up(self) -> bool:
        return all(
            val.get_estimated_on_count_reads() > 2 for val in self._estimator_records.values()
        )

    def get_acceptance_rate(self, strata_id: str) -> float:
        ordered_estimated_received_bases = np.array(
            [self._estimator_records[key].get_estimated_received_bases() for key in sorted(self._estimator_records)]
        )
        ordered_estimated_proportions = ordered_estimated_received_bases / np.sum(ordered_estimated_received_bases)

        ordered_target_ratios = np.array([self._target_ratios[key] for key in sorted(self._target_ratios)])
        ordered_target_proportions =  ordered_target_ratios / np.sum(ordered_target_ratios)

        most_underrepresented_c = np.min(np.divide(ordered_estimated_proportions, ordered_target_proportions))

        ordered_observed_bases = np.array([self._observed_bases[key] for key in sorted(self._observed_bases)])
        ordered_observed_proportions = ordered_observed_bases / np.sum(ordered_observed_bases)

        distance = np.linalg.norm(np.subtract(ordered_observed_proportions, ordered_target_proportions))

        alpha = max(
            1.0,
            -1 * log(1 - float(distance) + 1e-10) * self._beta
        )
        acceptance_rate = most_underrepresented_c * (
            (
                self._target_ratios[strata_id] /
                np.sum(ordered_target_proportions)
            ) / (
                self._estimator_records[strata_id].get_estimated_received_bases() /
                np.sum(ordered_estimated_received_bases)
            )
        )

        return acceptance_rate ** alpha

    def update_estimated_received_bases(self, strata_id: str) -> None:
        self._estimator_records[strata_id].update_estimated_received_bases()

    def add_entire_read(self, strata_id: str, read: NanoporeRead) -> None:
        self._observed_bases[strata_id] += read.get_sequence_length()
        self._estimator_records[strata_id].add_entire_read(read)
