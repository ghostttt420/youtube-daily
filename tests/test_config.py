"""Tests for configuration management."""

import os
from pathlib import Path

import pytest

from src.config import themes
from src.config.settings import (
    NEATConfig,
    PathsConfig,
    Settings,
    SimulationConfig,
    YouTubeConfig,
    get_settings,
    reset_settings,
)


class TestYouTubeConfig:
    """Test YouTube configuration."""

    def test_required_fields(self, monkeypatch):
        """Test that required fields raise error when missing."""
        monkeypatch.delenv("YT_CLIENT_ID", raising=False)
        monkeypatch.delenv("YT_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("YT_REFRESH_TOKEN", raising=False)
        
        with pytest.raises(Exception):  # pydantic.ValidationError
            YouTubeConfig()

    def test_valid_config(self, monkeypatch):
        """Test valid configuration loads correctly."""
        monkeypatch.setenv("YT_CLIENT_ID", "test_id")
        monkeypatch.setenv("YT_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "test_token")
        
        config = YouTubeConfig()
        assert config.client_id == "test_id"
        assert config.client_secret == "test_secret"
        assert config.refresh_token == "test_token"


class TestSimulationConfig:
    """Test simulation configuration."""

    def test_defaults(self):
        """Test default values."""
        config = SimulationConfig()
        assert config.fps == 30
        assert config.width == 1080
        assert config.height == 1920

    def test_validation(self):
        """Test value validation."""
        with pytest.raises(Exception):
            SimulationConfig(fps=0)  # Must be >= 1
        
        with pytest.raises(Exception):
            SimulationConfig(fps=200)  # Must be <= 120


class TestNEATConfig:
    """Test NEAT configuration."""

    def test_defaults(self):
        """Test default values."""
        config = NEATConfig()
        assert config.population_size == 40
        assert config.daily_generations == 50


class TestPathsConfig:
    """Test paths configuration."""

    def test_directories_created(self, tmp_path):
        """Test that directories are created."""
        config = PathsConfig(
            assets_dir=tmp_path / "assets",
            data_dir=tmp_path / "data",
            checkpoints_dir=tmp_path / "checkpoints",
            clips_dir=tmp_path / "clips",
        )
        
        assert config.assets_dir.exists()
        assert config.data_dir.exists()
        assert config.checkpoints_dir.exists()
        assert config.clips_dir.exists()


class TestSettings:
    """Test global settings."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def test_singleton(self):
        """Test that get_settings returns same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestThemes:
    """Test theme system."""

    def test_theme_keys(self):
        """Test all theme keys are valid."""
        expected_keys = [
            "CIRCUIT", "ICE", "DESERT", "CYBER",
            "TOXIC", "LAVA", "RETRO", "JUNGLE", "MIDNIGHT",
        ]
        assert set(themes.THEMES.keys()) == set(expected_keys)

    def test_theme_structure(self):
        """Test theme has required fields."""
        for key, theme in themes.THEMES.items():
            assert "name" in theme
            assert "friction" in theme
            assert "colors" in theme
            assert "title" in theme
            assert "tags" in theme
            
            # Check colors
            colors = theme["colors"]
            assert hasattr(colors, "bg")
            assert hasattr(colors, "road")
            assert hasattr(colors, "wall")
            assert hasattr(colors, "center")

    def test_generate_daily_theme(self):
        """Test theme generation."""
        theme = themes.get_daily_theme()
        assert theme.key in themes.THEMES
        assert 0 <= theme.map_seed <= 999_999
        assert theme.friction > 0

    def test_theme_serialization(self, tmp_path):
        """Test theme can be saved and loaded."""
        theme = themes.get_daily_theme()
        path = tmp_path / "theme.json"
        
        themes.save_theme(theme, path)
        assert path.exists()
        
        loaded = themes.load_theme(path)
        assert loaded is not None
        assert loaded.key == theme.key
        assert loaded.map_seed == theme.map_seed

    def test_load_missing_theme(self, tmp_path):
        """Test loading non-existent theme returns None."""
        path = tmp_path / "nonexistent.json"
        result = themes.load_theme(path)
        assert result is None
