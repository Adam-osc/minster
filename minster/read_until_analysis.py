import time
from collections import defaultdict
from queue import Queue
from timeit import default_timer as timer
from typing import Iterable

from minster.config import ReadUntilSettings
from minster.dorado_wrapper import DoradoWrapper, ReadChunk, ReadChunkWrap
from minster.classifiers.classifier import Classifier
from read_until import ReadUntilClient


class ReadUntilAnalysis:
    def __init__(self,
                 read_until_settings: ReadUntilSettings,
                 sampling_rate: float,
                 classifier: Classifier,
                 message_queue: Queue):
        print("Initializing the Read Until Client")
        self._read_until_client: ReadUntilClient = ReadUntilClient(mk_host=read_until_settings.host, mk_port=read_until_settings.port, one_chunk=False) # NOTE: check one_check, etc. with readfish
        print("Initializing the Basecaller")
        self._basecaller: DoradoWrapper = DoradoWrapper(read_until_settings.basecaller,
                                                        sampling_rate,
                                                        read_until_settings.throttle)
        self._depletion_chunks: int = read_until_settings.depletion_chunks
        self._throttle: float = read_until_settings.throttle
        self._classifier: Classifier = classifier
        self._message_queue: Queue = message_queue

    def run(self) -> None:
        self._read_until_client.run()

    def reset(self) -> None:
        self._read_until_client.reset()

    def analysis(self) -> None:
        depletion_hits: dict[str, int] = defaultdict(int)

        while self._read_until_client.is_running:
            t0 = timer()
            stop_receiving_batch: list[ReadChunk] = []
            unblock_batch: list[ReadChunk] = []

            basecalled_reads: Iterable[ReadChunkWrap] = self._basecaller.basecall(self._read_until_client.get_read_chunks(self._read_until_client.channel_count, last=True),
                                                                                  self._read_until_client.signal_dtype,
                                                                                 self._read_until_client.calibration_values)

            for chunk_wrap in basecalled_reads:
                read_chunk = chunk_wrap.read_chunk
                if self._classifier.is_sequence_present(chunk_wrap.seq):
                    self._message_queue.put(f"{read_chunk.read_id}: was found positive by the classifier.")
                    depletion_hits[read_chunk.read_id] += 1
                    if depletion_hits[read_chunk.read_id] >= self._depletion_chunks:
                        depletion_hits.pop(read_chunk.read_id)
                        unblock_batch.append(read_chunk)
                else:
                    self._message_queue.put(f"{read_chunk.read_id}: was found negative by the classifier.")
                    stop_receiving_batch.append(read_chunk)

            self._read_until_client.unblock_read_batch(unblock_batch)
            self._read_until_client.stop_receiving_batch(stop_receiving_batch)

            t1 = timer()
            if t0 + self._throttle > t1:
                time.sleep(self._throttle + t0 - t1)
