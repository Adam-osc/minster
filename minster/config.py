from pathlib import Path
from typing import Annotated, ClassVar, Optional

from pydantic import BaseModel, model_validator, AnyUrl, confloat, conint, constr, PositiveInt, NonNegativeInt
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource

UnitFloat = Annotated[float, confloat(gt=0, lt=1)]
UnprivPortInt = Annotated[int, conint(ge=1024, le=65535)]
HostName = Annotated[str, constr(max_length=253, pattern=r'^([a-z0-9-]+(\.[a-z0-9-]+)*)$')]


class BasecallerSettings(BaseModel):
    config: str
    address: AnyUrl = "ipc:///tmp/.guppy/5555"
    max_attempts: PositiveInt = 3

class IBFSettings(BaseModel):
    fragment_length: PositiveInt
    w: PositiveInt
    k: PositiveInt
    hashes: PositiveInt = 3
    num_of_bins: PositiveInt
    fp_rate: UnitFloat
    preserved_pct: UnitFloat

class MappySettings(BaseModel):
    pass

class ClassifierSettings(BaseModel):
    mappy: Optional[MappySettings] = None
    interleaved_bloom_filter: Optional[IBFSettings] = None

    @model_validator(mode='after')
    def check_only_one_classifier(self) -> 'ClassifierSettings':
        all_classifiers: list[Optional[BaseModel]] = [
            self.mappy,
            self.interleaved_bloom_filter
        ]

        if sum(1 for c in all_classifiers if c is not None) > 1:
            raise ValueError("Only one classifier can be specified.")
        return self

class ReadUntilSettings(BaseModel):
    host: HostName = "127.0.0.1"
    port: UnprivPortInt = 8000
    basecaller: BasecallerSettings
    classifier: ClassifierSettings
    depletion_chunks: PositiveInt = 4
    throttle: UnitFloat = 0.1

class SequencerSettings(BaseModel):
    name: str
    host: HostName = "localhost"
    port: UnprivPortInt = 9501

class ReferenceSequence(BaseModel):
    path: Path
    expected_ratio: PositiveInt

class ReadProcessorSettings(BaseModel):
    batch_size: PositiveInt
    read_processor: PositiveInt

class ExperimentSettings(BaseSettings):
    metrics_store: Path
    minimum_reads_for_parameter_estimation: Annotated[int, confloat(gt=1)]
    minimum_fragments_for_ratio_estimation: PositiveInt
    minimum_mapped_bases: PositiveInt
    thinning_accelerator: NonNegativeInt

    read_processor: ReadProcessorSettings
    reference_sequences: list[ReferenceSequence]

    sequencer: SequencerSettings
    read_until: ReadUntilSettings

    _is_toml_set: ClassVar[bool] = False
    _toml_file: ClassVar[Path]

    @classmethod
    def set_toml_file(cls, toml_file: Path) -> None:
        if not cls._is_toml_set:
            cls._toml_file = toml_file
            cls._is_toml_set = True
        else:
            raise AttributeError(f"Toml file is already set to {cls._toml_file}")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls, toml_file=cls._toml_file),)
