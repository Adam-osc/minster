import gzip

import pyfastx
from minknow_api.protocol_service import ProtocolService

from minster.alignment_stats import AlignmentStatsContainer
from minster.nanopore_read import ReadDirector
from minster.run_data_tracker import DataTrackerContainer, ReadQueue


class ExperimentManager:
    def __init__(self,
                 protocol: ProtocolService,
                 read_queue: ReadQueue,
                 alignment_stats_container: AlignmentStatsContainer):
        self._protocol: ProtocolService = protocol
        self._data_tracker_container: DataTrackerContainer = DataTrackerContainer(read_queue,
                                                                                  alignment_stats_container)

    @staticmethod
    def _get_run_id(fastq: str) -> str:
        handle = gzip.open(fastq, "rt") if ".gz" in fastq else open(fastq, "rt")
        with handle as file:
            line = file.readline()
            for part in line.split():
                if not part.startswith("runid"):
                    continue

                run_id = part.split("=")[1]
                return run_id

        raise RuntimeError(fastq + " is not a fastq file created by minKNOW.")

    def get_watch_dir(self) -> str:
        return self._protocol.get_run_info().output_path

    def parse_fastq_file(self, fastq_path: str) -> None:
        if self._data_tracker_container.stop_run():
            self._protocol.stop_protocol()

        run_id = ExperimentManager._get_run_id(fastq_path)
        run_data = self._data_tracker_container.get_run_collection(run_id)

        for record in pyfastx.Fastq(fastq_path):
            run_data.add_read(ReadDirector(record, fastq_path).construct_read())
