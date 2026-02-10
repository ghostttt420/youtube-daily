"""A/B testing tracker for video optimization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings
from src.metrics.database import MetricsDatabase

logger = structlog.get_logger()


class TitleVariant(Enum):
    """Predefined title variants for A/B testing."""
    HOOK_CHAOS = "hook_chaos"
    HOOK_IMPROVEMENT = "hook_improvement"
    HOOK_SATISFYING = "hook_satisfying"
    HOOK_SCARY = "hook_scary"
    HOOK_NOOB_TO_PRO = "hook_noob_to_pro"


@dataclass
class TitleTemplate:
    """A title template with variant info."""
    variant: TitleVariant
    template: str
    emoji_intensity: int  # 0-3
    urgency_level: int  # 0-3


# Title variants for testing
TITLE_VARIANTS: dict[TitleVariant, TitleTemplate] = {
    TitleVariant.HOOK_CHAOS: TitleTemplate(
        variant=TitleVariant.HOOK_CHAOS,
        template="AI Driving Goes COMPLETELY WRONG... 💀 (Gen {gen})",
        emoji_intensity=2,
        urgency_level=2,
    ),
    TitleVariant.HOOK_IMPROVEMENT: TitleTemplate(
        variant=TitleVariant.HOOK_IMPROVEMENT,
        template="Watch AI Learn to Drive in {gen} Gens 🧠🚗",
        emoji_intensity=2,
        urgency_level=1,
    ),
    TitleVariant.HOOK_SATISFYING: TitleTemplate(
        variant=TitleVariant.HOOK_SATISFYING,
        template="Satisfying AI Driving Lines... Gen {gen} is CLEAN 🤤",
        emoji_intensity=1,
        urgency_level=1,
    ),
    TitleVariant.HOOK_SCARY: TitleTemplate(
        variant=TitleVariant.HOOK_SCARY,
        template="This AI Driver is Getting SCARY Good... Gen {gen} 😰",
        emoji_intensity=1,
        urgency_level=3,
    ),
    TitleVariant.HOOK_NOOB_TO_PRO: TitleTemplate(
        variant=TitleVariant.HOOK_NOOB_TO_PRO,
        template="AI Goes from NOOB to PRO in {gen} Generations 🔥",
        emoji_intensity=1,
        urgency_level=2,
    ),
}


class ABTestTracker:
    """Tracks A/B test performance for video optimization."""

    def __init__(self, db: MetricsDatabase | None = None) -> None:
        """Initialize A/B test tracker."""
        self.db = db or MetricsDatabase()
        self.settings = get_settings()
        self._load_performance_data()

    def _load_performance_data(self) -> None:
        """Load historical performance data."""
        # Get recent video performance
        history = self.db.get_fitness_history(limit=50)
        
        # Calculate which variants perform best
        self.variant_performance: dict[TitleVariant, float] = {
            v: 0.0 for v in TitleVariant
        }

    def select_title(self, generation: int, force_variant: TitleVariant | None = None) -> tuple[str, TitleVariant]:
        """Select optimal title based on A/B testing data."""
        
        if force_variant:
            variant = force_variant
        else:
            # 80% exploitation (best performer), 20% exploration (random)
            import random
            
            if random.random() < 0.2:
                # Exploration: try random variant
                variant = random.choice(list(TitleVariant))
                logger.info("ab_test_exploration", variant=variant.value)
            else:
                # Exploitation: use best performer
                variant = self._get_best_variant()
                logger.info("ab_test_exploitation", variant=variant.value)
        
        template = TITLE_VARIANTS[variant]
        title = template.template.format(gen=generation)
        
        return title, variant

    def _get_best_variant(self) -> TitleVariant:
        """Get best performing variant based on historical data."""
        if not self.variant_performance:
            return TitleVariant.HOOK_NOOB_TO_PRO
        
        return max(self.variant_performance, key=self.variant_performance.get)

    def track_upload(
        self,
        video_id: str,
        title: str,
        variant: TitleVariant,
        generation: int,
    ) -> int:
        """Track video upload for A/B testing."""
        # Store in database
        row_id = self.db.log_video_performance(
            title=title,
            generation=generation,
            title_template=variant.value,
            theme="unknown",
            video_id=video_id,
        )
        
        logger.info(
            "ab_test_upload_tracked",
            video_id=video_id,
            variant=variant.value,
            title=title[:50],
        )
        
        return row_id

    def update_metrics(self, video_id: str, views: int, likes: int, ctr: float) -> None:
        """Update video metrics (called periodically via API)."""
        # This would be called by a separate job that polls YouTube API
        pass

    def get_report(self) -> dict[str, Any]:
        """Generate A/B test performance report."""
        return {
            "variant_performance": {
                v.value: score for v, score in self.variant_performance.items()
            },
            "best_variant": self._get_best_variant().value,
            "total_tests": sum(1 for v in self.variant_performance if v),
        }

    def get_title_suggestions(self, generation: int, count: int = 3) -> list[tuple[str, TitleVariant]]:
        """Get multiple title suggestions for manual selection."""
        import random
        
        variants = list(TitleVariant)
        random.shuffle(variants)
        
        return [
            (TITLE_VARIANTS[v].template.format(gen=generation), v)
            for v in variants[:count]
        ]
