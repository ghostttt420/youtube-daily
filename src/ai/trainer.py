"""NEAT evolution trainer with proper error handling."""

from __future__ import annotations

import glob
import os
import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import imageio
import neat
import numpy as np
import pygame

from src.config import get_settings, load_theme
from src.constants import Fitness, Video, NEAT
from src.logging_config import get_logger
from src.simulation import Camera, Car, TrackGenerator

if TYPE_CHECKING:
    from neat.genome import DefaultGenome

logger = get_logger(__name__)


class EvolutionTrainer:
    """Manages NEAT evolution training sessions.
    
    Attributes:
        config: NEAT configuration
        population: Current population
        generation: Current generation number
        start_gen: Generation number at session start
        final_gen: Target generation number
        stats: Statistics reporter
    """

    def __init__(self, config_path: str | Path = "config.txt") -> None:
        """Initialize the trainer.
        
        Args:
            config_path: Path to NEAT config file
        """
        self.settings = get_settings()
        self.config_path = Path(config_path)
        self.config: neat.Config | None = None
        self.population: neat.Population | None = None
        self.generation = 0
        self.start_gen = 0
        self.final_gen = 0
        self.stats = neat.StatisticsReporter()
        
        # Ensure pygame uses dummy drivers for headless
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    def create_neat_config(self) -> None:
        """Create default NEAT configuration file if not exists."""
        if self.config_path.exists():
            return

        config_content = """
[NEAT]
fitness_criterion     = max
fitness_threshold     = 100000
pop_size              = 40
reset_on_extinction   = False
no_fitness_termination = False

[DefaultGenome]
activation_default      = tanh
activation_mutate_rate  = 0.0
activation_options      = tanh
aggregation_default     = sum
aggregation_mutate_rate = 0.0
aggregation_options     = sum

bias_init_mean          = 0.0
bias_init_stdev         = 1.0
bias_max_value          = 30.0
bias_min_value          = -30.0
bias_mutate_power       = 0.5
bias_replace_rate       = 0.1
bias_mutate_rate        = 0.2
bias_init_type          = gaussian

response_init_mean      = 1.0
response_init_stdev     = 0.0
response_max_value      = 30.0
response_min_value      = -30.0
response_mutate_power   = 0.0
response_replace_rate   = 0.0
response_mutate_rate    = 0.0
response_init_type      = gaussian

weight_init_mean        = 0.0
weight_init_stdev       = 1.0
weight_max_value        = 30
weight_min_value        = -30
weight_mutate_power     = 0.5
weight_replace_rate     = 0.1
weight_mutate_rate      = 0.3
weight_init_type        = gaussian

conn_add_prob           = 0.3
conn_delete_prob        = 0.3
enabled_default         = True
enabled_mutate_rate     = 0.01
feed_forward            = True
initial_connection      = full

enabled_rate_to_true_add = 0.0
enabled_rate_to_false_add = 0.0

num_hidden              = 0
num_inputs              = 7
num_outputs             = 2

node_add_prob           = 0.1
node_delete_prob        = 0.1

compatibility_disjoint_coefficient = 1.0
compatibility_weight_coefficient   = 0.5

single_structural_mutation = False
structural_mutation_surer  = default

[DefaultSpeciesSet]
compatibility_threshold = 3.0

[DefaultStagnation]
species_fitness_func = max
max_stagnation       = 20
species_elitism      = 2

[DefaultReproduction]
elitism            = 2
survival_threshold = 0.2
min_species_size   = 2
"""
        self.config_path.write_text(config_content.strip())
        logger.info("neat_config_created", path=str(self.config_path))

    def find_latest_checkpoint(self) -> Path | None:
        """Find the most recent checkpoint file.
        
        Returns:
            Path to latest checkpoint or None
        """
        checkpoints = list(Path(".").glob("neat-checkpoint-*"))
        if not checkpoints:
            return None
        
        # Sort by generation number
        latest = max(checkpoints, key=lambda p: int(p.stem.split("-")[-1]))
        return latest

    def load_checkpoint(self, path: Path) -> neat.Population:
        """Load population from checkpoint.
        
        Args:
            path: Checkpoint file path
            
        Returns:
            Restored population
        """
        self.start_gen = int(path.stem.split("-")[-1])
        self.generation = self.start_gen
        
        logger.info(
            "checkpoint_loading",
            path=str(path),
            generation=self.start_gen,
        )
        
        try:
            population = neat.Checkpointer.restore_checkpoint(str(path))
            logger.info("checkpoint_loaded", generation=self.start_gen)
            return population
        except (pickle.PickleError, EOFError) as e:
            logger.error("checkpoint_corrupted", path=str(path), error=str(e))
            raise RuntimeError(f"Checkpoint corrupted: {path}") from e

    def create_population(self) -> neat.Population:
        """Create fresh population.
        
        Returns:
            New population
        """
        logger.info("creating_fresh_population")
        
        if not self.config:
            raise RuntimeError("NEAT config not loaded")
        
        population = neat.Population(self.config)
        self.start_gen = 0
        self.generation = 0
        return population

    def run_dummy_generation(self) -> None:
        """Run a dummy generation 0 for demonstration."""
        logger.info("running_dummy_generation")
        
        theme = load_theme()
        seed = theme.map_seed if theme else 42
        
        pygame.init()
        screen = pygame.display.set_mode(
            (self.settings.simulation.width, self.settings.simulation.height)
        )
        
        # Generate track
        track_gen = TrackGenerator(seed=seed)
        start_pos, track_surface, visual_map, checkpoints, start_angle = (
            track_gen.generate_track(self.settings.simulation.world_size)
        )
        map_mask = pygame.mask.from_surface(track_surface)
        camera = Camera(
            self.settings.simulation.world_size,
            self.settings.simulation.world_size,
        )
        camera.set_viewport(
            self.settings.simulation.width,
            self.settings.simulation.height,
        )
        
        # Create random cars
        cars = [Car(start_pos, start_angle) for _ in range(40)]
        
        # Setup video writer
        video_path = self.settings.paths.clips_dir / "gen_00000.mp4"
        writer = imageio.get_writer(video_path, fps=Video.OUTPUT_FPS)
        
        try:
            frame_count = 0
            max_frames = 300
            
            while frame_count < max_frames and any(c.alive for c in cars):
                frame_count += 1
                
                # Handle quit events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                
                # Update camera to follow leader
                alive_cars = [c for c in cars if c.alive]
                if alive_cars:
                    leader = max(alive_cars, key=lambda c: c.distance_traveled)
                    camera.update(leader)
                    for c in cars:
                        c.is_leader = (c == leader)
                
                # Random inputs for dummy gen
                for car in cars:
                    if car.alive:
                        if random.random() < 0.1:
                            car.steering = random.choice([-1.0, 0.0, 1.0])
                        car.input_gas()
                        car.update(map_mask)
                
                # Render
                screen.fill((30, 35, 30))
                screen.blit(visual_map, (camera.camera.x, camera.camera.y))
                for car in cars:
                    car.draw(screen, camera)
                
                # Draw label
                font = pygame.font.SysFont("consolas", 40, bold=True)
                label = font.render("GEN 0 (NOOB)", True, (200, 0, 0))
                screen.blit(label, (20, 20))
                
                pygame.display.flip()
                
                # Capture frame
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except Exception as e:
                    logger.warning("frame_capture_failed", frame=frame_count, error=str(e))
            
            logger.info("dummy_generation_complete", frames=frame_count)
            
        finally:
            writer.close()
            pygame.quit()

    def run_evolution(self) -> None:
        """Run the evolution process."""
        self.create_neat_config()
        
        # Load or create population
        checkpoint = self.find_latest_checkpoint()
        
        if checkpoint:
            self.population = self.load_checkpoint(checkpoint)
        else:
            # Fresh start
            self.config = neat.Config(
                neat.DefaultGenome,
                neat.DefaultReproduction,
                neat.DefaultSpeciesSet,
                neat.DefaultStagnation,
                str(self.config_path),
            )
            self.run_dummy_generation()
            self.population = self.create_population()
        
        # Set target
        self.final_gen = self.start_gen + self.settings.neat.daily_generations
        
        logger.info(
            "evolution_starting",
            start_gen=self.start_gen,
            target_gen=self.final_gen,
            generations=self.settings.neat.daily_generations,
        )
        
        # Add reporters
        self.population.add_reporter(neat.StdOutReporter(True))
        self.population.add_reporter(self.stats)
        self.population.add_reporter(
            neat.Checkpointer(
                generation_interval=self.settings.neat.checkpoint_interval,
                filename_prefix="neat-checkpoint-",
            )
        )
        
        # Run evolution
        winner = self.population.run(
            self._evaluate_generation,
            self.settings.neat.daily_generations,
        )
        
        logger.info(
            "evolution_complete",
            final_generation=self.generation,
            winner_fitness=winner.fitness if winner else None,
        )

    def _evaluate_generation(
        self,
        genomes: list[tuple[int, DefaultGenome]],
        config: neat.Config,
    ) -> None:
        """Evaluate one generation.
        
        Args:
            genomes: List of (genome_id, genome) tuples
            config: NEAT configuration
        """
        self.generation += 1
        
        logger.info(
            "generation_start",
            generation=self.generation,
            population_size=len(genomes),
        )
        
        # Create networks and cars
        nets = []
        cars = []
        genomes_list = []
        
        for _, genome in genomes:
            net = neat.nn.FeedForwardNetwork.create(genome, config)
            nets.append(net)
            # Car will be initialized with track
            cars.append(None)  # type: ignore
            genome.fitness = 0.0
            genomes_list.append(genome)
        
        # Run simulation
        self._simulate(cars, nets, genomes_list)
        
        # Log stats
        fitnesses = [g.fitness for g in genomes_list if g.fitness is not None]
        if fitnesses:
            logger.info(
                "generation_complete",
                generation=self.generation,
                max_fitness=max(fitnesses),
                avg_fitness=sum(fitnesses) / len(fitnesses),
                survivors=len([c for c in cars if c and c.alive]),
            )

    def _simulate(
        self,
        cars: list[Car | None],
        nets: list,
        genomes: list[DefaultGenome],
    ) -> None:
        """Run physics simulation for this generation.
        
        Args:
            cars: List of cars (some may be None initially)
            nets: Neural networks for each car
            genomes: Genomes to evaluate
        """
        import random
        
        theme = load_theme()
        seed = theme.map_seed if theme else 42
        friction = theme.friction if theme else 0.97
        
        pygame.init()
        screen = pygame.display.set_mode(
            (self.settings.simulation.width, self.settings.simulation.height)
        )
        
        # Generate track
        track_gen = TrackGenerator(seed=seed)
        start_pos, track_surface, visual_map, checkpoints, start_angle = (
            track_gen.generate_track(self.settings.simulation.world_size)
        )
        map_mask = pygame.mask.from_surface(track_surface)
        camera = Camera(
            self.settings.simulation.world_size,
            self.settings.simulation.world_size,
        )
        camera.set_viewport(
            self.settings.simulation.width,
            self.settings.simulation.height,
        )
        
        # Initialize cars
        for i in range(len(cars)):
            cars[i] = Car(start_pos, start_angle, friction=friction)
        
        # Determine if we should record
        is_first = self.generation == self.start_gen + 1
        is_milestone = self.generation % 10 == 0
        is_last = self.generation >= self.final_gen
        should_record = is_first or is_milestone or is_last
        
        writer = None
        if should_record:
            video_path = (
                self.settings.paths.clips_dir / f"gen_{self.generation:05d}.mp4"
            )
            writer = imageio.get_writer(video_path, fps=Video.OUTPUT_FPS)
            logger.info("recording_generation", generation=self.generation, path=str(video_path))
        
        # Determine max frames
        max_frames = (
            self.settings.simulation.max_frames_pro
            if is_last
            else self.settings.simulation.max_frames_training
        )
        
        # Initial sensor check
        for car in cars:
            if car:
                car.check_radar(map_mask)
        
        try:
            frame_count = 0
            
            while frame_count < max_frames and any(
                c and c.alive for c in cars
            ):
                frame_count += 1
                
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                
                # Find leader
                alive_cars = [c for c in cars if c and c.alive]
                if alive_cars:
                    leader = max(
                        alive_cars,
                        key=lambda c: c.gates_passed * 1000 + c.distance_traveled,
                    )
                    camera.update(leader)
                    for c in cars:
                        if c:
                            c.is_leader = (c == leader)
                
                # Update each car
                for i, car in enumerate(cars):
                    if not car or not car.alive:
                        continue
                    
                    # Prepare inputs
                    radar_inputs = (
                        [d[1] / 300.0 for d in car.radars]
                        if len(car.radars) >= 5
                        else [0.0] * 5
                    )
                    gps_inputs = car.get_data(checkpoints)
                    inputs = radar_inputs + gps_inputs
                    
                    # Get AI output
                    output = nets[i].activate(inputs)
                    
                    # Apply controls
                    if output[0] > 0.5:
                        car.input_steer(right=True)
                    elif output[0] < -0.5:
                        car.input_steer(left=True)
                    
                    car.input_gas()
                    car.update(map_mask)
                    car.check_radar(map_mask)
                    
                    # Score fitness
                    if car.check_gates(checkpoints):
                        genomes[i].fitness += Fitness.GATE_PASS_BONUS
                    
                    if car.gates_passed >= len(checkpoints):
                        genomes[i].fitness += Fitness.LAP_COMPLETE_BONUS
                    
                    # Distance score
                    dist_score = 1.0 - gps_inputs[1]
                    genomes[i].fitness += dist_score * Fitness.DISTANCE_WEIGHT
                    
                    # Center bonus
                    if len(car.radars) >= 5:
                        left_dist = car.radars[0][1]
                        right_dist = car.radars[4][1]
                        center_ratio = 1.0 - abs(left_dist - right_dist) / 300.0
                        center_ratio = max(0, center_ratio)
                        genomes[i].fitness += center_ratio * 0.1
                    
                    # Death penalties
                    if not car.alive:
                        genomes[i].fitness -= Fitness.DEATH_PENALTY
                        if car.distance_traveled < Fitness.MIN_DISTANCE_FOR_EARLY_DEATH:
                            genomes[i].fitness -= Fitness.EARLY_DEATH_PENALTY
                    
                    if not car.alive and car.frames_since_gate > Fitness.MAX_FRAMES_STUCK:
                        genomes[i].fitness -= Fitness.STUCK_PENALTY
                
                # Handle collisions
                valid_cars = [c for c in cars if c]
                for car in valid_cars:
                    if car.alive:
                        car.handle_car_collision(valid_cars)
                
                # Remove dead cars
                for i in range(len(cars) - 1, -1, -1):
                    if cars[i] and not cars[i].alive:
                        cars.pop(i)
                        nets.pop(i)
                        genomes.pop(i)
                
                # Render
                should_render = should_record or frame_count % Video.RECORD_EVERY_N_FRAMES == 0
                if should_render:
                    screen.fill((30, 35, 30))
                    screen.blit(visual_map, (camera.camera.x, camera.camera.y))
                    for car in cars:
                        if car:
                            car.draw(screen, camera)
                    
                    # Draw HUD
                    font = pygame.font.SysFont("consolas", 40, bold=True)
                    seconds = int(frame_count / Video.OUTPUT_FPS)
                    time_text = font.render(f"{seconds}s", True, (255, 255, 255))
                    gen_text = font.render(f"GEN {self.generation}", True, (200, 0, 0))
                    screen.blit(time_text, (20, 60))
                    screen.blit(gen_text, (20, 20))
                    
                    pygame.display.flip()
                    
                    # Capture for video
                    if writer:
                        try:
                            pixels = pygame.surfarray.array3d(screen)
                            pixels = np.transpose(pixels, (1, 0, 2))
                            writer.append_data(pixels)
                        except Exception as e:
                            logger.warning(
                                "frame_capture_failed",
                                frame=frame_count,
                                error=str(e),
                            )
        
        finally:
            if writer:
                writer.close()
            pygame.quit()
