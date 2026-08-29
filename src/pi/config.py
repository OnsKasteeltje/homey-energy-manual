from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    ems_mode: str = Field(default='SHADOW', alias='EMS_MODE')
    timezone: str = Field(default='Europe/Amsterdam', alias='TZ')
    database_url: str = Field(
        default='postgresql://ems:change-me@postgres:5432/ems', alias='DATABASE_URL'
    )
    mqtt_host: str = Field(default='mosquitto', alias='MQTT_HOST')
    mqtt_port: int = Field(default=1883, alias='MQTT_PORT')
    homey_base_url: str | None = Field(default=None, alias='HOMEY_BASE_URL')
    homey_token: str | None = Field(default=None, alias='HOMEY_TOKEN')
    homey_timeout_s: float = Field(default=5.0, alias='HOMEY_TIMEOUT_S')
    health_port: int = Field(default=9108, alias='HEALTH_PORT')

    @property
    def shadow_only(self) -> bool:
        return self.ems_mode.upper() == 'SHADOW'

    def assert_safe_mode(self) -> None:
        if not self.shadow_only:
            raise RuntimeError('Pi EMS v0.1 is SHADOW-only; LIVE mode is not implemented')
