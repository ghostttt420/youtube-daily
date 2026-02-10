"""Feature flags system for enabling/disabling features."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


@dataclass
class FeatureFlags:
    """Feature flag configuration."""
    
    # Core features
    enable_curriculum: bool = True
    enable_weather: bool = True
    enable_ghost_cars: bool = True
    enable_tournament_mode: bool = True
    enable_multi_objective: bool = True
    
    # Visual features
    enable_telemetry_overlay: bool = True
    enable_neural_visualization: bool = True
    enable_crash_heatmap: bool = True
    
    # Data/Analytics
    enable_wandb: bool = False
    enable_detailed_metrics: bool = True
    enable_ab_testing: bool = True
    
    # Racing modes
    enable_qualifying: bool = True
    enable_race_mode: bool = False  # Full race mode (slower)
    
    # Recovery
    enable_error_recovery: bool = True
    enable_emergency_checkpoints: bool = True
    
    # Cloud
    enable_cloud_storage: bool = False
    enable_community_voting: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enable_curriculum": self.enable_curriculum,
            "enable_weather": self.enable_weather,
            "enable_ghost_cars": self.enable_ghost_cars,
            "enable_tournament_mode": self.enable_tournament_mode,
            "enable_multi_objective": self.enable_multi_objective,
            "enable_telemetry_overlay": self.enable_telemetry_overlay,
            "enable_neural_visualization": self.enable_neural_visualization,
            "enable_crash_heatmap": self.enable_crash_heatmap,
            "enable_wandb": self.enable_wandb,
            "enable_detailed_metrics": self.enable_detailed_metrics,
            "enable_ab_testing": self.enable_ab_testing,
            "enable_qualifying": self.enable_qualifying,
            "enable_race_mode": self.enable_race_mode,
            "enable_error_recovery": self.enable_error_recovery,
            "enable_emergency_checkpoints": self.enable_emergency_checkpoints,
            "enable_cloud_storage": self.enable_cloud_storage,
            "enable_community_voting": self.enable_community_voting,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureFlags":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
    
    def get(self, flag_name: str, default: bool = False) -> bool:
        """Get flag value by name."""
        return getattr(self, flag_name, default)
    
    def set(self, flag_name: str, value: bool) -> None:
        """Set flag value by name."""
        if hasattr(self, flag_name):
            setattr(self, flag_name, value)
            logger.info("feature_flag_changed", flag=flag_name, value=value)
        else:
            logger.warning("unknown_feature_flag", flag=flag_name)


class FeatureFlagManager:
    """Manages feature flags from file and environment."""

    def __init__(self) -> None:
        """Initialize feature flag manager."""
        self.settings = get_settings()
        self.flags = FeatureFlags()
        self.config_path = Path("feature_flags.json")
        self._load_flags()
        self._apply_env_overrides()

    def _load_flags(self) -> None:
        """Load flags from config file."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                self.flags = FeatureFlags.from_dict(data)
                logger.info("feature_flags_loaded", path=str(self.config_path))
            except Exception as e:
                logger.warning("feature_flags_load_failed", error=str(e))

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        prefix = "FEATURE_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                flag_name = f"enable_{key[len(prefix):].lower()}"
                if hasattr(self.flags, flag_name):
                    bool_value = value.lower() in ("true", "1", "yes", "on")
                    self.flags.set(flag_name, bool_value)
                    logger.info("feature_flag_from_env", flag=flag_name, value=bool_value)

    def save(self) -> None:
        """Save current flags to file."""
        with open(self.config_path, "w") as f:
            json.dump(self.flags.to_dict(), f, indent=2)
        logger.info("feature_flags_saved")

    def get_flags(self) -> FeatureFlags:
        """Get current feature flags."""
        return self.flags


# Global instance
_flag_manager: FeatureFlagManager | None = None


def get_feature_flags() -> FeatureFlags:
    """Get global feature flags."""
    global _flag_manager
    if _flag_manager is None:
        _flag_manager = FeatureFlagManager()
    return _flag_manager.get_flags()
