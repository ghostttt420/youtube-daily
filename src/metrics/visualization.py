"""Metrics visualization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from src.metrics.database import MetricsDatabase

logger = structlog.get_logger()


class MetricsVisualizer:
    """Visualizes evolution metrics."""

    def __init__(self, db: MetricsDatabase | None = None) -> None:
        """Initialize visualizer."""
        self.db = db or MetricsDatabase()

    def generate_fitness_chart(self, output_path: Path | None = None) -> Path:
        """Generate fitness over time chart."""
        history = self.db.get_fitness_history(limit=100)
        
        if not history:
            logger.warning("no_data_for_chart")
            return Path("chart.png")
        
        # Simple text-based chart for now
        # Could be extended to use matplotlib
        lines = ["Fitness Progression", "=" * 40]
        
        for row in history[:20]:
            gen = row["generation"]
            max_fit = row["max_fitness"]
            bar_len = int(max_fit / 100)
            bar = "█" * min(bar_len, 30)
            lines.append(f"Gen {gen:4d}: {bar} {max_fit:.0f}")
        
        output = output_path or Path("fitness_chart.txt")
        with open(output, "w") as f:
            f.write("\n".join(lines))
        
        return output

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        history = self.db.get_fitness_history(limit=1000)
        
        if not history:
            return {"generations": 0, "best_fitness": 0}
        
        return {
            "generations": len(history),
            "best_fitness": max(r["max_fitness"] for r in history),
            "avg_fitness": sum(r["avg_fitness"] for r in history) / len(history),
        }
