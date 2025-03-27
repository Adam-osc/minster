import time
import warnings
from collections import namedtuple
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from minknow_api.data_pb2 import GetLiveReadsResponse
from pybasecall_client_lib.helper_functions import package_read
from pybasecall_client_lib.pyclient import PyBasecallClient

from minFQ.config import BasecallerSettings


@dataclass
class ReadChunk:
    _read_id: str
    _channel: int
    _seq: str

    @property
    def read_id(self) -> str:
        return self._read_id

    @property
    def channel(self) -> int:
        return self._channel

    @property
    def seq(self) -> str:
        return self._seq

class DoradoWrapper:
    def __init__(self, basecaller_settings: BasecallerSettings, throttle: float):
        self._throttle: float = throttle
        self._max_attempts: int = basecaller_settings.max_attempts
        self._basecall_client: PyBasecallClient = PyBasecallClient(
            address=str(basecaller_settings.address),
            config=basecaller_settings.config,
        )
        self._basecall_client.connect()

    def basecall(self,
                 reads: list[tuple[int, GetLiveReadsResponse.ReadData]],
                 signal_dtype: np.dtype[str],
                 calibration_values: dict[int, namedtuple]) -> Iterable[ReadChunk]:
        reads_to_basecall: list = []
        for channel, read in reads:
            # NOTE: deal with weak type hints here
            raw_data = np.frombuffer(read.raw_data, signal_dtype)
            reads_to_basecall.append(package_read(read.id,
                                                  raw_data,
                                                  calibration_values[channel].offset,
                                                  calibration_values[channel].scaling))

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

                    yield ReadChunk(read_id,
                                    result["metadata"]["channel"],
                                    result["datasets"]["sequence"])