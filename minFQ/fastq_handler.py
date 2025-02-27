"""
File Routines for handling fastq files and monitoring locations. Built on watchdog.
"""
import logging
import time

from minFQ.fastq_handler_utils import (
    parse_fastq_description,
    get_file_size,
    get_runid,
    create_run_collection
)
from minFQ.utils import SequencingStatistics
from watchdog.events import FileSystemEventHandler

import pyfastx

from minFQ.my_types import DescriptionDict, ReadContainer, ReadDirector, FastqFile, FastqFileContainer, RunDict

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def parse_fastq_record(
    name: str,
    qual: list[int],
    fastq_file_path: str,
    run_dict: RunDict,
    sequencing_statistic: SequencingStatistics,
    description_dict: DescriptionDict,
) -> None:
    """

    Parameters
    ----------
    name: str
        The fastq read id
    qual: list[int]
        The quality string for this fastq read
    fastq_file_path: str
        The absolute path to this fastq file
    run_dict: RunDict
        Dictionary containg runs that we have seen before and their RunCollection
    sequencing_statistic: SequencingStatistics
        The sequencing statistics class to track metrics about the run
    description_dict: DescriptionDict
        The description dictionary, split by key to value

    Returns
    -------

    """
    run_data = run_dict[description_dict["run_id"]] # NOTE: maybe run_dict should be immutable and created by a RunCollection manager?

    # NOTE: isn't there a better way to check this than in O(n)?
    # maybe change the data structure?
    if name in run_data.read_names:
        # NOTE: maybe it can happen when minKNOW writes files in multiple stages
        sequencing_statistic.increment_reads_skipped()
        return None

    read_director = ReadDirector(description_dict)
    run_data.add_read(read_director.construct_read(name,
                                                   fastq_file_path,
                                                   qual))


def parse_fastq_file(
        fastq_path: str,
        run_dict: RunDict,
        sequencing_stats,
        fastq_file_container: FastqFileContainer,
        read_container: ReadContainer
):
    """
    
    Parameters
    ----------
    fastq_path: str
        Path to the fastq file to parse
    run_dict: dict
        Dictionary containing the run
    sequencing_stats: minFQ.utils.SequencingStatistics
        The class to track the sequencing upload metrics and files

    Returns
    -------
    int 
        The updated number of lines we have already seen from the unblocked read ids file
    """
    log.debug("Parsing fastq file {}".format(fastq_path))
    run_id = get_runid(fastq_path)
    # NOTE: what about a container and a factory combined into a single pattern?
    fastq_file_container.add_fastq_file(FastqFile(fastq_path,
                                                  get_file_size(fastq_path),
                                                  run_id))

    counter = 0
    for record in pyfastx.Fastq(fastq_path):
        counter += 1
        description_dict = parse_fastq_description(record.description)
        sequencing_stats.increment_reads_seen()

        # NOTE: again run_id is unique, we can only encounter it twice if a file got updated
        if run_id not in run_dict:
            create_run_collection(
                run_id,
                run_dict,
                description_dict,
                sequencing_stats
            )
            # NOTE: maybe this should be part of creating a run collection
            run_dict[run_id].set_readnames_based_on_run(fastq_path, read_container)

        # NOTE: possibly pass the entire object
        parse_fastq_record(
            record.name,
            record.qauli,
            fastq_path,
            run_dict,
            sequencing_statistic=sequencing_stats,
            description_dict=description_dict,
        )

    return counter


class FastqHandler(FileSystemEventHandler):
    def __init__(self, rundict, sequencing_statistic):
        """
        Collect information about fastq files that have been written out.
        Parameters
        ----------
        rundict: dict
            The dictionary for tracking the runs
        sequencing_statistic: minFQ.utils.SequencingStatistics
            The class for tracking files and metrics about the upload
        """
        self.sequencing_statistic = sequencing_statistic
        self.rundict = rundict

        self.fastq_file_container = FastqFileContainer()
        self.read_container = ReadContainer()

    def process_file(self, fastq_file_path: str):
        """
        Process fastq files in a thread. This is the work horse for read fastqs. We have one of these per watch directory in the watch list
        :return:
        """
        _ = parse_fastq_file(
            fastq_file_path,
            self.rundict,
            self.sequencing_statistic,
            self.fastq_file_container,
            self.read_container
        )
        self.sequencing_statistic.increment_files_processed()

    def on_created(self, event):
         """Watchdog counts a new file in a folder it is watching as a new file"""
         # This will add a file which is added to the watchfolder to the creates and the info file.
         log.debug("Processing created file {}".format(event.src_path))

         if (
             event.src_path.endswith(".fastq")
             or event.src_path.endswith(".fastq.gz")
             or event.src_path.endswith(".fq")
             or event.src_path.endswith(".fq.gz")
         ):
            self.sequencing_statistic.increment_files_processed()

            # NOTE: only for testing purpose on development system (macOS)
            time.sleep(5)
            self.process_file(event.src_path)

    # NOTE: is on_closed event enough or do we need an on_modified event as well?
    def on_closed(self, event):
        log.debug("Processing closed file {}".format(event.src_path))

        if (
            event.src_path.endswith(".fastq")
            or event.src_path.endswith(".fastq.gz")
            or event.src_path.endswith(".fq")
            or event.src_path.endswith(".fq.gz")
        ):
            self.process_file(event.src_path)
