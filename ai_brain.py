import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys
import glob
import pickle
import imageio
import numpy as np
import neat
import pygame
import json
import random
import simulation 
from challenge_loader import ChallengeLoader

# CONFIG
DAILY_GENERATIONS = 50  # Increased from 20
VIDEO_OUTPUT_DIR = "training_clips"
FPS = 30 
MAX_FRAMES_PRO = 3600  # 2 minutes for final showcase
MAX_FRAMES_TRAINING = 900  # 30 seconds for training clips (up from 450)

if not os.path.exists(VIDEO_OUTPUT_DIR): os.makedirs(VIDEO_OUTPUT_DIR)

# Load challenges
challenge_loader = ChallengeLoader()

try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {"map_seed": 42}

def create_config_file():
    # --- ENHANCED CONFIG FOR BETTER LEARNING ---
    config_content = """
[NEAT]
fitness_criterion     = max
fitness_threshold     = 100000
pop_size              = 80
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
max_stagnation       = 30
species_elitism      = 2

[DefaultReproduction]
elitism            = 4
survival_threshold = 0.2
min_species_size   = 2
    """
    with open("config.txt", "w") as f:
        f.write(config_content)

def run_dummy_generation():
    # Only run this if we are starting from SCRATCH (Gen 0)
    checkpoints = glob.glob("neat-checkpoint-*")
    if len(checkpoints) > 0:
        return

    print("\n--- 🤡 Running Dummy Gen 0 (Fresh Start) ---")
    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))

    map_gen = simulation.TrackGenerator(seed=THEME["map_seed"])
    start_pos, track_surface, visual_map, checkpoints_map, start_angle = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    cars = [simulation.Car(start_pos, start_angle) for _ in range(80)]

    video_path = os.path.join(VIDEO_OUTPUT_DIR, "gen_00000.mp4")
    writer = imageio.get_writer(video_path, fps=FPS)

    running = True
    frame_count = 0
    while running and len(cars) > 0:
        frame_count += 1
        if frame_count > 300: break 
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()
        alive_cars = [c for c in cars if c.alive]
        if not alive_cars: break
        leader = max(alive_cars, key=lambda c: c.distance_traveled)
        camera.update(leader)
        for c in cars: c.is_leader = (c == leader)
        for car in cars:
            if not car.alive: continue
            if random.random() < 0.1: car.steering = random.choice([-1, 0, 1])
            car.input_gas()
            car.update(map_mask)
        screen.fill(simulation.COL_BG)
        screen.blit(visual_map, (camera.camera.x, camera.camera.y))
        for car in cars: car.draw(screen, camera)
        
        simulation.draw_text_with_outline(screen, "GEN 0: NOOBS", (20, 20), size=100, color=(255, 50, 50))
        
        pygame.display.flip()
        try:
            pixels = pygame.surfarray.array3d(screen)
            pixels = np.transpose(pixels, (1, 0, 2))
            writer.append_data(pixels)
        except: pass
    writer.close()
    print("✅ Gen 0 Saved.")

