import time

from watchdog.events import FileSystemEventHandler

from minFQ.experiment_manager import ExperimentManager


class FastqHandler(FileSystemEventHandler):
    def __init__(self, experiment_manager: ExperimentManager):
        self._experiment_manager: ExperimentManager = experiment_manager

    def on_created(self, event):
         if (
             event.src_path.endswith(".fastq")
             or event.src_path.endswith(".fastq.gz")
             or event.src_path.endswith(".fq")
             or event.src_path.endswith(".fq.gz")
         ):
            # NOTE: only for testing purpose on development system (macOS)
            time.sleep(5)
            self._experiment_manager.parse_fastq_file(event.src_path)

    # NOTE: is on_closed event enough or do we need an on_modified event as well?
    def on_closed(self, event):
        if (
            event.src_path.endswith(".fastq")
            or event.src_path.endswith(".fastq.gz")
            or event.src_path.endswith(".fq")
            or event.src_path.endswith(".fq.gz")
        ):
            self._experiment_manager.parse_fastq_file(event.src_path)
