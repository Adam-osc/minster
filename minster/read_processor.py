import threading
from collections import defaultdict
from collections import deque
from typing import Optional

from minster.classifiers.classifier import Classifier
from minster.config import ReadProcessorSettings
from minster.fragment_collection import FragmentCollection
from minster.nanopore_read import NanoporeRead
from minster.strata_balancer import StrataBalancer


class ReadProcessor:
    """
    This class receives basecalled reads from an ExperimentManager and,
    after classification it updates the sample mean and variance for each
    genome.
    """
    def __init__(
            self,
            classifier: Classifier,
            strata_balancer: StrataBalancer,
            fragment_collection: FragmentCollection,
            read_processor_settings: ReadProcessorSettings
    ):
        self._batch_size: int = read_processor_settings.batch_size
        self._target_base_count: int = read_processor_settings.target_base_count
        self._read_count: int = 0
        self._base_count: int = 0
        self._queue: deque[Optional[NanoporeRead]] = deque()
        self._condition: threading.Condition = threading.Condition()
        self._fragment_collection: FragmentCollection = fragment_collection
        self._strata_balancer: StrataBalancer = strata_balancer
        self._classifier: Classifier = classifier
        self._classifiers_activated: bool = False

    def quit(self) -> None:
        with self._condition:
            self._queue.appendleft(None)
            self._condition.notify()

    def add_read(self, read: NanoporeRead) -> None:
        if self._fragment_collection.was_ejected(read.get_read_id()):
            return

        with self._condition:
            self._queue.append(read)

            self._base_count += read.get_sequence_length()
            self._read_count += 1

            if len(self._queue) >= self._batch_size or self._base_count >= self._target_base_count:
                self._condition.notify()

    def process(self) -> None:
        while True:
            with self._condition:
                self._condition.wait()

                breaking = False
                batch: list[NanoporeRead] = []

                while len(self._queue) > 0:
                    read = self._queue.popleft()
                    if read is None:
                        breaking = True
                        break

                    self._read_count -= 1
                    self._base_count -= read.get_sequence_length()

                    batch.append(read)

            if breaking:
                break

            self._strata_balancer.update_alignments(batch)

            if self._classifiers_activated or not self._strata_balancer.are_all_warmed_up():
                continue
            for strata_id in self._strata_balancer.get_all_strata():
                self._classifier.activate_sequences(strata_id)
            self._classifiers_activated = True
