from __future__ import annotations

import os

import numpy as np
from dataclasses import dataclass, field

import mappy as mp
from typing import Optional, Iterable

type RunDict = dict[str, "RunDataTracker"]
type DescriptionDict = dict[str, str]


@dataclass
class Run:
    _run_id: str
    _is_barcoded: bool

    _barcodes: list[str] = field(default_factory=list)

    def get_run_id(self) -> str:
        return self._run_id

    def get_barcodes(self) -> list[str]:
        return self._barcodes

@dataclass
class FastqFile:
    _file_path: str
    _file_size: int
    _run_id: str

    def get_file_path(self) -> str:
        return self._file_path

    def get_file_size(self) -> int:
        return self._file_size

    def get_run_id(self) -> str:
        return self._run_id

@dataclass
class FastqFileContainer:
    _fastq_files: dict[str, FastqFile] = field(default_factory=dict)

    def add_fastq_file(self, fastq_file: FastqFile) -> None:
        self._fastq_files[fastq_file.get_file_path()] = fastq_file

    def get_fastq_file(self, file_name: str) -> Optional[FastqFile]:
        return self._fastq_files.get(file_name)

    def get_all_fastq_files(self) -> Iterable[FastqFile]:
        return self._fastq_files.values()

@dataclass
class Read:
    # NOTE: Think about all the IDs and whether they can be replaced with object references.
    _barcode_name: Optional[str]
    _channel: Optional[int]
    _fastq_file_path: str
    _quality_average: float
    _read_index: int
    _read_id: str
    _run_id: str
    _sequence_length: int
    _start_time: str # convert to time

    def get_read_id(self) -> str:
        return self._read_id

    def get_fastq_file_path(self) -> str:
        return self._fastq_file_path

    def get_sequence_length(self) -> int:
        return self._sequence_length

    def get_is_pass(self) -> bool:
        folders = os.path.split(self._fastq_file_path)
        if "pass" in folders[0]:
            return True
        elif "fail" in folders[0]:
            return False

        return self._quality_average >= 7

@dataclass
class ReadContainer:
    _reads: dict[str, Read] = field(default_factory=dict)

    def add_read(self, read: Read) -> None:
        self._reads[read.get_read_id()] = read

    def get_read(self, read_id: str) -> Optional[Read]:
        return self._reads.get(read_id)

    def get_all_reads(self) -> Iterable[Read]:
        return self._reads.values()

# NOTE: since the rest of the code was refactored this can possibly go?
@dataclass
class ReadBuilder:
    _fastq_file_path: str
    _quality: list[int]
    _read_index: int
    _read_id: str
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

    def get_result(self) -> Read:
        # NOTE: should average_quality really be a float?
        quality_average = round(ReadBuilder.mean_qscore(self._quality), 2)

        return Read(self._barcode_name,
                    self._channel,
                    self._fastq_file_path,
                    quality_average,
                    self._read_index,
                    self._read_id,
                    self._run_id,
                    len(self._quality),
                    self._start_time)

@dataclass
class ReadDirector:
    _description_dict: DescriptionDict

    def construct_read(self,
                       read_id: str,
                       fastq_file_path: str,
                       quality: list[int]) -> Read:
        run_id = self._description_dict["run_id"]

        read_builder = ReadBuilder(fastq_file_path,
                                   quality,
                                   int(self._description_dict["read"]),
                                   read_id,
                                   run_id,
                                   self._description_dict["start_time"]) # parse to time

        if "channel" in self._description_dict:
            read_builder.set_channel(int(self._description_dict["channel"]))
        if "barcode" in self._description_dict:
            read_builder.set_barcode_name(self._description_dict["barcode"].replace(" ", "_"))

        return read_builder.get_result()

@dataclass
class TargetRegion:
    _file_path: str
    _region_length: int

    def __init__(self, file_path: str, region_length: int):
        self._file_path = file_path
        self._region_length = region_length

    def get_file_path(self) -> str:
        return self._file_path

    def get_region_length(self) -> int:
        return self._region_length

class AlignmentStats:
    _target_region: TargetRegion

    _aligner: mp.Aligner
    _total_aligned_length: int
    _read_count: int

    def __init__(self, file_path: str, region_length: int):
        # NOTE: comparing assigning a object versus creating an object
        # especially in container classes
        self._target_region = TargetRegion(file_path, region_length)
        self._aligner = mp.Aligner(file_path, region_length)

        self._total_aligned_length = 0
        self._read_count = 0

    def update_coverage(self, fastq_file_path: str) -> None:
        for _, seq, _ in mp.fastx_read(fastq_file_path):
            if AlignmentStats.is_high_quality_mapping(self._aligner.map(seq)):
                # NOTE: if we first create a database object get the length from it
                self._total_aligned_length += len(seq)
                self._read_count += 1

    def get_mean_coverage(self) -> float:
        return round(self._total_aligned_length / self._target_region.get_region_length(), 2)

    def get_mean_read_length(self) -> float:
        return round(self._total_aligned_length / self._read_count, 2)

    # NOTE: bioinfo proof why this works
    @staticmethod
    def is_high_quality_mapping(hits: Iterable[mp.Alignment]) -> bool:
        filtered_hits = [hit for hit in hits if hit.is_primary and hit.mapq > 20]
        return len(filtered_hits) >= 2

@dataclass
class AlignmentStatsContainer:
    _alignment_stats: dict[str, AlignmentStats]

    def add_alignment_stats(self, alignment_stats: AlignmentStats) -> None:
        self._alignment_stats[""] = alignment_stats