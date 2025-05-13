import threading
import warnings
from dataclasses import dataclass, field
from math import exp, log
from queue import Queue
from typing import Optional

import numpy as np

from metrics.command_processor import MetricCommand
from minster.config import ReferenceSequence
from minster.nanopore_read import NanoporeRead


@dataclass
class EstimatorRecord:
    _strata_id: str
    _minimum_fragments_for_ratio_estimation: int
    _command_queue: Queue[Optional[MetricCommand]]
    _log_mean_length: float = 0.0
    _log_squared_difference: float = 0.0
    _read_count: int = 0
    _estimated_reads_received: int = 0
    _consistency_lock: threading.Lock = field(default_factory=threading.Lock)

    def add_entire_read(self, read: NanoporeRead) -> None:
        log_length = log(read.get_sequence_length())
        with self._consistency_lock:
            # https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
            self._read_count += 1
            delta = log_length - self._log_mean_length

            self._log_mean_length += delta / self._read_count

            delta_2 = log_length - self._log_mean_length
            self._log_squared_difference += delta * delta_2

    def get_log_mean(self) -> float:
        return self._log_mean_length

    def get_log_variance(self) -> float:
        return (self._log_squared_difference / (self._read_count - 1)) if self._read_count > 1 else 0.0

    def get_estimated_bases_received(self) -> float:
        exponent = self.get_log_mean() + (self.get_log_variance() / 2)

        if exponent >= 17:
            warnings.warn("The mean of the distribution is very high.")
            warnings.warn("Make sure the warm up number of reads is large enough.")

        return exp(exponent) * self._estimated_reads_received

    def get_estimated_reads_received(self) -> int:
        return self._estimated_reads_received

    def update_estimated_received_bases(self) -> None:
        self._estimated_reads_received += 1

    def is_ratio_estimation_warmed_up(self) -> bool:
        return self._estimated_reads_received >= self._minimum_fragments_for_ratio_estimation


class EstimatorManager:
    def __init__(
            self,
            reference_sequences: list[ReferenceSequence],
            minimum_fragments_for_ratio_estimation: int,
            beta: int,
            command_queue: Queue[Optional[MetricCommand]]
    ):
        self._target_ratios: dict[str, int] = {str(rs.path):rs.expected_ratio for rs in reference_sequences}
        self._beta: int = beta
        self._observed_bases: dict[str, int] = {str(rs.path):0 for rs in reference_sequences}
        self._estimator_records: dict[str, EstimatorRecord] = {
            str(rs.path):EstimatorRecord(
                str(rs.path),
                minimum_fragments_for_ratio_estimation,
                command_queue
            )
            for rs in reference_sequences
        }
        self._command_queue: Queue[Optional[MetricCommand]] = command_queue

    def are_all_warmed_up(self) -> bool:
        return all(
            val.is_ratio_estimation_warmed_up() for val in self._estimator_records.values()
        )

    def get_acceptance_rate(self, strata_id: str) -> float:
        keys = sorted(self._estimator_records)

        ordered_estimated_received_bases = np.array([self._estimator_records[key].get_estimated_bases_received() for key in keys])
        total_estimated_received_bases = np.sum(ordered_estimated_received_bases)

        ordered_target_ratios = np.array([self._target_ratios[k] for k in keys])
        target_whole = np.sum(ordered_target_ratios)
        ordered_target_proportions = ordered_target_ratios / target_whole

        # p_raw / r
        representation = (
                (ordered_estimated_received_bases * target_whole) /
                (ordered_target_ratios * total_estimated_received_bases)
        )
        min_index = np.argmin(representation)

        target_part = self._target_ratios[strata_id]
        estimated_received_part = self._estimator_records[strata_id].get_estimated_bases_received()
        # min_i(p_raw,i / r_i) * (r / p_raw)
        acceptance_rate = (
                (target_part * ordered_estimated_received_bases[min_index]) /
                (ordered_target_ratios[min_index] * estimated_received_part)
        )

        ordered_observed_bases = np.array([self._observed_bases[key] for key in keys])
        total_observed_bases = np.sum(ordered_observed_bases)
        ordered_observed_proportions = ordered_observed_bases / total_observed_bases

        distance = 0.5 * np.sum(np.abs(np.subtract(ordered_observed_proportions, ordered_target_proportions)))
        distance = min(distance, 1 - 1e-5)
        alpha = max(
            1.0,
            -1 * log(1 - distance) * self._beta
        )

        return float(acceptance_rate) ** alpha

    def update_estimated_received_bases(self, strata_id: str) -> None:
        self._estimator_records[strata_id].update_estimated_received_bases()

    def add_entire_read(self, strata_id: str, read: NanoporeRead) -> None:
        self._observed_bases[strata_id] += read.get_sequence_length()
        self._estimator_records[strata_id].add_entire_read(read)
