import gzip
import logging
import os

from minFQ.run_data_tracker import RunDataTracker

from minFQ.utils import SequencingStatistics
from minFQ.my_types import DescriptionDict, RunDict

log = logging.getLogger(__name__)

def get_file_size(file_path: str) -> int:
    """
    Returns the size of the filepath in bytes.
    :param file_path: The path to file in the watch directory
    :return:
    """
    return os.path.getsize(file_path)


def parse_fastq_description(description: str) -> DescriptionDict:
    """
    Parse the description found in a fastq reads header

    Parameters
    ----------
    description: str
        A string of the fastq reads description header

    Returns
    -------
    description_dict: dict
        A dictionary containing the keys and values found in the fastq read headers
    """
    recognized_keys: dict[str, str] = {
        "runid": "run_id"
    }

    # NOTE: create a dictionary of accepted strings and the keys they are translated to
    description_dict: DescriptionDict = dict()
    descriptors = description.split(" ")

    for item in descriptors:
        if "=" in item:
            bits = item.split("=")
            description_dict[recognized_keys.get(bits[0], bits[0])] = bits[1]
    return description_dict


def get_runid(fastq: str) -> str:
    """
    Open a fastq file, read the first line and parse out the Run ID
    :param fastq: path to the fastq file to be parsed
    :type fastq: str
    :return runid: The run ID of this fastq file as a string
    """
    runid = ""

    handle = gzip.open(fastq, "rt") if ".gz" in fastq else open(fastq, "rt")
    with handle as file:
        line = file.readline()
        for _ in line.split():
            if not _.startswith("runid"):
                continue

            runid = _.split("=")[1]
            break

    return runid


def create_run_collection(run_id, run_dict: RunDict, description_dict, sequencing_statistics) -> None:
    """
    Create run collection for this run id if we don't already have one, store in run_dict
    Parameters
    ----------
    run_id: str
        The uuid of this run
    run_dict: dict
        The dictionary containing run collections
    description_dict: dict
        The description dict
    sequencing_statistics: SequencingStatistics
        Class to communicate sequencing statistics
    Returns
    -------

    """
    run_dict[run_id] = RunDataTracker(sequencing_statistics)
    run_dict[run_id].add_run(description_dict)
