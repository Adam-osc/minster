"""
A class to handle the collection of run statistics and information 
from fastq files.
"""
import logging

from typing import Optional, Deque
from minFQ.utils import SequencingStatistics
from minFQ.my_types import DescriptionDict, Read, ReadContainer, Run

from collections import deque

log = logging.getLogger(__name__)


# REVIEW: refractor using the builder pattern
# Should it be merged with the Run class?
class RunDataTracker:
    def __init__(self, sequencing_statistics: SequencingStatistics):
        log.debug("Initialising Runcollection")

        self.read_count = 0
        self.base_count = 0
        self.tracked_base_count = 0
        self.batchsize = 5000

        self.fastq_file_path: Optional[str] = None

        self.run: Optional[Run] = None

        self.read_names: list[str] = []
        self.read_list: list[Read] = []

        self.sequencing_statistics = sequencing_statistics

        # REVIEW: what about multi-thread queues?
        self.queue: Deque[Read] = deque()


    def set_readnames_based_on_run(self, fastq_file_path: str, read_container: ReadContainer) -> None:
        """
        *Do something* with read ids for the last incomplete file we have in a run
        Parameters
        ----------
        fastq_file_path: str

        Returns
        -------

        """
        if self.fastq_file_path is not None:
            return None

        log.debug("Fetching reads to check if we've uploaded these before.")
        log.debug("Wiping previous reads seen.")

        self.fastq_file_path = fastq_file_path
        read_names = [read.get_read_id() for read in read_container.get_all_reads() if read.get_fastq_file_path()]

        self.read_names = read_names

        log.debug(
            "{} reads already processed and included into readnames list for run {}".format(
                len(self.read_names), self.run.get_run_id() if self.run is not None else "NaN"
            )
        )

    def add_run(self, description_dict: DescriptionDict) -> None:
        """
        Add run
        Parameters
        ----------
        description_dict: dict
            Dictionary of a fastq read description

        Returns
        -------

        """
        run_id = description_dict["run_id"]

        # NOTE: does this check even make sense?
        if self.run is None:
            # NOTE: skipping barcode object creation for now
            self.run = Run(run_id,
                            "barcode" in description_dict)

    def commit_reads(self) -> None:
        """
        Add reads to a queue for further processing.
        Returns
        -------
        None
        """
        if len(self.read_list) > 0:
            # NOTE: write the reads to a buffer
            # a different thread will wait for a signal and re-calculate the coverage using the reads in this buffer
            self.queue.extend(self.read_list)

        self.sequencing_statistics.increment_reads_saved(len(self.read_list))
        self.read_list = []

    @staticmethod
    def check_1d2(read_id):
        """
        Check if the read is 1d&2 by checking the length of the read_id uuid
        Parameters
        ----------
        read_id: str
            The read id to update
        Returns
        -------
        bool
            True if read is 1d^2
        """
        return len(read_id) > 64

    def add_read(self, fastq_read: Read) -> None:
        """
        Add a read to the readnames list
        Parameters
        ----------

        Returns
        -------
        None
        """
        if fastq_read.get_read_id() in self.read_names:
            # NOTE: why is this not recorded in stats?
            # And why are we skipping it?
            # Possibly answer - the read has already been processed?
            # NOTE: How can a read be processed more than once when they are unique?
            return None

        assert not self.check_1d2(fastq_read.get_read_id())

        self.read_names.append(fastq_read.get_read_id())
        self.base_count += fastq_read.get_sequence_length()
        self.tracked_base_count += fastq_read.get_sequence_length()
        self.read_list.append(fastq_read)

        log.debug(
            "Checking read_list size {} - {}".format(
                len(self.read_list), self.batchsize
            )
        )
        # NOTE: is this really necessary
        if len(self.read_list) >= self.batchsize:
            # aiming for yield of 100 Mb in number of reads
            log.debug("Commit reads")
            # NOTE: magic constant 100 Mb
            # if not self.args.skip_sequence:
            self.batchsize = 1000000 // (self.base_count // self.read_count)
            self.commit_reads()
        elif self.tracked_base_count >= 1000000:
            self.commit_reads()
            self.tracked_base_count = 0

        self.read_count += 1
