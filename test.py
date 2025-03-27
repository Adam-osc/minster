import argparse
import concurrent.futures
import sys
from pathlib import Path
from typing import Optional

from minknow_api import Connection
from minknow_api.acquisition_pb2 import AcquisitionState
from minknow_api.manager import Manager
from minknow_api.protocol_service import ProtocolService
from watchdog.observers.polling import PollingObserver as Observer

from minFQ.config import ExperimentSettings, SequencerSettings
from minFQ.experiment_manager import ExperimentManager
from minFQ.fastq_handler import FastqHandler
from minFQ.read_until_analysis import IBFWrapper, ReadUntilAnalysis
from minFQ.run_data_tracker import ReadQueue

ACQUISITION_ACTIVE_STATES = {
    AcquisitionState.ACQUISITION_RUNNING,
    AcquisitionState.ACQUISITION_STARTING
}


def get_current_protocol(sequencer_settings: SequencerSettings) -> Optional[ProtocolService]:
    manager = Manager(host=sequencer_settings.host, port=sequencer_settings.port)
    position_connection: Optional[Connection] = None

    for position in manager.flow_cell_positions():
        if position.description.name == sequencer_settings.name:
            position_connection = position.connect()
            break
    if position_connection is None:
        return None
    if position_connection.acquisition.get_acquisition_info().state in ACQUISITION_ACTIVE_STATES :
        return position_connection.protocol

    for acquisition_status in position_connection.acquisition.watch_current_acquisition_run():
        if acquisition_status.state in ACQUISITION_ACTIVE_STATES:
            return position_connection.protocol

    return None


def start_basecalled_monitoring(
        protocol_service: ProtocolService,
        read_queue: ReadQueue
) -> None:
    exp_manager = ExperimentManager(protocol_service, read_queue)
    event_handler = FastqHandler(exp_manager)

    observer = Observer()
    observer.schedule(event_handler,
                      path=exp_manager.get_watch_dir(),
                      recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            observer.join()
    except (KeyboardInterrupt, Exception) as e:
        observer.stop()
        observer.join()
        print(repr(e))
        sys.exit(0)


def main():
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

    maybe_protocol_service = get_current_protocol(experiment_settings.sequencer)
    if maybe_protocol_service is None:
        print("Could not acquire the running protocol.")
        sys.exit(1)
    protocol_service: ProtocolService = maybe_protocol_service

    read_until_settings = experiment_settings.read_until
    depletion_ibf = IBFWrapper(read_until_settings.interleaved_bloom_filter,
                               experiment_settings.reference_sequences)
    read_until_analysis = ReadUntilAnalysis(read_until_settings, depletion_ibf)
    read_queue = ReadQueue(experiment_settings.reference_sequences, depletion_ibf)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_analysis = executor.submit(read_until_analysis.analysis)
        future_queue_worker = executor.submit(read_queue.process)
        future_monitoring = executor.submit(start_basecalled_monitoring, protocol_service, read_queue)

        done, not_done = concurrent.futures.wait(
            [future_analysis, future_queue_worker, future_monitoring],
            timeout=0
        )
        try:
            while len(not_done) == 3:
                freshly_done, not_done = concurrent.futures.wait(not_done, timeout=1)
                done |= freshly_done
        except KeyboardInterrupt:
            for future in not_done:
                future.cancel()
            _ = concurrent.futures.wait(not_done, timeout=None)

        for future in done:
            try:
                future.result()
            except Exception as e:
                print(repr(e))
                sys.exit(1)


if __name__ == "__main__":
    main()
