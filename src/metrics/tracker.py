"""Real-time metrics tracking with wandb integration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from src.config import get_settings
from src.metrics.database import MetricsDatabase

logger = structlog.get_logger()

if TYPE_CHECKING:
    from neat.population import Population
    from neat.species import Species


@dataclass
class GenerationMetrics:
    """Metrics for a single generation."""

    generation: int
    timestamp: float = field(default_factory=time.time)
    
    # Fitness stats
    fitness_max: float = 0.0
    fitness_avg: float = 0.0
    fitness_min: float = 0.0
    fitness_std: float = 0.0
    
    # Population stats
    population_size: int = 0
    survivors: int = 0
    species_count: int = 0
    
    # Performance
    simulation_time: float = 0.0
    frames_simulated: int = 0
    
    # Best performer
    best_distance: float = 0.0
    best_gates: int = 0
    best_lap_time: int = 0
    
    # Multi-objective
    smoothness_score: float = 0.0
    efficiency_score: float = 0.0
    speed_score: float = 0.0
    
    # Speciation
    species_data: list[dict] = field(default_factory=list)


class MetricsTracker:
    """Tracks evolution metrics with optional wandb logging."""

    def __init__(self) -> None:
        """Initialize tracker."""
        self.settings = get_settings()
        self.db = MetricsDatabase()
        self._wandb = None
        self._wandb_enabled = False
        
        # Generation tracking
        self.current_generation = 0
        self.generation_start_time: float | None = None
        self.metrics_history: list[GenerationMetrics] = []
        
        # Best tracking
        self.best_fitness_ever = 0.0
        self.best_generation = 0
        
        # Crash tracking for heatmap
        self.crashes_this_generation: list[tuple[float, float, str]] = []
        
        self._init_wandb()

    def _init_wandb(self) -> None:
        """Initialize wandb if available and enabled."""
        try:
            import wandb
            
            if self.settings.feature_flags.get("enable_wandb", False):
                wandb.init(
                    project="ai-racing-evolution",
                    entity=self.settings.wandb_entity,
                    config={
                        "population_size": self.settings.neat.population_size,
                        "daily_generations": self.settings.neat.daily_generations,
                        "theme": self._get_current_theme(),
                    },
                )
                self._wandb = wandb
                self._wandb_enabled = True
                logger.info("wandb_initialized")
        except ImportError:
            logger.debug("wandb_not_available")
        except Exception as e:
            logger.warning("wandb_init_failed", error=str(e))

    def start_generation(self, generation: int) -> None:
        """Mark start of generation."""
        self.current_generation = generation
        self.generation_start_time = time.time()
        self.crashes_this_generation = []
        logger.info("generation_started", generation=generation)

    def log_simulation_step(
        self,
        cars_alive: int,
        frames: int,
    ) -> None:
        """Log mid-simulation metrics (for long simulations)."""
        if self._wandb_enabled and frames % 100 == 0:
            self._wandb.log({
                "simulation/cars_alive": cars_alive,
                "simulation/frames": frames,
                "simulation/generation": self.current_generation,
            }, step=self.current_generation * 10000 + frames)

    def log_crash(self, x: float, y: float, cause: str, fitness: float) -> None:
        """Log a crash event."""
        self.crashes_this_generation.append((x, y, cause))
        self.db.log_crash(self.current_generation, x, y, cause, fitness)

    def end_generation(
        self,
        genomes: list[tuple[int, Any]],
        population: Population | None = None,
        best_car_data: dict[str, Any] | None = None,
    ) -> GenerationMetrics:
        """Log end of generation statistics."""
        simulation_time = time.time() - (self.generation_start_time or time.time())
        
        # Calculate fitness stats
        fitnesses = [g.fitness for _, g in genomes if g.fitness is not None]
        if not fitnesses:
            fitnesses = [0.0]
        
        metrics = GenerationMetrics(
            generation=self.current_generation,
            fitness_max=max(fitnesses),
            fitness_avg=sum(fitnesses) / len(fitnesses),
            fitness_min=min(fitnesses),
            fitness_std=self._calc_std(fitnesses),
            population_size=len(genomes),
            survivors=len([f for f in fitnesses if f > 0]),
            simulation_time=simulation_time,
        )
        
        # Extract species data
        if population and population.species:
            metrics.species_count = len(population.species.species)
            metrics.species_data = self._extract_species_data(population.species)
        
        # Add best car data
        if best_car_data:
            metrics.best_distance = best_car_data.get("distance", 0)
            metrics.best_gates = best_car_data.get("gates", 0)
            metrics.best_lap_time = best_car_data.get("lap_time", 0)
            metrics.smoothness_score = best_car_data.get("smoothness", 0)
            metrics.efficiency_score = best_car_data.get("efficiency", 0)
            metrics.speed_score = best_car_data.get("speed", 0)
        
        # Update best ever
        if metrics.fitness_max > self.best_fitness_ever:
            self.best_fitness_ever = metrics.fitness_max
            self.best_generation = self.current_generation
        
        # Store and log
        self.metrics_history.append(metrics)
        self._persist_metrics(metrics)
        self._log_to_wandb(metrics)
        
        logger.info(
            "generation_complete",
            generation=metrics.generation,
            max_fitness=metrics.fitness_max,
            avg_fitness=metrics.fitness_avg,
            species=metrics.species_count,
            survivors=metrics.survivors,
            time=simulation_time,
        )
        
        return metrics

    def _persist_metrics(self, metrics: GenerationMetrics) -> None:
        """Save metrics to database."""
        self.db.log_generation(
            generation=metrics.generation,
            fitnesses=[metrics.fitness_max, metrics.fitness_avg, metrics.fitness_min],
            species_count=metrics.species_count,
            survivors=metrics.survivors,
            theme=self._get_current_theme(),
            map_seed=self._get_current_seed(),
            best_genome_fitness=metrics.fitness_max,
        )
        
        if metrics.species_data:
            self.db.log_species(metrics.generation, metrics.species_data)

    def _log_to_wandb(self, metrics: GenerationMetrics) -> None:
        """Log to wandb if enabled."""
        if not self._wandb_enabled:
            return
        
        self._wandb.log({
            "fitness/max": metrics.fitness_max,
            "fitness/avg": metrics.fitness_avg,
            "fitness/min": metrics.fitness_min,
            "fitness/std": metrics.fitness_std,
            "population/size": metrics.population_size,
            "population/survivors": metrics.survivors,
            "population/species": metrics.species_count,
            "performance/simulation_time": metrics.simulation_time,
            "performance/best_distance": metrics.best_distance,
            "performance/best_gates": metrics.best_gates,
            "multi_objective/smoothness": metrics.smoothness_score,
            "multi_objective/efficiency": metrics.efficiency_score,
            "multi_objective/speed": metrics.speed_score,
            "generation": metrics.generation,
        })

    def _extract_species_data(self, species_set) -> list[dict]:
        """Extract data from species set."""
        data = []
        for sid, species in species_set.species.items():
            fitnesses = [m.fitness for m in species.members.values() if m.fitness]
            # Calculate age from created generation (use getattr for compatibility)
            created_gen = getattr(species, 'created', 0)
            age = self.current_generation - created_gen if hasattr(self, 'current_generation') else 0
            stagnant = getattr(species, 'stagnation', 0)
            data.append({
                "id": sid,
                "size": len(species.members),
                "fitness_max": max(fitnesses) if fitnesses else 0,
                "fitness_avg": sum(fitnesses) / len(fitnesses) if fitnesses else 0,
                "fitness_min": min(fitnesses) if fitnesses else 0,
                "age": age,
                "stagnant": stagnant,
            })
        return data

    def _calc_std(self, values: list[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

    def _get_current_theme(self) -> str:
        """Get current theme key."""
        from src.config import load_theme
        theme = load_theme()
        return theme.key if theme else "unknown"

    def _get_current_seed(self) -> int:
        """Get current map seed."""
        from src.config import load_theme
        theme = load_theme()
        return theme.map_seed if theme else 0

    def get_improvement_rate(self, window: int = 10) -> float:
        """Calculate rate of improvement over recent generations."""
        if len(self.metrics_history) < window:
            return 0.0
        
        recent = self.metrics_history[-window:]
        if recent[0].fitness_avg == 0:
            return 0.0
        
        return (recent[-1].fitness_avg - recent[0].fitness_avg) / recent[0].fitness_avg

    def should_increase_difficulty(self) -> bool:
        """Check if curriculum should advance."""
        if len(self.metrics_history) < 5:
            return False
        
        recent = self.metrics_history[-5:]
        avg_fitness = sum(m.fitness_max for m in recent) / 5
        
        # If consistently achieving high fitness, increase difficulty
        return avg_fitness > 5000  # Threshold for curriculum advancement


# Global tracker instance
_tracker_instance: MetricsTracker | None = None


def get_tracker() -> MetricsTracker:
    """Get global tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = MetricsTracker()
    return _tracker_instance


def reset_tracker() -> None:
    """Reset global tracker (for testing)."""
    global _tracker_instance
    _tracker_instance = None
