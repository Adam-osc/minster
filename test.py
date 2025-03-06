import sys, logging

from minFQ.fastq_handler import FastqHandler
from minFQ.my_types import ExperimentManager, ExperimentManagerBuilder

from watchdog.observers.polling import PollingObserver as Observer

from minknow_api import Connection
from minknow_api.manager import Manager
from minknow_api.protocol_pb2 import ProtocolState
from minknow_api.protocol_pb2 import AnalysisWorkflowInfo
from minknow_api.protocol_service import ProtocolService

from typing import Optional

logging.basicConfig(
    format="%(asctime)s %(module)s:%(levelname)s:%(thread)d:%(message)s",
    filename="minFQ.log",
    filemode="w",
    level=logging.INFO,
)

log = logging.getLogger()
log.setLevel(logging.DEBUG)


def get_current_protocol(device_name: str) -> Optional[ProtocolService]:
    manager = Manager(host="localhost", port=9501)
    position_connection: Optional[Connection] = None

    for position in manager.flow_cell_positions():
        if position.description.name == device_name:
            position_connection = position.connect()
            break

    if position_connection is None:
        return None

    if position_connection.protocol.get_run_info().state == AnalysisWorkflowInfo.Status.RUNNING:
        return position_connection.protocol

    for activity in position_connection.instance.stream_instance_activity():
        if (len(activity.protocol_run_info.ListFields()) > 0 and
                activity.protocol_run_info.state in [
                    ProtocolState.PROTOCOL_RUNNING,
                    ProtocolState.PROTOCOL_WAITING_FOR_TEMPERATURE,
                    ProtocolState.PROTOCOL_WAITING_FOR_ACQUISITION
            ]):
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


def main():
    start_minknow_and_basecalled_monitoring("MN34986")


if __name__ == "__main__":
    main()
