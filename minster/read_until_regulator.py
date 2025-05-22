import time
from collections import defaultdict
from queue import Queue
from timeit import default_timer as timer
from typing import Iterable, Optional

from metrics.command_processor import MetricCommand, RecordClassifiedReadCommand
from minster.classifiers.classifier import Classifier
from minster.config import ReadUntilSettings
from minster.dorado_wrapper import DoradoWrapper, ReadChunk, ReadChunkWrap
from minster.fragment_collection import FragmentCollection
from minster.strata_balancer import StrataBalancer
from read_until import ReadUntilClient, AccumulatingCache


class ReadUntilRegulator:
    """
    This class interfaces with a basecaller, a classifier, and a balancer to eject
    the reads originating from overrepresented genomes (strata).
    """
    def __init__(
            self,
            read_until_settings: ReadUntilSettings,
            sampling_rate: float,
            classifier: Classifier,
            strata_balancer: StrataBalancer,
            fragment_collection: FragmentCollection,
            command_queue: Queue[Optional[MetricCommand]]
    ):
        print("Initializing the Read Until Client")
        self._read_until_client: ReadUntilClient = ReadUntilClient(
            mk_host=read_until_settings.host,
            mk_port=read_until_settings.port,
            one_chunk=False,
            cache_type=AccumulatingCache
        )
        print("Initializing the Basecaller")
        self._basecaller: DoradoWrapper = DoradoWrapper(
            read_until_settings.basecaller,
            sampling_rate,
            read_until_settings.throttle
        )
        self._depletion_chunks: int = read_until_settings.depletion_chunks
        self._throttle: float = read_until_settings.throttle
        self._classifier: Classifier = classifier
        self._fragment_collection: FragmentCollection = fragment_collection
        self._strata_balancer: StrataBalancer = strata_balancer
        self._command_queue: Queue[Optional[MetricCommand]] = command_queue

    def run(self) -> None:
        self._read_until_client.run()

    def reset(self) -> None:
        self._read_until_client.reset()

    def run_regulation_loop(self) -> None:
        fragments_count: dict[str, int] = defaultdict(int)

        while self._read_until_client.is_running:
            t0 = timer()
            stop_receiving_batch: list[ReadChunk] = []
            unblock_batch: list[ReadChunk] = []

            basecalled_reads: Iterable[ReadChunkWrap] = self._basecaller.basecall(
                # self._read_until_client.channel_count
                self._read_until_client.get_read_chunks(1, last=True),
                self._read_until_client.signal_dtype,
                self._read_until_client.calibration_values
            )

            for chunk_wrap in basecalled_reads:
                read_chunk = chunk_wrap.read_chunk
                matched_cat_id = self._classifier.is_sequence_present(chunk_wrap.seq)
                self._command_queue.put(
                    RecordClassifiedReadCommand(read_chunk.read_id, matched_cat_id)
                )

                clean_up_p = False
                if matched_cat_id is not None:
                    self._strata_balancer.update_estimated_received_bases(matched_cat_id)
                    if self._strata_balancer.thin_out_p(matched_cat_id):
                        self._fragment_collection.add_ejected(read_chunk.read_id)
                        unblock_batch.append(read_chunk)
                    else:
                        stop_receiving_batch.append(read_chunk)
                    clean_up_p = True
                else:
                    fragments_count[read_chunk.read_id] += 1
                    if fragments_count[read_chunk.read_id] >= self._depletion_chunks:
                        stop_receiving_batch.append(read_chunk)
                        clean_up_p = True

                if clean_up_p:
                    fragments_count.pop(read_chunk.read_id, None)

            self._read_until_client.unblock_read_batch(unblock_batch)
            self._read_until_client.stop_receiving_batch(stop_receiving_batch)

            t1 = timer()
            if t0 + self._throttle > t1:
                time.sleep(self._throttle + t0 - t1)
