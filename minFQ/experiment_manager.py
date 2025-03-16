import gzip
from typing import Optional

import pyfastx
from minknow_api.protocol_service import ProtocolService

from minFQ.alignment_stats import AlignmentStats, AlignmentStatsContainer
from minFQ.nanopore_read import ReadDirector
from minFQ.run_data_tracker import RunDataContainer
from minFQ.target_region import Bed6


class ExperimentManagerBuilder:
    _regions_path: str
    _regions_fasta: pyfastx.Fasta
    _target_regions: set[Bed6]
    _protocol: Optional[ProtocolService]
    _alignment_stats_container: AlignmentStatsContainer

    def __init__(self, regions_path: str):
        self._regions_path = regions_path
        self._regions_fasta = pyfastx.Fasta(regions_path)
        self._alignment_stats_container = AlignmentStatsContainer()

    def set_protocol(self, protocol: ProtocolService) -> "ExperimentManagerBuilder":
        self._protocol = protocol
        return self

    def add_target_region(self, target_region: Bed6) -> "ExperimentManagerBuilder":
        self._target_regions.add(target_region)
        return self

    def get_result(self) -> "ExperimentManager":
        for target_region  in self._target_regions:
            self._alignment_stats_container.add_alignment_stats(
                AlignmentStats(self._regions_fasta, target_region)
            )

        return ExperimentManager(self._protocol, self._alignment_stats_container)

# NOTE: verify single responsibility principle
class ExperimentManager:
    _protocol: ProtocolService
    _alignment_stats_container: AlignmentStatsContainer
    _runs_being_monitored: RunDataContainer

    def __init__(self, protocol: ProtocolService, alignment_stats_container: AlignmentStatsContainer):
        self._protocol = protocol
        self._alignment_stats_container = alignment_stats_container
        self._runs_being_monitored = RunDataContainer()

    @staticmethod
    def _get_run_id(fastq: str) -> str:
        handle = gzip.open(fastq, "rt") if ".gz" in fastq else open(fastq, "rt")
        with handle as file:
            line = file.readline()
            for _ in line.split():
                if not _.startswith("runid"):
                    break

                run_id = _.split("=")[1]
                return run_id

        raise RuntimeError(fastq + " is not a fastq file created by minKNOW.")

    def get_watch_dir(self) -> str:
        return self._protocol.get_run_info().output_path

    def parse_fastq_file(self, fastq_path: str) -> None:
        run_id = ExperimentManager._get_run_id(fastq_path)

        for record in pyfastx.Fastq(fastq_path):
            run_data = self._runs_being_monitored.get_run_collection(run_id)
            run_data.add_read(ReadDirector(record, fastq_path).construct_read())
