import os
import time

from watchdog.events import FileSystemEventHandler, DirCreatedEvent, FileCreatedEvent

from minster.experiment_manager import ExperimentManager


class FastqHandler(FileSystemEventHandler):
    def __init__(self, experiment_manager: ExperimentManager):
        self._experiment_manager: ExperimentManager = experiment_manager

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if (event.src_path.endswith(".fastq") or
            event.src_path.endswith(".fastq.gz") or
            event.src_path.endswith(".fq") or
            event.src_path.endswith(".fq.gz")):
            # NOTE: only for development purposes
            while True:
                initial_size = os.path.getsize(event.src_path)
                time.sleep(1)
                new_size = os.path.getsize(event.src_path)

                if initial_size == new_size:
                    break
            self._experiment_manager.parse_fastq_file(event.src_path)

    # def on_closed(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
    #     if (
    #         event.src_path.endswith(".fastq")
    #         or event.src_path.endswith(".fastq.gz")
    #         or event.src_path.endswith(".fq")
    #         or event.src_path.endswith(".fq.gz")
    #     ):
    #         self._experiment_manager.parse_fastq_file(event.src_path)
