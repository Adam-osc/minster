import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from datetime import datetime

import numpy as np
import pyfastx

type DescriptionDict = dict[str, str]


@dataclass
class NanoporeRead:
    """
    A class that represents a basecalled Nanopore read.
    """
    _barcode_name: Optional[str]
    _channel: Optional[int]
    _fastq_file_path: str
    _quality_average: float
    _read: pyfastx.Read
    _read_index: int
    _run_id: str
    _start_time: datetime

    def get_read_id(self) -> str:
        return self._read.name

    def get_fastq_file_path(self) -> str:
        return self._fastq_file_path

    def get_sequence(self) -> str:
        return self._read.seq

    def get_sequence_length(self) -> int:
        return len(self._read)

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


@dataclass
class ReadBuilder:
    _fastq_file_path: str
    _read: pyfastx.Read
    _run_id: str
    _start_time: datetime

    _read_index: Optional[int] = None
    _channel: Optional[int] = None
    _barcode_name: Optional[str] = None

    @staticmethod
    def _mean_qscore(quality: list[int]) -> float:
        return -10 * np.log10(np.mean(10 ** (-1 * np.array(quality) / 10)))

    def set_read_index(self, read_index: int) -> "ReadBuilder":
        self._read_index = read_index
        return self

    def set_channel(self, channel: int) -> "ReadBuilder":
        self._channel = channel
        return self

    def set_barcode_name(self, barcode_name: str) -> "ReadBuilder":
        self._barcode_name = barcode_name
        return self

    def get_result(self) -> NanoporeRead:
        qual = self._read.quali

        return NanoporeRead(
            self._barcode_name,
            self._channel,
            self._fastq_file_path,
            ReadBuilder._mean_qscore(qual),
            self._read,
            self._read_index,
            self._run_id,
            self._start_time
        )


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
                parts = item.split("=")
                description_dict[recognized_keys.get(parts[0], parts[0])] = parts[1]
        return description_dict

    def construct_read(self) -> NanoporeRead:
        description_dict = ReadDirector._parse_fastq_description(self._read.description)
        read_builder = ReadBuilder(
            self._fastq_file_path,
            self._read,
            description_dict["run_id"],
            datetime.fromisoformat(description_dict["start_time"])
        )

        if "read" in description_dict:
            read_builder.set_read_index(int(description_dict["read"]))

        channel_query: Optional[str] = None
        if "ch" in description_dict:
            channel_query = "ch"
        elif "channel" in description_dict:
            channel_query = "channel"
        if channel_query is not None:
            read_builder.set_channel(int(description_dict[channel_query]))

        if "barcode" in description_dict:
            read_builder.set_barcode_name(description_dict["barcode"].replace(" ", "_"))

        return read_builder.get_result()
