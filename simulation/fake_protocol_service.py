from dataclasses import dataclass


@dataclass
class FakeMessageWrapper:
    _output_path: str

    @property
    def output_path(self) -> str:
        return self._output_path

class FakeProtocolService:
    def __init__(self, output_path: str):
        self._output_path: str = output_path

    def get_run_info(self) -> FakeMessageWrapper:
        return FakeMessageWrapper(self._output_path)