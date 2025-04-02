from abc import ABC, abstractmethod


class Classifier(ABC):
    @abstractmethod
    def activate_sequence(self, sequence_id: tuple[str, str]) -> None:
        pass

    @abstractmethod
    def is_sequence_present(self, sequence: str) -> bool:
        pass
