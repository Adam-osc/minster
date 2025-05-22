import time
import warnings
from typing import Iterable, NamedTuple

import numpy as np
from minknow_api.data_pb2 import GetLiveReadsResponse
from pybasecall_client_lib.helper_functions import package_read
from pybasecall_client_lib.pyclient import PyBasecallClient

from minster.config import BasecallerSettings
from read_until.base import CALIBRATION


class ReadChunk(NamedTuple):
    channel: int
    read_id: str

class ReadChunkWrap:
    def __init__(self, channel: int, read_id: str, seq: str):
        self._read_chunk: ReadChunk = ReadChunk(channel, read_id)
        self._seq: str = seq

    @property
    def read_chunk(self) -> ReadChunk:
        return self._read_chunk

    @property
    def seq(self) -> str:
        return self._seq


class DoradoWrapper:
    """
    A class that basecalls the accumulated read fragments.
    """
    def __init__(
            self,
            basecaller_settings: BasecallerSettings,
            sampling_rate: float,
            throttle: float
    ):
        self._throttle: float = throttle
        self._max_attempts: int = basecaller_settings.max_attempts
        self._sampling_rate: float = sampling_rate
        self._basecall_client: PyBasecallClient = PyBasecallClient(
            address=str(basecaller_settings.address),
            config=basecaller_settings.config,
        )
        self._basecall_client.set_params({'priority': PyBasecallClient.high_priority})
        self._basecall_client.connect()

    def basecall(
            self,
            reads: list[tuple[int, GetLiveReadsResponse.ReadData]],
            signal_dtype: np.dtype[str],
            calibration_values: dict[int, CALIBRATION]
    ) -> Iterable[ReadChunkWrap]:
        channels: dict[str, int] = dict()
        reads_to_basecall: list[dict] = []

        for channel, read in reads:
            channels[read.id] = channel
            raw_data = np.frombuffer(read.raw_data, signal_dtype)
            packaged_read = package_read(
                    read_id=read.id,
                    raw_data=raw_data,
                    daq_offset=calibration_values[channel].offset,
                    daq_scaling=calibration_values[channel].scaling,
                    sampling_rate=self._sampling_rate,
                    start_time=read.start_sample
            )
            reads_to_basecall.append(packaged_read)

        if len(reads_to_basecall) == 0:
            return None

        passed = False
        for _ in range(self._max_attempts):
            if self._basecall_client.pass_reads(reads_to_basecall):
                passed = True
                break
            time.sleep(self._throttle)
        if not passed:
            warnings.warn("Could not pass the reads to the basecaller.")
            return None

        basecalled_reads = 0
        while len(reads_to_basecall) > basecalled_reads:
            results = self._basecall_client.get_completed_reads()
            if len(results) == 0:
                time.sleep(self._throttle)
                continue

            for results_batch in results:
                for result in results_batch:
                    if result["sub_tag"] > 0:
                        continue

                    read_id = result["metadata"]["read_id"]
                    basecalled_reads += 1

                    yield ReadChunkWrap(
                        channels[read_id],
                        read_id,
                        result["datasets"]["sequence"]
                    )
