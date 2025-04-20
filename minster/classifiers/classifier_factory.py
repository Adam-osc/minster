import mappy as mp

from classifier import Classifier
from ibf_wrapper import IBFWrapper
from mappy_wrapper import MappyWrapper
from minster.config import ClassifierSettings


class ClassifierFactory:
    def __init__(self, aligners: dict[str, mp.Aligner], reference_files: list[str],
    ) -> None:
        self._aligners: dict[str, mp.Aligner] = aligners
        self._reference_files: list[str] = reference_files

    def create(self, cfg: ClassifierSettings) -> Classifier:
        if cfg.mappy is not None:
            return MappyWrapper(self._aligners)

        if cfg.interleaved_bloom_filter is not None:
            return IBFWrapper(
                cfg.interleaved_bloom_filter,
                self._reference_files,
            )

        raise ValueError("No valid classifier configuration passed")
