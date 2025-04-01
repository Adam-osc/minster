import argparse
import concurrent.futures
import sys
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
from typing import Optional

from minknow_api import Connection
from minknow_api.acquisition_pb2 import AcquisitionState
from minknow_api.manager import Manager
from minknow_api.protocol_service import ProtocolService
from watchdog.observers.polling import PollingObserver as Observer

from minster.alignment_stats import AlignmentStatsContainer
from minster.config import ExperimentSettings, SequencerSettings
from minster.experiment_manager import ExperimentManager
from minster.fastq_handler import FastqHandler
from minster.printer import Printer
from minster.read_until_analysis import IBFWrapper, ReadUntilAnalysis
from minster.run_data_tracker import ReadQueue

ACQUISITION_ACTIVE_STATES = {
    AcquisitionState.ACQUISITION_RUNNING
}


def get_active_connection(sequencer_settings: SequencerSettings) -> Optional[Connection]:
    manager = Manager(host=sequencer_settings.host, port=sequencer_settings.port)
    position_connection: Optional[Connection] = None

    for position in manager.flow_cell_positions():
        if position.description.name == sequencer_settings.name:
            position_connection = position.connect()
            break
    if position_connection is None:
        return None
    if position_connection.acquisition.get_acquisition_info().state in ACQUISITION_ACTIVE_STATES :
        return position_connection

    for acquisition_status in position_connection.acquisition.watch_current_acquisition_run():
        if acquisition_status.state in ACQUISITION_ACTIVE_STATES:
            return position_connection

    return None


def clean_threads(message_queue: Queue,
                  printer_thread: threading.Thread,
                  observer: Observer,
                  read_queue: ReadQueue,
                  read_until_analysis: ReadUntilAnalysis,
                  futures: dict[str, Future[None]]) -> None:
    message_queue.put("Shutting down all threads.")
    message_queue.put(None)
    printer_thread.join()

    observer.stop()
    read_queue.quit()
    read_until_analysis.reset()

    for name, future in futures.items():
        future.cancel()
        print(f"{name} finished: {future.done()}")


def start_basecalled_monitoring(
        protocol_service: ProtocolService,
        observer: Observer,
        read_queue: ReadQueue,
        alignment_stats_container: AlignmentStatsContainer
) -> None:
    exp_manager = ExperimentManager(protocol_service,
                                    read_queue,
                                    alignment_stats_container)
    event_handler = FastqHandler(exp_manager)

    watch_dir = Path(exp_manager.get_watch_dir())
    while not watch_dir.exists():
        time.sleep(1)

    observer.schedule(event_handler,
                      path=str(watch_dir),
                      recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except Exception as e:
        print(repr(e))
        observer.stop()
    finally:
        observer.join()


def main() -> None:
    parser = argparse.ArgumentParser(description="minster: dynamic adaptive sampling")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file"
    )
    args = parser.parse_args()

    ExperimentSettings.set_toml_file(Path(args.config))
    experiment_settings = ExperimentSettings()

    print("Waiting for device to enter acquisition state")
    maybe_connection = get_active_connection(experiment_settings.sequencer)
    if maybe_connection is None:
        print("Could not acquire the running protocol.")
        sys.exit(1)
    connection: Connection = maybe_connection
    protocol_service: ProtocolService = connection.protocol

    message_queue: Queue[Optional[str]] = Queue()
    printer = Printer(message_queue)
    printer_thread = threading.Thread(target=printer.process, daemon=True)
    printer_thread.start()

    read_until_settings = experiment_settings.read_until
    print("Building a bloom filter for the reference sequences")
    depletion_ibf = IBFWrapper(read_until_settings.interleaved_bloom_filter,
                               experiment_settings.reference_sequences)
    read_until_analysis = ReadUntilAnalysis(read_until_settings,
                                            float(connection.device.get_sample_rate().sample_rate),
                                            depletion_ibf,
                                            message_queue)
    print("Initializing aligner for the reference sequences")
    alignment_stats_container = AlignmentStatsContainer(experiment_settings.min_coverage,
                                                        experiment_settings.min_read_length,
                                                        message_queue,
                                                        experiment_settings.reference_sequences)
    read_queue = ReadQueue(depletion_ibf,
                           alignment_stats_container)
    read_until_analysis.run()

    observer = Observer()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures: dict[str, Future[None]] = {
            "Analysis": executor.submit(read_until_analysis.analysis),
            "ReadQueue": executor.submit(read_queue.process),
            "BasecalledMonitoring": executor.submit(start_basecalled_monitoring,
                                                    protocol_service,
                                                    observer,
                                                    read_queue,
                                                    alignment_stats_container),
        }

        done, not_done = concurrent.futures.wait(
            futures.values(),
            timeout=0
        )
        print("Dynamic adaptive sampling started")
        try:
            while True:
                freshly_done, not_done = concurrent.futures.wait(not_done, timeout=1)
                if len(freshly_done) > 0:
                    done |= freshly_done

                    clean_threads(message_queue, printer_thread, observer, read_queue, read_until_analysis, futures)
                    break
        except KeyboardInterrupt:
            clean_threads(message_queue, printer_thread, observer, read_queue, read_until_analysis, futures)

        for future in done:
            try:
                future.result()
            except Exception as e:
                print(repr(e))


if __name__ == "__main__":
    main()