# Global to track start/end for this session
START_GEN = 0
FINAL_GEN = 0
GENERATION = 0

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    
    # Check if we need to switch challenges
    if challenge_loader.should_switch_challenge(GENERATION):
        next_challenge = challenge_loader.switch_to_next_challenge(GENERATION)
        if next_challenge:
            challenge_loader.apply_challenge_config(next_challenge)
            # Reload theme after applying new challenge
            with open("theme.json", "r") as f:
                global THEME
                THEME = json.load(f)
    
    # Get current challenge info
    active_challenge = challenge_loader.get_active_challenge()
    challenge_name = active_challenge['name'] if active_challenge else None
    
    print(f"\n--- 🏁 Gen {GENERATION} {f'({challenge_name})' if challenge_name else ''} ---")

    nets = []
    cars = []
    ge = []

    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))

    map_gen = simulation.TrackGenerator()
    start_pos, track_surface, visual_map, checkpoints, start_angle = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos, start_angle)) 
        g.fitness = 0
        ge.append(g)

    writer = None

    # RECORDING LOGIC:
    # 1. First gen of new challenge (the struggle)
    # 2. Every 50 gens (milestones)
    # 3. Last 5 gens of challenge (the mastery)
    
    is_challenge_start = False
    is_challenge_end = False
    
    if active_challenge:
        is_challenge_start = (GENERATION == active_challenge['start_gen'])
        is_challenge_end = (GENERATION >= active_challenge['target_gen'] - 5)
    
    is_milestone = (GENERATION % 50 == 0)
    
    should_record = is_challenge_start or is_milestone or is_challenge_end

    if should_record:
        filename = f"gen_{GENERATION:05d}.mp4"
        video_path = os.path.join(VIDEO_OUTPUT_DIR, filename)
        print(f"🎥 Recording Gen {GENERATION}...")
        writer = imageio.get_writer(video_path, fps=FPS)

    running = True
    frame_count = 0
    for car in cars: car.check_radar(map_mask)

    # Give more time for end-of-challenge runs
    current_max_frames = MAX_FRAMES_PRO if is_challenge_end else MAX_FRAMES_TRAINING

    while running and len(cars) > 0:
        frame_count += 1
        if frame_count > current_max_frames: break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

        leader = max(cars, key=lambda c: c.gates_passed * 1000 + c.distance_traveled)
        camera.update(leader)
        for c in cars: c.is_leader = (c == leader)

        for i, car in enumerate(cars):
            if not car.alive: continue

            if len(car.radars) < 5: inputs = [0] * 5
            else: inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]
            gps = car.get_data(checkpoints)
            inputs.extend(gps)

            output = nets[i].activate(inputs)
            if output[0] > 0.5: car.input_steer(right=True)
            elif output[0] < -0.5: car.input_steer(left=True)

            car.input_gas()
            car.update(map_mask)
            car.check_radar(map_mask)

            # ENHANCED FITNESS FUNCTION
            if car.check_gates(checkpoints):
                ge[i].fitness += 500  # Big reward for gates (up from 200)

            # Reward staying alive
            if car.alive:
                ge[i].fitness += 1.5

            # Reward speed
            speed_bonus = car.velocity.length() / car.max_speed
            ge[i].fitness += speed_bonus * 0.8  # Up from 0.05

            # Distance to next gate (closer = better)
            dist_score = 1.0 - gps[1] 
            ge[i].fitness += dist_score * 0.1

            # HARSH death penalty
            if not car.alive:
                ge[i].fitness -= 200  # Up from 50

            # Stuck penalty
            if not car.alive and car.frames_since_gate > 100:
                ge[i].fitness -= 50

            # HUGE bonus for completing laps
            if car.gates_passed >= len(checkpoints):
                ge[i].fitness += 3000  # Massive lap completion bonus

        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if should_record or frame_count % 10 == 0:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            for car in cars: car.draw(screen, camera)

            # Use new HUD
            simulation.draw_hud(screen, leader, GENERATION, frame_count, checkpoints, challenge_name)
            
            pygame.display.flip()

            if writer:
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except: pass

    if writer: writer.close()

def run_neat(config_path):
    global GENERATION, START_GEN, FINAL_GEN

    # 1. Clear OLD clips
    for f in glob.glob(os.path.join(VIDEO_OUTPUT_DIR, "*.mp4")):
        try: os.remove(f)
        except: pass

    # 2. Check for brain history
    checkpoints = [f for f in os.listdir(".") if f.startswith("neat-checkpoint-")]

    if checkpoints:
        latest = sorted(checkpoints, key=lambda x: int(x.split('-')[2]))[-1]
        print(f"🧠 RESTORING BRAIN FROM: {latest}")

        START_GEN = int(latest.split('-')[2])
        GENERATION = START_GEN

        p = neat.Checkpointer.restore_checkpoint(latest)
        
        # Apply current challenge config
        active_challenge = challenge_loader.get_active_challenge()
        if active_challenge:
            print(f"🎮 ACTIVE CHALLENGE: {active_challenge['name']}")
            print(f"📊 Progress: Gen {GENERATION} / {active_challenge['target_gen']}")
            challenge_loader.apply_challenge_config(active_challenge)
    else:
        print("👶 NO BRAIN FOUND. STARTING FROM GEN 0.")
        
        # Apply first challenge config
        active_challenge = challenge_loader.get_active_challenge()
        if active_challenge:
            print(f"🎯 FIRST CHALLENGE: {active_challenge['name']}")
            challenge_loader.apply_challenge_config(active_challenge)
        
        run_dummy_generation()
        START_GEN = 0
        GENERATION = 0
        config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                    neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                    config_path)
        p = neat.Population(config)

    # 3. Set Goals
    FINAL_GEN = START_GEN + DAILY_GENERATIONS
    print(f"🎯 SESSION: Gen {START_GEN} → Gen {FINAL_GEN}")

    # 4. Run
    p.add_reporter(neat.StdOutReporter(True))
    p.add_reporter(neat.Checkpointer(generation_interval=5, filename_prefix="neat-checkpoint-"))

    p.run(run_simulation, DAILY_GENERATIONS)

if __name__ == "__main__":
    create_config_file()
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)