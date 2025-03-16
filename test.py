import sys
from typing import Optional

import numpy as np
from minknow_api import Connection
from minknow_api.acquisition_pb2 import AcquisitionState
from minknow_api.manager import Manager
# from minknow_api.protocol_pb2 import ProtocolState
# from minknow_api.protocol_pb2 import AnalysisWorkflowInfo
from minknow_api.protocol_service import ProtocolService
from pybasecall_client_lib.pyclient import PyBasecallClient
from watchdog.observers.polling import PollingObserver as Observer

from minFQ.experiment_manager import ExperimentManager, ExperimentManagerBuilder
from minFQ.fastq_handler import FastqHandler


ACQUISITION_ACTIVE_STATES = {
    AcquisitionState.ACQUISITION_RUNNING,
    AcquisitionState.ACQUISITION_STARTING
}


def get_current_protocol(device_name: str) -> Optional[ProtocolService]:
    manager = Manager(host="localhost", port=9501)
    position_connection: Optional[Connection] = None

    for position in manager.flow_cell_positions():
        if position.description.name == device_name:
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


def start_minknow_and_basecalled_monitoring(
    regions_fasta_path: str,
    regions_bed_path: str,
    device_name: str
) -> None:
    exp_manager_builder = ExperimentManagerBuilder(regions_fasta_path)

    # NOTE: refactor into a separate function
    with open(regions_bed_path) as fh:
        for line in fh:
            chrom, start, end, name, score, strand = line.strip().split()
            if strand not in ["+", "-"]:
                raise ValueError("Strand cannot be unknown.")

            exp_manager_builder.add_target_region((chrom,
                                                   int(start),
                                                   int(end),
                                                   name,
                                                   int(score) if score.isdigit() else None,
                                                   strand == "-"))

    exp_manager: ExperimentManager = (exp_manager_builder
                                        .set_protocol(get_current_protocol(device_name))
                                        .get_result())

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
        print("Exiting - Will take a few seconds to close threads.")
        sys.exit(0)


def analysis(client):
    while client.is_running:
        for channel, read in client.get_read_chunks():
            raw_data = np.fromstring(read.raw_data, client.signal_dtype)


def main():
    client = PyBasecallClient(
        "127.0.0.1:5555",
        "dna_r9.4.1_450bps_fast",
    )
    client.connect()

    start_minknow_and_basecalled_monitoring("MN34986")


if __name__ == "__main__":
    main()
