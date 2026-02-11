"""Enhanced NEAT trainer with all new features integrated."""

from __future__ import annotations

import os
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import imageio
import neat
import numpy as np
import pygame
import structlog

from src.config import get_settings, load_theme
from src.constants import Fitness, Video
from src.curriculum.manager import get_curriculum_manager
from src.logging_config import get_logger
from src.metrics.tracker import get_tracker
from src.racing.ghost import GhostCar, GhostRecorder
from src.simulation import Camera, Car, TrackGenerator
from src.utils.error_recovery import ErrorRecovery, SimulationCrash
from src.utils.feature_flags import get_feature_flags
from src.weather.system import WeatherSystem
from src.weather.effects import WeatherEffects

if TYPE_CHECKING:
    from neat.genome import DefaultGenome

logger = get_logger(__name__)


@dataclass
class CarEvaluationData:
    """Extended data for evaluating a car's performance."""
    distance: float = 0.0
    gates: int = 0
    lap_time: int = 0
    steering_changes: int = 0
    total_steering: float = 0.0
    path_length: float = 0.0
    last_position: tuple[float, float] | None = None
    
    @property
    def smoothness(self) -> float:
        """Calculate smoothness score (lower steering variance = smoother)."""
        if self.steering_changes == 0:
            return 1.0
        avg_steering = abs(self.total_steering) / self.steering_changes
        return max(0, 1.0 - avg_steering / 10)
    
    @property
    def efficiency(self) -> float:
        """Calculate efficiency (shorter path = more efficient)."""
        if self.distance == 0:
            return 0.0
        # Ideal would be straight line, reward staying close to it
        return min(1.0, self.distance / max(self.path_length, 1))
    
    @property
    def speed(self) -> float:
        """Calculate average speed."""
        if self.lap_time == 0:
            return 0.0
        return self.distance / self.lap_time


