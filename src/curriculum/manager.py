"""Curriculum learning with progressive difficulty."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings
from src.metrics.database import MetricsDatabase

logger = structlog.get_logger()


class DifficultyLevel(IntEnum):
    """Progressive difficulty levels."""
    
    WEEK_1_SIMPLE_OVALS = 1      # Learn basic steering
    WEEK_2_CHICANES = 2          # Learn braking
    WEEK_3_HAIRPINS = 3          # Learn drifting
    WEEK_4_COMPLEX = 4           # Full tracks
    WEEK_5_NIGHT_RAIN = 5        # Reduced visibility
    WEEK_6_COMPETITIVE = 6       # Racing against ghosts
    WEEK_7_CHAMPIONSHIP = 7      # Multi-race tournaments
    WEEK_8_MASTERY = 8           # User-designed tracks


@dataclass
class CurriculumConfig:
    """Configuration for a difficulty level."""
    
    level: DifficultyLevel
    name: str
    description: str
    
    # Track complexity
    num_control_points: int
    radius_variance: float  # How much track radius varies
    min_straight_length: int  # Minimum straight sections
    max_curvature: float  # Maximum turn sharpness
    
    # Physics
    friction_base: float
    friction_variance: float  # Random variation
    
    # AI Challenge
    target_fitness: float
    max_time_frames: int
    required_gates: int
    
    # Visual
    visibility: float  # 1.0 = full, <1.0 = fog/night
    sensor_range_multiplier: float
    
    # Success criteria
    generations_to_advance: int
    fitness_threshold: float


# Curriculum definitions
CURRICULUM: dict[DifficultyLevel, CurriculumConfig] = {
    DifficultyLevel.WEEK_1_SIMPLE_OVALS: CurriculumConfig(
        level=DifficultyLevel.WEEK_1_SIMPLE_OVALS,
        name="Simple Ovals",
        description="Learn basic steering on smooth oval tracks",
        num_control_points=8,
        radius_variance=0.1,  # Very consistent radius
        min_straight_length=50,
        max_curvature=0.2,
        friction_base=0.98,
        friction_variance=0.0,
        target_fitness=2000,
        max_time_frames=600,
        required_gates=5,
        visibility=1.0,
        sensor_range_multiplier=1.0,
        generations_to_advance=10,
        fitness_threshold=1500,
    ),
    DifficultyLevel.WEEK_2_CHICANES: CurriculumConfig(
        level=DifficultyLevel.WEEK_2_CHICANES,
        name="Chicanes",
        description="Learn braking and precision through chicanes",
        num_control_points=12,
        radius_variance=0.3,
        min_straight_length=30,
        max_curvature=0.4,
        friction_base=0.97,
        friction_variance=0.01,
        target_fitness=3000,
        max_time_frames=800,
        required_gates=10,
        visibility=1.0,
        sensor_range_multiplier=1.0,
        generations_to_advance=10,
        fitness_threshold=2500,
    ),
    DifficultyLevel.WEEK_3_HAIRPINS: CurriculumConfig(
        level=DifficultyLevel.WEEK_3_HAIRPINS,
        name="Hairpins",
        description="Master tight turns and drifting",
        num_control_points=15,
        radius_variance=0.5,
        min_straight_length=20,
        max_curvature=0.7,
        friction_base=0.95,
        friction_variance=0.02,
        target_fitness=4000,
        max_time_frames=1000,
        required_gates=15,
        visibility=1.0,
        sensor_range_multiplier=0.9,
        generations_to_advance=15,
        fitness_threshold=3500,
    ),
    DifficultyLevel.WEEK_4_COMPLEX: CurriculumConfig(
        level=DifficultyLevel.WEEK_4_COMPLEX,
        name="Complex Circuits",
        description="Full-featured tracks with all elements",
        num_control_points=20,
        radius_variance=0.6,
        min_straight_length=10,
        max_curvature=0.8,
        friction_base=0.97,
        friction_variance=0.03,
        target_fitness=5000,
        max_time_frames=1800,
        required_gates=20,
        visibility=1.0,
        sensor_range_multiplier=1.0,
        generations_to_advance=15,
        fitness_threshold=4500,
    ),
    DifficultyLevel.WEEK_5_NIGHT_RAIN: CurriculumConfig(
        level=DifficultyLevel.WEEK_5_NIGHT_RAIN,
        name="Night & Rain",
        description="Reduced visibility and slippery conditions",
        num_control_points=20,
        radius_variance=0.6,
        min_straight_length=10,
        max_curvature=0.8,
        friction_base=0.92,
        friction_variance=0.05,
        target_fitness=4500,
        max_time_frames=1800,
        required_gates=20,
        visibility=0.6,
        sensor_range_multiplier=0.7,
        generations_to_advance=20,
        fitness_threshold=4000,
    ),
    DifficultyLevel.WEEK_6_COMPETITIVE: CurriculumConfig(
        level=DifficultyLevel.WEEK_6_COMPETITIVE,
        name="Ghost Racing",
        description="Race against previous best",
        num_control_points=20,
        radius_variance=0.6,
        min_straight_length=10,
        max_curvature=0.8,
        friction_base=0.97,
        friction_variance=0.03,
        target_fitness=6000,
        max_time_frames=1800,
        required_gates=20,
        visibility=1.0,
        sensor_range_multiplier=1.0,
        generations_to_advance=20,
        fitness_threshold=5500,
    ),
    DifficultyLevel.WEEK_7_CHAMPIONSHIP: CurriculumConfig(
        level=DifficultyLevel.WEEK_7_CHAMPIONSHIP,
        name="Championship",
        description="Multi-race tournaments",
        num_control_points=20,
        radius_variance=0.7,
        min_straight_length=10,
        max_curvature=0.9,
        friction_base=0.96,
        friction_variance=0.04,
        target_fitness=7000,
        max_time_frames=2000,
        required_gates=25,
        visibility=1.0,
        sensor_range_multiplier=1.0,
        generations_to_advance=25,
        fitness_threshold=6500,
    ),
    DifficultyLevel.WEEK_8_MASTERY: CurriculumConfig(
        level=DifficultyLevel.WEEK_8_MASTERY,
        name="Mastery",
        description="User-designed and extreme tracks",
        num_control_points=25,
        radius_variance=0.8,
        min_straight_length=5,
        max_curvature=1.0,
        friction_base=0.95,
        friction_variance=0.05,
        target_fitness=8000,
        max_time_frames=2400,
        required_gates=30,
        visibility=0.8,
        sensor_range_multiplier=1.0,
        generations_to_advance=50,
        fitness_threshold=7500,
    ),
}


class CurriculumManager:
    """Manages progressive difficulty curriculum."""

    def __init__(self, db: MetricsDatabase | None = None) -> None:
        """Initialize curriculum manager."""
        self.db = db or MetricsDatabase()
        self.settings = get_settings()
        self.current_level = DifficultyLevel.WEEK_1_SIMPLE_OVALS
        self.generations_at_level = 0
        self.best_fitness_at_level = 0.0
        self._load_progress()

    def _load_progress(self) -> None:
        """Load curriculum progress from database."""
        # Get most recent generation to determine current level
        history = self.db.get_fitness_history(limit=100)
        if history:
            # Count how many generations since last level change
            # This is simplified - in production, store level changes explicitly
            self.generations_at_level = len(history) % 10

    def get_current_config(self) -> CurriculumConfig:
        """Get configuration for current difficulty level."""
        return CURRICULUM[self.current_level]

    def should_advance(self, recent_fitnesses: list[float]) -> bool:
        """Check if we should advance to next difficulty level."""
        config = self.get_current_config()
        
        # Check if enough generations at this level
        if self.generations_at_level < config.generations_to_advance:
            return False
        
        # Check if fitness threshold achieved
        if not recent_fitnesses:
            return False
        
        avg_recent = sum(recent_fitnesses[-5:]) / min(5, len(recent_fitnesses))
        return avg_recent >= config.fitness_threshold

    def advance_level(self) -> CurriculumConfig | None:
        """Advance to next difficulty level."""
        if self.current_level >= DifficultyLevel.WEEK_8_MASTERY:
            logger.info("curriculum_at_max_level")
            return None
        
        old_level = self.current_level
        self.current_level = DifficultyLevel(self.current_level + 1)
        self.generations_at_level = 0
        self.best_fitness_at_level = 0.0
        
        logger.info(
            "curriculum_advanced",
            old_level=old_level.name,
            new_level=self.current_level.name,
        )
        
        return self.get_current_config()

    def on_generation_complete(self, fitness: float) -> None:
        """Record generation completion."""
        self.generations_at_level += 1
        self.best_fitness_at_level = max(self.best_fitness_at_level, fitness)

    def get_track_seed(self) -> int:
        """Generate track seed appropriate for current level."""
        import random
        import time
        
        # Seed based on level and time to ensure variety within level
        base_seed = int(time.time() / 86400)  # Changes daily
        level_offset = self.current_level * 10000
        return base_seed + level_offset + random.randint(0, 999)

    def modify_theme_for_difficulty(self, theme_data: dict) -> dict:
        """Adjust theme physics based on current difficulty."""
        config = self.get_current_config()
        
        modified = theme_data.copy()
        modified["physics"] = modified.get("physics", {})
        
        # Override friction
        modified["physics"]["friction"] = config.friction_base
        
        # Add visibility for night/fog
        modified["visibility"] = config.visibility
        modified["sensor_range_multiplier"] = config.sensor_range_multiplier
        
        return modified

    def get_difficulty_name(self) -> str:
        """Get human-readable difficulty name."""
        return self.get_current_config().name

    def get_progress_percent(self) -> float:
        """Get progress through current level (0-100)."""
        config = self.get_current_config()
        return min(100, (self.generations_at_level / config.generations_to_advance) * 100)


# Global instance
_curriculum_manager: CurriculumManager | None = None


def get_curriculum_manager() -> CurriculumManager:
    """Get global curriculum manager."""
    global _curriculum_manager
    if _curriculum_manager is None:
        _curriculum_manager = CurriculumManager()
    return _curriculum_manager
