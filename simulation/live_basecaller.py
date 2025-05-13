import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from pybasecall_client_lib.helper_functions import basecall_with_pybasecall_client
from pybasecall_client_lib.pyclient import PyBasecallClient
from watchdog.events import FileSystemEventHandler, DirCreatedEvent, FileCreatedEvent
from watchdog.observers import Observer

WATCH_DIR = "/path/to/current/icarust/simulation/directory"
FASTQ_PASS_DIR = WATCH_DIR + "/fastq_pass"
PROCESSED_DIR = WATCH_DIR + "/processed"
Path(FASTQ_PASS_DIR).mkdir(exist_ok=True)
Path(PROCESSED_DIR).mkdir(exist_ok=True)

ADDRESS = "ipc:///tmp/.guppy/5555"
CONFIG = "dna_r10.4.1_e8.2_400bps_5khz_fast"


class Pod5Handler(FileSystemEventHandler):
    @staticmethod
    def generate_iso_start_time() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def write_custom_fastq(reads: list[dict], output_path: str) -> None:
        with open(output_path, "w") as f:
            for read in reads:
                meta = read["metadata"]
                data = read["datasets"]

                header = (
                    f"@{meta['read_id']} "
                    f"runid={meta['run_id']} "
                    f"channel={meta['channel']} "
                    f"start_time={Pod5Handler.generate_iso_start_time()}"
                )

                sequence = data["sequence"]
                quality = data["qstring"]

                f.write(f"{header}\n{sequence}\n+\n{quality}\n")

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if event.is_directory:
            return
        if not Path(event.src_path).parent.stem == "fast5_pass" or not event.src_path.endswith(".pod5"):
            return

        while True:
            initial_size = os.path.getsize(event.src_path)
            time.sleep(5)
            new_size = os.path.getsize(event.src_path)

            if initial_size == new_size:
                break

        dorado_client: PyBasecallClient = PyBasecallClient(
            address=ADDRESS,
            config=CONFIG
        )
        dorado_client.connect()

        output_path = FASTQ_PASS_DIR + "/" + (Path(event.src_path).stem + ".fastq")
        try:
            print(f"Trying to call {event.src_path}")
            called_reads = basecall_with_pybasecall_client(
                client=dorado_client,
                input_path=str(Path(event.src_path).parent)
            )
            print("Finished calling")
            Pod5Handler.write_custom_fastq(called_reads, output_path)
        except Exception as e:
            print(repr(e))

        shutil.move(event.src_path, PROCESSED_DIR + "/" + Path(event.src_path).name)
        dorado_client.disconnect()


if __name__ == "__main__":
    observer = Observer()
    observer.schedule(Pod5Handler(), path=WATCH_DIR, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()