class EnhancedEvolutionTrainer:
    """Enhanced trainer with curriculum, weather, ghosts, and multi-objective fitness."""

    def __init__(self, config_path: str | Path = "config.txt") -> None:
        """Initialize enhanced trainer."""
        self.settings = get_settings()
        self.config_path = Path(config_path)
        self.config: neat.Config | None = None
        self.population: neat.Population | None = None
        self.generation = 0
        self.start_gen = 0
        self.final_gen = 0
        
        # Feature flags
        self.flags = get_feature_flags()
        
        # Subsystems
        self.tracker = get_tracker()
        self.curriculum = get_curriculum_manager()
        self.weather = WeatherSystem(enable_weather=self.flags.enable_weather)
        self.weather_effects = WeatherEffects()
        self.recovery = ErrorRecovery()
        
        # Ghost system
        self.ghost_recorder = GhostRecorder()
        self.current_ghost: GhostCar | None = None
        
        # Track generation
        self.track_gen: TrackGenerator | None = None
        self.start_pos: tuple[int, int] = (0, 0)
        self.start_angle: float = 0.0
        self.checkpoints: list[tuple[float, float]] = []
        self._bg_color = (30, 35, 30)  # Default background color
        
        # Headless mode for server
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    
    def _get_bg_color(self) -> tuple[int, int, int]:
        """Get background color from current theme."""
        theme = load_theme()
        if theme:
            return theme.colors.bg
        return (30, 35, 30)

    def create_neat_config(self) -> None:
        """Create and validate NEAT configuration."""
        if self.config_path.exists():
            # Validate existing config
            self._validate_config()
            return
        
        # Create default config with correct values
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

    def _validate_config(self) -> None:
        """Validate NEAT config matches expected values."""
        # Parse config file
        import configparser
        parser = configparser.ConfigParser()
        parser.read(self.config_path)
        
        # Check critical values
        num_inputs = parser.getint("DefaultGenome", "num_inputs", fallback=0)
        num_outputs = parser.getint("DefaultGenome", "num_outputs", fallback=0)
        
        if num_inputs != 7 or num_outputs != 2:
            logger.error(
                "config_mismatch",
                expected_inputs=7,
                actual_inputs=num_inputs,
                expected_outputs=2,
                actual_outputs=num_outputs,
            )
            raise ValueError(
                f"NEAT config mismatch: expected 7 inputs and 2 outputs, "
                f"got {num_inputs} inputs and {num_outputs} outputs"
            )

    def find_latest_checkpoint(self) -> Path | None:
        """Find most recent checkpoint."""
        checkpoints = list(Path(".").glob("neat-checkpoint-*"))
        if not checkpoints:
            return None
        return max(checkpoints, key=lambda p: int(p.stem.split("-")[-1]))

    def load_checkpoint(self, path: Path) -> neat.Population:
        """Load population from checkpoint."""
        self.start_gen = int(path.stem.split("-")[-1])
        self.generation = self.start_gen
        
        logger.info("loading_checkpoint", path=str(path), generation=self.start_gen)
        
        try:
            population = neat.Checkpointer.restore_checkpoint(str(path))
            return population
        except (pickle.PickleError, EOFError) as e:
            logger.error("checkpoint_corrupted", error=str(e))
            raise

    def create_population(self) -> neat.Population:
        """Create fresh population."""
        if not self.config:
            raise RuntimeError("NEAT config not loaded")
        
        return neat.Population(self.config)

    def setup_track(self) -> None:
        """Setup track for current generation."""
        theme = load_theme()
        
        # Use curriculum seed if enabled
        if self.flags.enable_curriculum:
            seed = self.curriculum.get_track_seed()
        else:
            seed = theme.map_seed if theme else 42
        
        self.track_gen = TrackGenerator(seed=seed)
        
        # Modify world size based on curriculum
        world_size = self.settings.simulation.world_size
        if self.flags.enable_curriculum:
            # Smaller world for early curriculum levels
            level = self.curriculum.current_level
            if level <= 2:
                world_size = 3000
            elif level <= 4:
                world_size = 3500
        
        self.start_pos, track_surface, visual_map, self.checkpoints, self.start_angle = \
            self.track_gen.generate_track(world_size)
        
        self.track_surface = track_surface
        self.visual_map = visual_map
        self.map_mask = pygame.mask.from_surface(track_surface)

    def run_evolution(self) -> None:
        """Run the full evolution process."""
        # Setup with error recovery
        def _setup():
            self.create_neat_config()
            
            checkpoint = self.find_latest_checkpoint()
            if checkpoint:
                self.population = self.load_checkpoint(checkpoint)
            else:
                self.config = neat.Config(
                    neat.DefaultGenome,
                    neat.DefaultReproduction,
                    neat.DefaultSpeciesSet,
                    neat.DefaultStagnation,
                    str(self.config_path),
                )
                self.run_dummy_generation()
                self.population = self.create_population()
            
            self.final_gen = self.start_gen + self.settings.neat.daily_generations
            
            # Add reporters
            self.population.add_reporter(neat.StdOutReporter(True))
            self.population.add_reporter(
                neat.Checkpointer(
                    generation_interval=self.settings.neat.checkpoint_interval,
                    filename_prefix="neat-checkpoint-",
                )
            )
            
            return True
        
        if self.flags.enable_error_recovery:
            self.recovery.with_recovery(_setup)
        else:
            _setup()
        
        logger.info(
            "evolution_starting",
            start_gen=self.start_gen,
            target_gen=self.final_gen,
            curriculum=self.curriculum.get_difficulty_name() if self.flags.enable_curriculum else "disabled",
            weather="enabled" if self.flags.enable_weather else "disabled",
        )
        
        # Run generations
        try:
            self.population.run(self._evaluate_generation, self.settings.neat.daily_generations)
        except Exception as e:
            if self.flags.enable_error_recovery:
                self.recovery.with_recovery(lambda: self.population.run(
                    self._evaluate_generation,
                    self.settings.neat.daily_generations
                ))
            else:
                raise

    def run_dummy_generation(self) -> None:
        """Run generation 0 with random inputs."""
        logger.info("running_dummy_generation")
        
        self.setup_track()
        
        pygame.init()
        screen = pygame.display.set_mode(
            (self.settings.simulation.width, self.settings.simulation.height)
        )
        camera = Camera(self.settings.simulation.world_size, self.settings.simulation.world_size)
        camera.set_viewport(self.settings.simulation.width, self.settings.simulation.height)
        
        cars = [Car(self.start_pos, self.start_angle) for _ in range(40)]
        
        # Load sprites for all cars
        for car in cars:
            car.load_sprites(self.settings.paths.assets_dir)
        
        # Initialize camera to center on starting position
        start_x = -self.start_pos[0] + self.settings.simulation.width / 2
        start_y = -self.start_pos[1] + self.settings.simulation.height / 2
        start_x = min(0, max(-(self.settings.simulation.world_size - self.settings.simulation.width), start_x))
        start_y = min(0, max(-(self.settings.simulation.world_size - self.settings.simulation.height), start_y))
        camera.exact_x = start_x
        camera.exact_y = start_y
        
        # Video setup
        video_path = self.settings.paths.clips_dir / "gen_00000.mp4"
        writer = imageio.get_writer(video_path, fps=Video.OUTPUT_FPS)
        
        try:
            frame_count = 0
            max_frames = 300
            fps_clock = pygame.time.Clock()
            
            while frame_count < max_frames and any(c.alive for c in cars):
                frame_count += 1
                fps_clock.tick(Video.OUTPUT_FPS)
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                
                alive_cars = [c for c in cars if c.alive]
                if alive_cars:
                    leader = max(alive_cars, key=lambda c: c.distance_traveled)
                    camera.update(leader)
                    for c in cars:
                        c.is_leader = (c == leader)
                
                # Random inputs
                for car in cars:
                    if car.alive:
                        if __import__('random').random() < 0.1:
                            car.steering = __import__('random').choice([-1.0, 0.0, 1.0])
                        car.input_gas()
                        car.update(self.map_mask)
                
                # Render
                bg_color = self._get_bg_color()
                screen.fill(bg_color)
                screen.blit(self.visual_map, (camera.camera.x, camera.camera.y))
                for car in cars:
                    car.draw(screen, camera)
                
                font = pygame.font.SysFont("consolas", 40, bold=True)
                label = font.render("GEN 0 (NOOB) 🤡", True, (200, 0, 0))
                screen.blit(label, (20, 20))
                
                pygame.display.flip()
                
                # Capture
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except Exception:
                    pass
        finally:
            writer.close()
            pygame.quit()

    def _evaluate_generation(
        self,
        genomes: list[tuple[int, DefaultGenome]],
        config: neat.Config,
    ) -> None:
        """Evaluate one generation."""
        self.generation += 1
        self.tracker.start_generation(self.generation)
        
        logger.info(
            "generation_start",
            generation=self.generation,
            population_size=len(genomes),
        )
        
        # Check if curriculum should advance
        if self.flags.enable_curriculum:
            recent = self.tracker.metrics_history[-10:] if len(self.tracker.metrics_history) >= 5 else []
            recent_fitnesses = [m.fitness_max for m in recent]
            
            if self.curriculum.should_advance(recent_fitnesses):
                self.curriculum.advance_level()
        
        # Setup track
        self.setup_track()
        
        # Load ghost for ghost racing
        if self.flags.enable_ghost_cars and self.generation > self.start_gen + 5:
            ghost_data = GhostRecorder.find_best_ghost(self.generation - 1)
            if ghost_data:
                gen, frames = ghost_data
                self.current_ghost = GhostCar(frames)
                logger.info("ghost_loaded", generation=gen)
            else:
                self.current_ghost = None
        
        # Create networks and cars
        nets = []
        cars = []
        genomes_list = []
        eval_data = []
        
        for _, genome in genomes:
            net = neat.nn.FeedForwardNetwork.create(genome, config)
            nets.append(net)
            
            # Car with curriculum-adjusted friction
            friction = self._get_friction()
            car = Car(self.start_pos, self.start_angle, friction=friction)
            cars.append(car)
            
            genome.fitness = 0.0
            genomes_list.append(genome)
            eval_data.append(CarEvaluationData())
        
        # Run simulation (sprites loaded after pygame init)
        self._simulate(cars, nets, genomes_list, eval_data)
        
        # Log metrics
        fitnesses = [g.fitness for g in genomes_list if g.fitness is not None]
        best_data = max(eval_data, key=lambda e: e.distance) if eval_data else CarEvaluationData()
        
        self.tracker.end_generation(
            genomes=[(0, g) for g in genomes_list],
            population=self.population,
            best_car_data={
                "distance": best_data.distance,
                "gates": best_data.gates,
                "lap_time": best_data.lap_time,
                "smoothness": best_data.smoothness,
                "efficiency": best_data.efficiency,
                "speed": best_data.speed,
            }
        )
        
        # Reset recovery counter on success
        if self.flags.enable_error_recovery:
            self.recovery.reset_recovery_count()
        
        # Curriculum progress
        if self.flags.enable_curriculum:
            self.curriculum.on_generation_complete(max(fitnesses) if fitnesses else 0)

    def _get_friction(self) -> float:
        """Get friction based on curriculum and weather."""
        base_friction = 0.97
        
        if self.flags.enable_curriculum:
            base_friction = self.curriculum.get_current_config().friction_base
        
        if self.flags.enable_weather and self.weather.current:
            # Weather friction is applied per-frame in simulation
            pass
        
        return base_friction

    def _simulate(
        self,
        cars: list[Car],
        nets: list,
        genomes: list[DefaultGenome],
        eval_data: list[CarEvaluationData],
    ) -> None:
        """Run physics simulation."""
        import random
        
        pygame.init()
        screen = pygame.display.set_mode(
            (self.settings.simulation.width, self.settings.simulation.height)
        )
        camera = Camera(self.settings.simulation.world_size, self.settings.simulation.world_size)
        camera.set_viewport(self.settings.simulation.width, self.settings.simulation.height)
        
        # Load sprites for all cars (after pygame init)
        for car in cars:
            car.load_sprites(self.settings.paths.assets_dir)
        
        # Initialize camera to center on starting position (prevent off-screen start)
        if cars:
            start_x = -cars[0].position.x + self.settings.simulation.width / 2
            start_y = -cars[0].position.y + self.settings.simulation.height / 2
            # Clamp to world bounds
            start_x = min(0, max(-(self.settings.simulation.world_size - self.settings.simulation.width), start_x))
            start_y = min(0, max(-(self.settings.simulation.world_size - self.settings.simulation.height), start_y))
            camera.exact_x = start_x
            camera.exact_y = start_y
        
        # Determine recording
        is_first = self.generation == self.start_gen + 1
        is_milestone = self.generation % 10 == 0
        is_last = self.generation >= self.final_gen
        should_record = is_first or is_milestone or is_last
        
        writer = None
        if should_record:
            video_path = self.settings.paths.clips_dir / f"gen_{self.generation:05d}.mp4"
            writer = imageio.get_writer(video_path, fps=Video.OUTPUT_FPS)
        
        # Ghost recording
        if self.flags.enable_ghost_cars:
            self.ghost_recorder.start()
        
        max_frames = (
            self.settings.simulation.max_frames_pro
            if is_last
            else self.settings.simulation.max_frames_training
        )
        
        # Initialize sensors
        for car in cars:
            car.check_radar(self.map_mask)
        
        try:
            frame_count = 0
            fps_clock = pygame.time.Clock()
            fps_target = Video.OUTPUT_FPS
            
            while frame_count < max_frames and any(c.alive for c in cars):
                frame_count += 1
                
                # Frame rate limiting
                fps_clock.tick(fps_target)
                
                # Update weather
                if self.flags.enable_weather:
                    self.weather.update()
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                
                # Find leader
                alive_cars = [c for c in cars if c.alive]
                if alive_cars:
                    leader = max(
                        alive_cars,
                        key=lambda c: c.gates_passed * 1000 + c.distance_traveled
                    )
                    camera.update(leader)
                    for c in cars:
                        c.is_leader = (c == leader)
                    
                    # Record ghost from leader
                    if self.flags.enable_ghost_cars and leader.is_leader:
                        self.ghost_recorder.record(leader, frame_count)
                
                # Update ghost
                if self.current_ghost:
                    self.current_ghost.update()
                
                # Update each car
                for i, car in enumerate(cars):
                    if not car.alive:
                        continue
                    
                    data = eval_data[i]
                    
                    # Apply weather friction
                    if self.flags.enable_weather:
                        weather_friction = self.weather.get_friction_at(
                            car.position.x, car.position.y
                        )
                        car.friction = weather_friction
                    
                    # Get AI inputs
                    radar_inputs = (
                        [d[1] / 300.0 for d in car.radars]
                        if len(car.radars) >= 5
                        else [0.0] * 5
                    )
                    gps_inputs = car.get_data(self.checkpoints)
                    inputs = radar_inputs + gps_inputs
                    
                    # Activate network
                    output = nets[i].activate(inputs)
                    
                    # Track steering for smoothness
                    prev_steering = car.steering
                    
                    # Apply controls
                    if output[0] > 0.5:
                        car.input_steer(right=True)
                    elif output[0] < -0.5:
                        car.input_steer(left=True)
                    
                    # Track steering changes
                    if car.steering != prev_steering:
                        data.steering_changes += 1
                    data.total_steering += abs(car.steering)
                    
                    car.input_gas()
                    car.update(self.map_mask)
                    car.check_radar(self.map_mask)
                    
                    # Update evaluation data
                    data.distance = car.distance_traveled
                    data.gates = car.gates_passed
                    data.lap_time = frame_count
                    
                    if data.last_position:
                        dx = car.position.x - data.last_position[0]
                        dy = car.position.y - data.last_position[1]
                        data.path_length += (dx ** 2 + dy ** 2) ** 0.5
                    data.last_position = (car.position.x, car.position.y)
                    
                    # Score fitness (base)
                    if car.check_gates(self.checkpoints):
                        genomes[i].fitness += Fitness.GATE_PASS_BONUS
                    
                    if car.gates_passed >= len(self.checkpoints):
                        genomes[i].fitness += Fitness.LAP_COMPLETE_BONUS
                    
                    dist_score = 1.0 - gps_inputs[1]
                    genomes[i].fitness += dist_score * Fitness.DISTANCE_WEIGHT
                    
                    # Multi-objective bonuses
                    if self.flags.enable_multi_objective:
                        # Center bonus
                        if len(car.radars) >= 5:
                            left_dist = car.radars[0][1]
                            right_dist = car.radars[4][1]
                            center_ratio = 1.0 - abs(left_dist - right_dist) / 300.0
                            center_ratio = max(0, center_ratio)
                            genomes[i].fitness += center_ratio * 0.1
                        
                        # Smoothness bonus (applied at end)
                        pass
                    
                    # Penalties
                    if not car.alive:
                        genomes[i].fitness -= Fitness.DEATH_PENALTY
                        
                        # Log crash for heatmap
                        if self.flags.enable_detailed_metrics:
                            self.tracker.log_crash(
                                car.position.x,
                                car.position.y,
                                "wall" if car.distance_traveled > 100 else "early_crash",
                                genomes[i].fitness
                            )
                        
                        if car.distance_traveled < Fitness.MIN_DISTANCE_FOR_EARLY_DEATH:
                            genomes[i].fitness -= Fitness.EARLY_DEATH_PENALTY
                    
                    if not car.alive and car.frames_since_gate > Fitness.MAX_FRAMES_STUCK:
                        genomes[i].fitness -= Fitness.STUCK_PENALTY
                
                # Handle collisions (only between alive cars)
                alive_cars_for_collision = [c for c in cars if c and c.alive]
                for car in alive_cars_for_collision:
                    car.handle_car_collision(alive_cars_for_collision)
                
                # Mark dead cars for removal from active simulation
                # (Don't remove from list to avoid index issues - just filter when iterating)
                
                # Render
                should_render = should_record or frame_count % Video.RECORD_EVERY_N_FRAMES == 0
                if should_render:
                    bg_color = self._get_bg_color()
                    screen.fill(bg_color)
                    screen.blit(self.visual_map, (camera.camera.x, camera.camera.y))
                    
                    # Draw weather effects
                    if self.flags.enable_weather and self.weather.current:
                        self.weather_effects.update(screen.get_width(), screen.get_height())
                        if self.weather.current.weather_type.value in [3, 4]:  # LIGHT_RAIN, HEAVY_RAIN
                            self.weather_effects.draw_rain(screen, self.weather.current.intensity)
                        if self.weather.current.weather_type.value == 5:  # FOG
                            self.weather_effects.draw_fog(screen, self.weather.current.visibility)
                    
                    # Draw ghost
                    if self.current_ghost:
                        self.current_ghost.draw(screen, camera)
                    
                    # Draw cars
                    for car in cars:
                        if car:
                            car.draw(screen, camera)
                    
                    # HUD
                    font = pygame.font.SysFont("consolas", 40, bold=True)
                    seconds = int(frame_count / Video.OUTPUT_FPS)
                    time_text = font.render(f"{seconds}s", True, (255, 255, 255))
                    gen_text = font.render(f"GEN {self.generation}", True, (200, 0, 0))
                    
                    # Weather indicator
                    if self.flags.enable_weather and self.weather.current:
                        weather_text = font.render(
                            self.weather.get_weather_name(),
                            True,
                            (100, 200, 255)
                        )
                        screen.blit(weather_text, (20, 100))
                    
                    # Curriculum indicator
                    if self.flags.enable_curriculum:
                        curr_text = font.render(
                            f"Level: {self.curriculum.get_difficulty_name()}",
                            True,
                            (255, 200, 100)
                        )
                        screen.blit(curr_text, (20, 140))
                    
                    screen.blit(time_text, (20, 60))
                    screen.blit(gen_text, (20, 20))
                    
                    pygame.display.flip()
                    
                    # Capture
                    if writer:
                        try:
                            pixels = pygame.surfarray.array3d(screen)
                            pixels = np.transpose(pixels, (1, 0, 2))
                            writer.append_data(pixels)
                        except Exception as e:
                            logger.warning("frame_capture_failed", error=str(e))
                
                # Track simulation progress
                if frame_count % 100 == 0:
                    self.tracker.log_simulation_step(len(cars), frame_count)
            
            # Apply multi-objective bonuses at end
            if self.flags.enable_multi_objective:
                for i, data in enumerate(eval_data):
                    if i < len(genomes):
                        # Smoothness bonus
                        genomes[i].fitness += data.smoothness * 100
                        
                        # Efficiency bonus
                        genomes[i].fitness += data.efficiency * 50
            
            # Save ghost from best performer
            if self.flags.enable_ghost_cars and eval_data:
                best_idx = max(range(len(eval_data)), key=lambda i: eval_data[i].distance)
                if best_idx < len(genomes):
                    ghost_frames = self.ghost_recorder.stop()
                    if ghost_frames:
                        self.ghost_recorder.save(
                            self.generation,
                            genomes[best_idx].fitness
                        )
        
        finally:
            if writer:
                writer.close()
            pygame.quit()
