from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, AnyUrl, confloat, conint, constr, PositiveInt
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

UnitFloat = confloat(gt=0, lt=1)
UnprivPortInt = conint(ge=1024, le=65535)
HostName = constr(max_length=253, pattern=r'^([a-z0-9-]+(\.[a-z0-9-]+)*)$')


class BasecallerSettings(BaseModel):
    config: str
    address: AnyUrl = "ipc:///tmp/.guppy/5555"
    max_attempts: PositiveInt = 3

class IBFSettings(BaseModel):
    fragment_length: PositiveInt
    k: PositiveInt
    error_rate: UnitFloat
    hashes: PositiveInt = 3
    confidence: UnitFloat = 0.95

class ReadUntilSettings(BaseModel):
    host: HostName = "127.0.0.1"
    port: UnprivPortInt = 8000
    basecaller: BasecallerSettings
    interleaved_bloom_filter: IBFSettings
    depletion_chunks: PositiveInt = 4
    throttle: UnitFloat = 0.1

class SequencerSettings(BaseModel):
    name: str
    host: HostName = "localhost"
    port: UnprivPortInt = 9501

class ExperimentSettings(BaseSettings):
    reference_sequences: list[Path]
    sequencer: SequencerSettings
    read_until: ReadUntilSettings
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict()

    _is_toml_set: ClassVar[bool] = False
    _toml_file: ClassVar[Path] = Path("./minster.toml")

    @classmethod
    def set_toml_file(cls, toml_file: Path):
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
