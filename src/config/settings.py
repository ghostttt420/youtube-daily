"""Application settings with validation."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class YouTubeConfig(BaseSettings):
    """YouTube API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="YT_",
        extra="ignore",
    )

    client_id: str = Field(..., description="YouTube OAuth client ID")
    client_secret: str = Field(..., description="YouTube OAuth client secret")
    refresh_token: str = Field(..., description="YouTube OAuth refresh token")


class SimulationConfig(BaseSettings):
    """Simulation physics and timing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SIM_",
        extra="ignore",
    )

    fps: int = Field(default=30, ge=1, le=120, description="Simulation frame rate")
    width: int = Field(default=1080, ge=480, description="Viewport width in pixels")
    height: int = Field(default=1920, ge=640, description="Viewport height in pixels")
    world_size: int = Field(default=4000, ge=1000, description="World size in pixels")
    sensor_length: int = Field(default=300, ge=100, description="Sensor ray length")
    max_frames_training: int = Field(
        default=450, ge=100, description="Max frames for training clips (15s at 30fps)"
    )
    max_frames_pro: int = Field(
        default=1800, ge=300, description="Max frames for final render (60s at 30fps)"
    )


class NEATConfig(BaseSettings):
    """NEAT algorithm configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NEAT_",
        extra="ignore",
    )

    population_size: int = Field(default=40, ge=10, le=200)
    daily_generations: int = Field(default=50, ge=1, le=500)
    checkpoint_interval: int = Field(default=5, ge=1, le=20)
    config_path: Path = Field(default=Path("config.txt"))


class PathsConfig(BaseSettings):
    """File path configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PATH_",
        extra="ignore",
    )

    assets_dir: Path = Field(default=Path("assets"))
    data_dir: Path = Field(default=Path("data"))
    checkpoints_dir: Path = Field(default=Path("data/checkpoints"))
    clips_dir: Path = Field(default=Path("training_clips"))
    theme_file: Path = Field(default=Path("theme.json"))

    @field_validator("assets_dir", "data_dir", "checkpoints_dir", "clips_dir", mode="after")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Ensure directories exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class Settings(BaseSettings):
    """Global application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: Literal["development", "staging", "production"] = Field(
        default="development", description="Runtime environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # Sub-configs
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    neat: NEATConfig = Field(default_factory=NEATConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # Feature flags
    enable_youtube_upload: bool = Field(default=True)
    enable_video_render: bool = Field(default=True)
    enable_sound: bool = Field(default=False)

    @field_validator("youtube", mode="before")
    @classmethod
    def validate_youtube(cls, v: YouTubeConfig) -> YouTubeConfig:
        """Validate YouTube credentials are present if upload is enabled."""
        if isinstance(v, dict):
            v = YouTubeConfig(**v)
        return v


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
