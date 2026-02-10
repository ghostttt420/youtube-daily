"""SQLite database for persistent metrics storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class MetricsDatabase:
    """Persistent storage for evolution metrics."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize database connection."""
        settings = get_settings()
        self.db_path = db_path or settings.paths.data_dir / "metrics.db"
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    max_fitness REAL,
                    avg_fitness REAL,
                    min_fitness REAL,
                    std_fitness REAL,
                    species_count INTEGER,
                    survivors INTEGER,
                    theme TEXT,
                    map_seed INTEGER,
                    best_genome_id INTEGER,
                    best_genome_fitness REAL,
                    checkpoint_path TEXT
                );

                CREATE TABLE IF NOT EXISTS species (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER NOT NULL,
                    species_id INTEGER NOT NULL,
                    size INTEGER,
                    fitness_max REAL,
                    fitness_avg REAL,
                    fitness_min REAL,
                    age INTEGER,
                    stagnant INTEGER
                );

                CREATE TABLE IF NOT EXISTS best_laps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    fitness REAL,
                    distance_traveled REAL,
                    gates_passed INTEGER,
                    lap_time_frames INTEGER,
                    trajectory BLOB,  -- JSON serialized list of positions
                    genome_id INTEGER,
                    theme TEXT
                );

                CREATE TABLE IF NOT EXISTS video_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    title TEXT,
                    generation INTEGER,
                    upload_time TEXT,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    ctr REAL,  -- Click-through rate
                    avg_watch_duration REAL,
                    title_template TEXT,
                    theme TEXT
                );

                CREATE TABLE IF NOT EXISTS crashes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER NOT NULL,
                    x REAL,
                    y REAL,
                    cause TEXT,  -- 'wall', 'timeout', 'collision'
                    fitness_at_death REAL,
                    timestamp TEXT
                );

                CREATE TABLE IF NOT EXISTS curriculum (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    difficulty_level INTEGER,
                    track_complexity REAL,
                    target_fitness REAL,
                    achieved_fitness REAL,
                    completed INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_gen_gen ON generations(generation);
                CREATE INDEX IF NOT EXISTS idx_species_gen ON species(generation);
                CREATE INDEX IF NOT EXISTS idx_laps_gen ON best_laps(generation);
            """)
            conn.commit()
        logger.info("metrics_database_initialized", path=str(self.db_path))

    def log_generation(
        self,
        generation: int,
        fitnesses: list[float],
        species_count: int,
        survivors: int,
        theme: str,
        map_seed: int,
        best_genome_id: int | None = None,
        best_genome_fitness: float | None = None,
        checkpoint_path: str | None = None,
    ) -> None:
        """Log generation statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO generations (
                    generation, timestamp, max_fitness, avg_fitness, min_fitness,
                    std_fitness, species_count, survivors, theme, map_seed,
                    best_genome_id, best_genome_fitness, checkpoint_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation,
                    datetime.now().isoformat(),
                    max(fitnesses) if fitnesses else 0,
                    sum(fitnesses) / len(fitnesses) if fitnesses else 0,
                    min(fitnesses) if fitnesses else 0,
                    self._std(fitnesses) if fitnesses else 0,
                    species_count,
                    survivors,
                    theme,
                    map_seed,
                    best_genome_id,
                    best_genome_fitness,
                    checkpoint_path,
                ),
            )
            conn.commit()

    def log_species(
        self,
        generation: int,
        species_data: list[dict[str, Any]],
    ) -> None:
        """Log species statistics."""
        with sqlite3.connect(self.db_path) as conn:
            for spec in species_data:
                conn.execute(
                    """
                    INSERT INTO species (
                        generation, species_id, size, fitness_max, fitness_avg,
                        fitness_min, age, stagnant
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generation,
                        spec["id"],
                        spec["size"],
                        spec["fitness_max"],
                        spec["fitness_avg"],
                        spec["fitness_min"],
                        spec["age"],
                        spec["stagnant"],
                    ),
                )
            conn.commit()

    def log_best_lap(
        self,
        generation: int,
        fitness: float,
        distance_traveled: float,
        gates_passed: int,
        lap_time_frames: int,
        trajectory: list[tuple[float, float]],
        genome_id: int,
        theme: str,
    ) -> None:
        """Log best lap trajectory for replay."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO best_laps (
                    generation, timestamp, fitness, distance_traveled, gates_passed,
                    lap_time_frames, trajectory, genome_id, theme
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation,
                    datetime.now().isoformat(),
                    fitness,
                    distance_traveled,
                    gates_passed,
                    lap_time_frames,
                    json.dumps(trajectory),
                    genome_id,
                    theme,
                ),
            )
            conn.commit()

    def log_crash(
        self,
        generation: int,
        x: float,
        y: float,
        cause: str,
        fitness_at_death: float,
    ) -> None:
        """Log crash location for heatmap analysis."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO crashes (generation, x, y, cause, fitness_at_death, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (generation, x, y, cause, fitness_at_death, datetime.now().isoformat()),
            )
            conn.commit()

    def log_video_performance(
        self,
        title: str,
        generation: int,
        title_template: str,
        theme: str,
        video_id: str | None = None,
    ) -> int:
        """Log video upload with A/B test tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO video_performance (
                    video_id, title, generation, upload_time, title_template, theme
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    title,
                    generation,
                    datetime.now().isoformat(),
                    title_template,
                    theme,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_fitness_history(self, limit: int = 1000) -> list[dict]:
        """Get fitness progression over generations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT generation, max_fitness, avg_fitness, species_count, timestamp
                FROM generations
                ORDER BY generation DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_crash_heatmap(self, generation: int | None = None) -> list[tuple[float, float]]:
        """Get crash locations for heatmap visualization."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT x, y FROM crashes"
            params = ()
            if generation is not None:
                query += " WHERE generation = ?"
                params = (generation,)
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def get_best_lap_trajectory(self, generation: int) -> list[tuple[float, float]] | None:
        """Get trajectory for ghost car replay."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT trajectory FROM best_laps
                WHERE generation = ?
                ORDER BY fitness DESC
                LIMIT 1
                """,
                (generation,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    @staticmethod
    def _std(values: list[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
