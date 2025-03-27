import threading
import time
from collections import defaultdict
from pathlib import Path
from timeit import default_timer as timer
from typing import Iterable

import pyfastx
from interleaved_bloom_filter import InterleavedBloomFilter

from minFQ.config import IBFSettings, ReadUntilSettings
from minFQ.dorado_wrapper import DoradoWrapper
from minFQ.dorado_wrapper import ReadChunk
from read_until import ReadUntilClient


class IBFWrapper:
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
            self._ibf.insert_sequence((container_path, ref_seq.name), ref_seq.name)

    def active_filter(self, sequence_id: tuple[str, str]) -> None:
        with self._lock:
            self._ibf.activate_filter(sequence_id)

    def is_sequence_present(self, sequence: str) -> bool:
        with self._lock:
            return self._ibf.is_sequence_present(sequence)

class ReadUntilAnalysis:
    def __init__(self,
                 read_until_settings: ReadUntilSettings,
                 depletion_ibf: IBFWrapper):
        self._read_until_client: ReadUntilClient = ReadUntilClient(mk_host=read_until_settings.host, mk_port=read_until_settings.port, one_chunk=False) # NOTE: check one_check, etc. with readfish
        self._basecaller: DoradoWrapper = DoradoWrapper(read_until_settings.basecaller,
                                         read_until_settings.throttle)
        self._depletion_chunks: int = read_until_settings.depletion_chunks
        self._throttle: float = read_until_settings.throttle
        self._depletion_ibf: IBFWrapper = depletion_ibf

    def analysis(self) -> None:
        depletion_hits: dict[str, int] = defaultdict(int)

        while self._read_until_client.is_running:
            t0 = timer()
            stop_receiving_batch: list[ReadChunk] = []
            unblock_batch: list[ReadChunk] = []

            basecalled_reads: Iterable[ReadChunk] = self._basecaller.basecall(self._read_until_client.get_read_chunks(self._read_until_client.channel_count),
                                                                              self._read_until_client.signal_dtype,
                                                                              self._read_until_client.calibration_values)

            for basecalled_read in basecalled_reads:
                if self._depletion_ibf.is_sequence_present(basecalled_read.seq):
                    depletion_hits[basecalled_read.read_id] += 1
                    if depletion_hits[basecalled_read.read_id] >= self._depletion_chunks:
                        depletion_hits.pop(basecalled_read.read_id)
                        stop_receiving_batch.append(basecalled_read)
                else:
                    unblock_batch.append(basecalled_read)

            self._read_until_client.unblock_read_batch(unblock_batch)
            self._read_until_client.stop_receiving_batch(stop_receiving_batch)

            t1 = timer()
            if t0 + self._throttle > t1:
                time.sleep(self._throttle + t0 - t1)