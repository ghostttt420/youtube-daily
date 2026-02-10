"""Racing modes: qualifying and championship races."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.simulation.car import Car

logger = structlog.get_logger()


class RaceType(Enum):
    """Types of races."""
    QUALIFYING = auto()  # Time trial, all cars run
    RACE = auto()        # Position-based, limited field
    CHAMPIONSHIP = auto()  # Multi-race series


@dataclass
class RaceResult:
    """Result of a single race."""
    car_id: int
    genome_id: int
    position: int
    lap_time: float
    best_lap: float
    gates_passed: int
    finished: bool
    points: int = 0


@dataclass
class RaceConfig:
    """Configuration for a race."""
    race_type: RaceType
    max_cars: int = 40
    qualifying_spots: int = 8
    laps: int = 1
    max_time_frames: int = 1800


class RaceMode:
    """Base class for racing modes."""

    def __init__(self, config: RaceConfig) -> None:
        """Initialize race mode."""
        self.config = config
        self.results: list[RaceResult] = []
        self.running = False

    def setup(self, cars: list[Car], genomes: list[Any]) -> list[tuple[Car, Any]]:
        """Setup race with given cars."""
        raise NotImplementedError

    def on_car_finish(self, car: Car, genome_id: int, lap_time: float) -> None:
        """Record car finish."""
        raise NotImplementedError

    def get_final_positions(self) -> list[RaceResult]:
        """Get final race positions."""
        return sorted(self.results, key=lambda r: (not r.finished, r.position))

    def calculate_fitness(self, result: RaceResult) -> float:
        """Calculate fitness from race result."""
        raise NotImplementedError


class QualifyingMode(RaceMode):
    """Qualifying: all cars get a chance, best advance."""

    def __init__(self) -> None:
        """Initialize qualifying mode."""
        super().__init__(RaceConfig(
            race_type=RaceType.QUALIFYING,
            max_cars=40,
            qualifying_spots=8,
            laps=1,
            max_time_frames=1800,
        ))
        self.finish_order: list[tuple[int, float]] = []  # (genome_id, lap_time)

    def setup(self, cars: list[Car], genomes: list[Any]) -> list[tuple[Car, Any]]:
        """All cars participate in qualifying."""
        self.running = True
        self.finish_order = []
        return list(zip(cars, genomes))

    def on_car_finish(self, car: Car, genome_id: int, lap_time: float) -> None:
        """Record qualifying time."""
        self.finish_order.append((genome_id, lap_time))

    def get_qualified(self) -> list[int]:
        """Get IDs of cars that qualified."""
        sorted_results = sorted(self.finish_order, key=lambda x: x[1])
        return [gid for gid, _ in sorted_results[:self.config.qualifying_spots]]

    def calculate_fitness(self, result: RaceResult) -> float:
        """Fitness based on qualifying position."""
        if not result.finished:
            return 0.0
        
        # Base fitness for completing lap
        fitness = 1000.0
        
        # Bonus for faster times
        if result.best_lap > 0:
            fitness += max(0, 2000 - result.best_lap)  # Faster = more points
        
        # Position bonus
        position_bonus = max(0, (self.config.qualifying_spots - result.position) * 500)
        fitness += position_bonus
        
        return fitness


class TournamentMode(RaceMode):
    """Championship race with points system."""

    POINTS_SYSTEM = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]  # F1-style

    def __init__(self, num_cars: int = 8, laps: int = 3) -> None:
        """Initialize tournament mode."""
        super().__init__(RaceConfig(
            race_type=RaceType.CHAMPIONSHIP,
            max_cars=num_cars,
            qualifying_spots=num_cars,
            laps=laps,
            max_time_frames=3000,
        ))
        self.lap_counts: dict[int, int] = {}  # genome_id -> laps completed
        self.positions: dict[int, int] = {}  # genome_id -> current position
        self.race_start_time: float = 0

    def setup(self, cars: list[Car], genomes: list[Any]) -> list[tuple[Car, Any]]:
        """Only qualified cars race."""
        self.running = True
        self.lap_counts = {}
        self.positions = {}
        self.results = []
        
        # Limit to max_cars
        participants = list(zip(cars, genomes))[:self.config.max_cars]
        
        # Initialize lap counts
        for _, genome in participants:
            self.lap_counts[id(genome)] = 0
            self.positions[id(genome)] = 0
        
        return participants

    def update_position(self, car: Car, genome_id: int, gates_passed: int) -> None:
        """Update race position based on gates passed."""
        self.positions[genome_id] = gates_passed
        self.lap_counts[genome_id] = gates_passed // 20  # Approximate laps

    def on_car_finish(self, car: Car, genome_id: int, race_time: float) -> None:
        """Record race finish."""
        # Calculate position based on when they finished
        position = len([r for r in self.results if r.finished]) + 1
        
        points = self.POINTS_SYSTEM[position - 1] if position <= len(self.POINTS_SYSTEM) else 0
        
        result = RaceResult(
            car_id=id(car),
            genome_id=genome_id,
            position=position,
            lap_time=race_time,
            best_lap=race_time / max(1, self.lap_counts.get(genome_id, 1)),
            gates_passed=self.positions.get(genome_id, 0),
            finished=True,
            points=points,
        )
        self.results.append(result)

    def calculate_fitness(self, result: RaceResult) -> float:
        """Calculate fitness from race result."""
        fitness = result.points * 100  # Points are primary
        
        # Bonus for finishing
        if result.finished:
            fitness += 500
        
        # Bonus for gates passed (for DNF cars)
        fitness += result.gates_passed * 10
        
        return fitness

    def get_leader(self) -> int | None:
        """Get genome ID of current leader."""
        if not self.positions:
            return None
        return max(self.positions, key=self.positions.get)

    def is_race_over(self) -> bool:
        """Check if all cars have finished or timed out."""
        finished_count = len([r for r in self.results if r.finished])
        return finished_count >= len(self.positions)
