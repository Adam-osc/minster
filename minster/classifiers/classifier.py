from abc import ABC, abstractmethod
from typing import Optional


class Classifier(ABC):
    @abstractmethod
    def activate_sequences(self, container_id: str) -> None:
        pass

    @abstractmethod
    def deactivate_sequences(self, container_id: str) -> None:
        pass

    @abstractmethod
    def is_sequence_present(self, sequence: str) -> Optional[str]:
        pass
