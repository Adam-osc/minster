from queue import Queue
from typing import Optional


class Printer:
    def __init__(self, message_queue: Queue[Optional[str]]):
        self._message_queue: Queue[Optional[str]] = message_queue

    def process(self) -> None:
        while True:
            message = self._message_queue.get()
            if message is None:
                break
            print(message)
