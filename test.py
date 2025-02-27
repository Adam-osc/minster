import sys
import logging

from minFQ.fastq_handler import FastqHandler
from watchdog.observers.polling import PollingObserver as Observer
from minFQ.utils import SequencingStatistics

from minFQ.my_types import RunDict

logging.basicConfig(
    format="%(asctime)s %(module)s:%(levelname)s:%(thread)d:%(message)s",
    filename="minFQ.log",
    filemode="w",
    level=logging.INFO,
)

log = logging.getLogger()
log.setLevel(logging.DEBUG)


def start_minknow_and_basecalled_monitoring(
    sequencing_statistics: SequencingStatistics,
) -> None:
    """
    Start the minKnow monitoring and basecalled data monitoring in accordance with arguments passed by user
    Parameters
    ----------
    sequencing_statistics: minFQ.utils.SequencingStatistics
        Tracker class for files being monitored, and the metrics about upload
    Returns
    -------

    """
    runs_being_monitored_dict: RunDict = dict()
    event_handler = FastqHandler(runs_being_monitored_dict,
                                 sequencing_statistics)

    observer = Observer()
    for folder in sequencing_statistics.get_watch_directories():
        observer.schedule(event_handler,
                          path=folder,
                          recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            observer.join()
    except (KeyboardInterrupt, Exception) as e:
        observer.stop()
        observer.join()
        print(repr(e))
        print("Exiting - Will take a few seconds to close threads.")
        sys.exit(0)


def main():
    """
    Entry point for minFQ, parses CLI arguments and sets off correct scripts
    Returns
    -------

    """
    target_regions = {
        "/Users/adam/thesis/realtime-seq/test-data/region_01.fa",
        "/Users/adam/thesis/realtime-seq/test-data/region_02.fa"
    }
    # NOTE: create a container class and a class of the coverage statistics
    # mean coverage, etc.
    sequencing_statistics = SequencingStatistics({
        "/Users/adam/thesis/realtime-seq/test-data/2023-08-nanopore-workshop-example-bacteria/fastq"
    })

    start_minknow_and_basecalled_monitoring(sequencing_statistics)


if __name__ == "__main__":
    main()
