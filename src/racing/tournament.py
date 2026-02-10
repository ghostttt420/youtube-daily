"""Weekly tournament system for championship races."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import neat
import pygame
import structlog

from src.config import get_settings
from src.logging_config import get_logger
from src.metrics.database import MetricsDatabase
from src.racing.ghost import GhostCar, GhostRecorder
from src.simulation import Camera, Car, TrackGenerator

logger = get_logger(__name__)


@dataclass
class TournamentEntry:
    """Entry in the tournament."""
    generation: int
    genome_id: int
    fitness: float
    checkpoint_path: Path
    points: int = 0


@dataclass
class TournamentResult:
    """Result of tournament for one entry."""
    generation: int
    position: int
    points: int
    best_lap: float
    total_time: float


class WeeklyTournament:
    """Manages weekly championship tournaments."""

    POINTS_SYSTEM = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

    def __init__(self, db: MetricsDatabase | None = None) -> None:
        """Initialize tournament manager."""
        self.settings = get_settings()
        self.db = db or MetricsDatabase()
        self.entries: list[TournamentEntry] = []
        self.results: list[TournamentResult] = []
        
        # Tournament config
        self.num_races = 3
        self.laps_per_race = 2
        self.max_cars = 8

    def find_best_cars(self, days: int = 7) -> list[TournamentEntry]:
        """Find best performing cars from recent generations."""
        history = self.db.get_fitness_history(limit=100)
        
        entries = []
        seen_gens = set()
        
        # Sort by fitness
        sorted_history = sorted(history, key=lambda x: x["max_fitness"], reverse=True)
        
        for row in sorted_history:
            gen = row["generation"]
            if gen in seen_gens:
                continue
            
            # Find checkpoint
            checkpoint = Path(f"neat-checkpoint-{gen}")
            if checkpoint.exists():
                entries.append(TournamentEntry(
                    generation=gen,
                    genome_id=row.get("best_genome_id", 0),
                    fitness=row["max_fitness"],
                    checkpoint_path=checkpoint,
                ))
                seen_gens.add(gen)
            
            if len(entries) >= self.max_cars:
                break
        
        self.entries = entries
        return entries

    def run_tournament(self) -> list[dict]:
        """Run the full tournament."""
        logger.info("tournament_starting")
        
        # Get entries
        self.find_best_cars()
        
        if len(self.entries) < 2:
            logger.error("not_enough_entries", count=len(self.entries))
            return []
        
        logger.info("tournament_entries", count=len(self.entries), generations=[e.generation for e in self.entries])
        
        # Run races
        for race_num in range(self.num_races):
            logger.info("tournament_race_starting", race=race_num + 1)
            self._run_race(race_num)
        
        # Calculate final results
        self._calculate_final_results()
        
        # Save results
        self._save_results()
        
        return [r.__dict__ for r in self.results]

    def _run_race(self, race_num: int) -> None:
        """Run a single race."""
        # Generate track
        track_gen = TrackGenerator(seed=race_num + 1000)
        start_pos, track_surface, visual_map, checkpoints, start_angle = \
            track_gen.generate_track(self.settings.simulation.world_size)
        
        map_mask = pygame.mask.from_surface(track_surface)
        camera = Camera(self.settings.simulation.world_size, self.settings.simulation.world_size)
        camera.set_viewport(self.settings.simulation.width, self.settings.simulation.height)
        
        # Load genomes
        cars = []
        genomes = []
        networks = []
        lap_counts = {i: 0 for i in range(len(self.entries))}
        finish_times = {}
        
        pygame.init()
        
        config = neat.Config(
            neat.DefaultGenome,
            neat.DefaultReproduction,
            neat.DefaultSpeciesSet,
            neat.DefaultStagnation,
            str(self.settings.neat.config_path),
        )
        
        for i, entry in enumerate(self.entries):
            try:
                population = neat.Checkpointer.restore_checkpoint(str(entry.checkpoint_path))
                
                # Get best genome from this population
                best_genome = max(population.population.values(), key=lambda g: g.fitness or 0)
                
                net = neat.nn.FeedForwardNetwork.create(best_genome, config)
                networks.append(net)
                genomes.append((i, best_genome))
                cars.append(Car(start_pos, start_angle))
                
            except Exception as e:
                logger.error("failed_to_load_checkpoint", generation=entry.generation, error=str(e))
                continue
        
        if len(cars) < 2:
            logger.error("not_enough_cars_loaded")
            return
        
        # Initialize sensors
        for car in cars:
            car.check_radar(map_mask)
        
        # Race loop
        max_frames = self.laps_per_race * 2000  # Approximate
        frame = 0
        
        try:
            while frame < max_frames and len(finish_times) < len(cars):
                frame += 1
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                
                # Find leader
                alive_cars = [(i, c) for i, c in enumerate(cars) if c.alive]
                if alive_cars:
                    leader_idx, leader = max(
                        alive_cars,
                        key=lambda x: x[1].gates_passed * 1000 + x[1].distance_traveled
                    )
                    camera.update(leader)
                    for c in cars:
                        c.is_leader = (c == leader)
                
                # Update each car
                for i, car in enumerate(cars):
                    if not car.alive or i >= len(networks):
                        continue
                    
                    # AI inputs
                    radar_inputs = (
                        [d[1] / 300.0 for d in car.radars]
                        if len(car.radars) >= 5
                        else [0.0] * 5
                    )
                    gps_inputs = car.get_data(checkpoints)
                    inputs = radar_inputs + gps_inputs
                    
                    output = networks[i].activate(inputs)
                    
                    if output[0] > 0.5:
                        car.input_steer(right=True)
                    elif output[0] < -0.5:
                        car.input_steer(left=True)
                    
                    car.input_gas()
                    car.update(map_mask)
                    car.check_radar(map_mask)
                    
                    # Track laps
                    if car.check_gates(checkpoints):
                        lap_counts[i] += 1
                        if lap_counts[i] >= len(checkpoints) * self.laps_per_race:
                            if i not in finish_times:
                                finish_times[i] = frame
                                car.alive = False
                
                # Handle collisions
                for i, car in enumerate(cars):
                    if car.alive:
                        car.handle_car_collision(cars)
        
        finally:
            pygame.quit()
        
        # Award points based on finish order
        sorted_finishes = sorted(finish_times.items(), key=lambda x: x[1])
        
        for position, (car_idx, time) in enumerate(sorted_finishes):
            if car_idx < len(self.entries):
                points = self.POINTS_SYSTEM[position] if position < len(self.POINTS_SYSTEM) else 0
                self.entries[car_idx].points += points

    def _calculate_final_results(self) -> None:
        """Calculate final tournament results."""
        sorted_entries = sorted(self.entries, key=lambda e: e.points, reverse=True)
        
        self.results = [
            TournamentResult(
                generation=e.generation,
                position=i + 1,
                points=e.points,
                best_lap=0.0,
                total_time=0.0,
            )
            for i, e in enumerate(sorted_entries)
        ]

    def _save_results(self) -> None:
        """Save tournament results."""
        results_dir = self.settings.paths.data_dir / "tournaments"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"tournament_{datetime.now().strftime('%Y%m%d')}.json"
        path = results_dir / filename
        
        data = {
            "date": datetime.now().isoformat(),
            "entries": len(self.entries),
            "results": [r.__dict__ for r in self.results],
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info("tournament_results_saved", path=str(path))

    def get_champion(self) -> TournamentEntry | None:
        """Get the tournament champion."""
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: e.points)
