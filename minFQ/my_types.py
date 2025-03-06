from __future__ import annotations

import gzip
import warnings
import numpy as np
from dataclasses import dataclass, field

import mappy as mp
import pyfastx
from typing import Optional, Iterable

from minknow_api.protocol_service import ProtocolService

from multiprocessing import Value
from pathlib import Path

from minFQ.run_data_tracker import RunDataContainer

type DescriptionDict = dict[str, str]
type Bed6 = tuple[str, int, int, str, Optional[int], bool]


@dataclass
class NanoporeRead:
    # NOTE: Think about all the IDs and whether they can be replaced with object references.
    # for other classes as well
    _barcode_name: Optional[str]
    _channel: Optional[int]
    _fastq_file_path: str
    _quality_average: float
    _read: pyfastx.Read
    _read_index: int
    _run_id: str
    _sequence_length: int
    _start_time: str # convert to time

    def get_read_id(self) -> str:
        return self._read.name

    def get_fastq_file_path(self) -> str:
        return self._fastq_file_path

    def get_sequence(self) -> str:
        return self._read.seq

    def get_sequence_length(self) -> int:
        return self._sequence_length

    def get_is_pass(self) -> bool:
        all_parts = Path(self._fastq_file_path).parts

        # https://nanoporetech.com/document/q-system-data-analysis
        # {output_dir}/{experiment_id}/{sample_id}/{start_time}_{device_ID}_{flow_cell_id}_{short_protocol_run_id}/{ext}_{status}/{flow cell id}_{run id}_{batch_number}.{ext}
        if len(all_parts) >= 6:
            if all_parts[-2] == "fastq_pass":
                return True
            elif all_parts[-2] == "fastq_fail":
                return False

        warnings.warn(self._fastq_file_path + " does not comply with the minKNOW specification.")
        return False

# NOTE: since the rest of the code was refactored this can possibly be simplified?
@dataclass
class ReadBuilder:
    _fastq_file_path: str
    _read: pyfastx.Read
    _read_index: int
    _run_id: str
    _start_time: str # NOTE: ditto

    _channel: Optional[int] = None
    _barcode_name: Optional[str] = None

    @staticmethod
    def mean_qscore(quality: list[int]) -> float:
        return -10 * np.log10(np.mean(10 ** (-1 * np.array(quality) / 10)))

    def set_channel(self, channel: int) -> "ReadBuilder":
        self._channel = channel
        return self

    def set_barcode_name(self, barcode_name: str) -> "ReadBuilder":
        self._barcode_name = barcode_name
        return self

    def get_result(self) -> NanoporeRead:
        # NOTE: should average_quality really be a float?
        qual = self._read.quali

        return NanoporeRead(self._barcode_name,
                            self._channel,
                            self._fastq_file_path,
                            round(ReadBuilder.mean_qscore(qual), 2),
                            self._read,
                            self._read_index,
                            self._run_id,
                            len(qual),
                            self._start_time)

@dataclass
class ReadDirector:
    _read: pyfastx.Read
    _fastq_file_path: str

    @staticmethod
    def _parse_fastq_description(description: str) -> DescriptionDict:
        recognized_keys: dict[str, str] = {
            "runid": "run_id"
        }

        description_dict: DescriptionDict = dict()
        descriptors = description.split(" ")

        for item in descriptors:
            if "=" in item:
                bits = item.split("=")
                description_dict[recognized_keys.get(bits[0], bits[0])] = bits[1]
        return description_dict

    def construct_read(self) -> NanoporeRead:
        description_dict = ReadDirector._parse_fastq_description(self._read.description)
        read_builder = ReadBuilder(self._fastq_file_path,
                                   self._read,
                                   int(description_dict["read"]),
                                   description_dict["run_id"],
                                   description_dict["start_time"]) # parse to time

        if "channel" in description_dict:
            read_builder.set_channel(int(description_dict["channel"]))
        if "barcode" in description_dict:
            read_builder.set_barcode_name(description_dict["barcode"].replace(" ", "_"))

        return read_builder.get_result()

class TargetRegion:
    _sequence: pyfastx.Sequence
    _chrom: str
    _region_start: int
    _region_end: int
    _reverse_strand: bool

    def __init__(self, sequence: pyfastx.Sequence, target_region: Bed6):
        self._sequence = sequence

        (self._chrom,
         self._region_start,
         self._region_end,
         _,
         _,
         self._reverse_strand) = target_region

    def get_region_length(self) -> int:
        return self._region_end - self._region_start

    def get_sequence(self) -> str:
        seq = self._sequence[self._chrom][self._region_start:self._region_end]
        return seq.reverse if self._reverse_strand else seq

class AlignmentStats:
    _target_region: TargetRegion
    _aligner: mp.Aligner
    _total_aligned_length: Value[int]
    _read_count: Value[int]

    def __init__(self, sequence: pyfastx.Sequence, target_region: Bed6):
        # NOTE: comparing assigning an object versus creating an object
        # especially in container classes
        self._target_region = TargetRegion(sequence, target_region)
        # NOTE: think about writing files and then using these to save memory
        self._aligner = mp.Aligner(seq=self._target_region.get_sequence(), preset="map-ont")
        self._total_aligned_length = Value('i', 0)
        self._read_count = Value('i', 0)

    def update_stats(self, read: NanoporeRead) -> None:
        seq = read.get_sequence()

        if AlignmentStats.is_high_quality_mapping(self._aligner.map(seq)):
            with self._total_aligned_length.get_lock():
                self._total_aligned_length.value += len(seq)
            with self._read_count.get_lock():
                self._read_count.value += 1

    # NOTE: is the name correct?
    def get_mean_coverage(self) -> float:
        return round(self._total_aligned_length.value / self._target_region.get_region_length(), 2)

    # NOTE: ditto
    def get_mean_read_length(self) -> float:
        read_count = self._read_count.value
        return round(self._total_aligned_length.value / self._read_count.value, 2) if read_count > 0 else 0

    @staticmethod
    def is_high_quality_mapping(hits: Iterable[mp.Alignment]) -> bool:
        for hit in hits:
            if hit.is_primary and hit.mapq >= 20:
                return True

        return False

@dataclass
class AlignmentStatsContainer:
    # NOTE: think about changing the data type to a set
    _alignment_stats_plural: list[AlignmentStats] = field(default_factory=list)

    def add_alignment_stats(self, alignment_stats: AlignmentStats) -> None:
        self._alignment_stats_plural.append(alignment_stats)

    def get_all_alignment_stats(self) -> Iterable[AlignmentStats]:
        return self._alignment_stats_plural

    def update_all_alignment_stats(self, batch: Iterable[NanoporeRead]) -> None:
        for read in batch:
            for alignment_stats in self._alignment_stats_plural:
                alignment_stats.update_stats(read)

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

    def set_protocol(self, protocol: ProtocolService) -> ExperimentManagerBuilder:
        self._protocol = protocol
        return self

    def add_target_region(self, target_region: Bed6) -> ExperimentManagerBuilder:
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
