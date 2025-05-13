import argparse
import concurrent.futures
import sys
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
from typing import Optional

import mappy as mp
from minknow_api import Connection
from minknow_api.acquisition_pb2 import AcquisitionState
from minknow_api.manager import Manager
from minknow_api.protocol_service import ProtocolService
from watchdog.observers.polling import PollingObserver as Observer

from metrics.command_processor import MetricCommand, CommandProcessor
from metrics.metrics_store import MetricsStore
from minster.classifiers.classifier import Classifier
from minster.classifiers.classifier_factory import ClassifierFactory
from minster.config import ExperimentSettings, SequencerSettings
from minster.experiment_manager import ExperimentManager
from minster.fastq_handler import FastqHandler
from minster.fragment_collection import FragmentCollection
from minster.read_processor import ReadProcessor
from minster.read_until_regulator import ReadUntilRegulator
from minster.strata_balancer import StrataBalancer
from simulation.fake_protocol_service import FakeProtocolService

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
    if position_connection.acquisition.get_acquisition_info().state in ACQUISITION_ACTIVE_STATES:
        return position_connection

    for acquisition_status in position_connection.acquisition.watch_current_acquisition_run():
        if acquisition_status.state in ACQUISITION_ACTIVE_STATES:
            return position_connection

    return None


def clean_threads(
        command_queue: Queue[Optional[CommandProcessor]],
        cmd_processor_thread: threading.Thread,
        observer: Observer,
        read_processor: ReadProcessor,
        read_until_regulator: ReadUntilRegulator,
        futures: dict[str, Future[None]]
) -> None:
    command_queue.put(None)
    cmd_processor_thread.join()

    observer.stop()
    read_processor.quit()
    read_until_regulator.reset()

    for name, future in futures.items():
        future.cancel()
        print(f"{name} finished: {future.done()}")


def start_basecalled_monitoring(
        protocol_service: ProtocolService,
        observer: Observer,
        read_processor: ReadProcessor,
) -> None:
    exp_manager = ExperimentManager(
        protocol_service,
        read_processor,
    )
    event_handler = FastqHandler(exp_manager)

    watch_dir = Path(exp_manager.get_watch_dir())
    while not watch_dir.exists():
        time.sleep(1)

    observer.schedule(
        event_handler,
        path=str(watch_dir),
        recursive=True
    )
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
    parser.add_argument(
        "--simulated-dir",
        type=str,
        required=False,
        help="Path to the dir where the Icarust simulator writes data"
    )
    args = parser.parse_args()

    ExperimentSettings.set_toml_file(Path(args.config))
    experiment_settings = ExperimentSettings()

    command_queue: Queue[Optional[MetricCommand]] = Queue()
    metrics_store = MetricsStore(str(experiment_settings.metrics_store))
    command_processor = CommandProcessor(command_queue, metrics_store)
    cmd_processor_thread = threading.Thread(target=command_processor.run, daemon=True)
    cmd_processor_thread.start()

    print("Initializing aligner for the reference sequences")
    reference_files: list[str] = [str(rf.path) for rf in experiment_settings.reference_sequences]
    aligners: dict[str, mp.Aligner] = {
        rf:mp.Aligner(rf) for rf in reference_files
    }
    classifier_factory = ClassifierFactory(aligners, reference_files)
    classifier: Classifier = classifier_factory.create(experiment_settings.read_until.classifier)

    strata_balancer = StrataBalancer(
        experiment_settings.reference_sequences,
        aligners,
        experiment_settings.minimum_mapped_bases,
        experiment_settings.minimum_reads_for_parameter_estimation,
        experiment_settings.minimum_fragments_for_ratio_estimation,
        experiment_settings.thinning_accelerator,
        command_queue
    )

    protocol_service: FakeProtocolService | ProtocolService
    sample_rate: float
    if args.simulated_dir is not None:
        protocol_service = FakeProtocolService(args.simulated_dir)
        sample_rate = 4000.0
    else:
        print("Waiting for device to enter acquisition state")
        maybe_connection = get_active_connection(experiment_settings.sequencer)
        if maybe_connection is None:
            print("Could not acquire the running protocol.")
            sys.exit(1)
        connection: Connection = maybe_connection
        protocol_service: ProtocolService = connection.protocol
        sample_rate = float(connection.device.get_sample_rate().sample_rate)

    fragment_collection = FragmentCollection()
    read_until_settings = experiment_settings.read_until
    read_until_regulator = ReadUntilRegulator(
        read_until_settings,
        sample_rate,
        classifier,
        strata_balancer,
        fragment_collection,
        command_queue
    )
    read_until_regulator.run()

    read_processor_settings = experiment_settings.read_processor
    read_processor = ReadProcessor(
        classifier,
        strata_balancer,
        fragment_collection,
        read_processor_settings
    )
    observer = Observer()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures: dict[str, Future[None]] = {
            "Regulator": executor.submit(read_until_regulator.run_regulation_loop),
            "ReadProcessor": executor.submit(read_processor.process),
            "BasecalledMonitoring": executor.submit(
                start_basecalled_monitoring,
                protocol_service,
                observer,
                read_processor
            )
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

                    clean_threads(
                        command_queue,
                        cmd_processor_thread,
                        observer,
                        read_processor,
                        read_until_regulator,
                        futures
                    )
                    break
        except KeyboardInterrupt:
            clean_threads(
                command_queue,
                cmd_processor_thread,
                observer,
                read_processor,
                read_until_regulator,
                futures
            )

        for future in done:
            try:
                future.result()
            except Exception as e:
                print(repr(e))


if __name__ == "__main__":
    main()
