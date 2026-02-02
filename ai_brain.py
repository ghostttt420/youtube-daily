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

# CONFIG
DAILY_GENERATIONS = 20  
VIDEO_OUTPUT_DIR = "training_clips"
FPS = 30 
MAX_FRAMES_PRO = 1800  # 60s for pro showcase
MAX_FRAMES_TRAINING = 450  # 15s for training clips

if not os.path.exists(VIDEO_OUTPUT_DIR): os.makedirs(VIDEO_OUTPUT_DIR)

try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {"map_seed": 42}

def create_config_file():
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
    with open("config.txt", "w") as f:
        f.write(config_content)

def run_dummy_generation():
    checkpoints = glob.glob("neat-checkpoint-*")
    if len(checkpoints) > 0:
        return

    print("\n--- 🤡 Running Dummy Gen 0 (Fresh Start) ---")
    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    map_gen = simulation.TrackGenerator(seed=THEME["map_seed"])
    start_pos, track_surface, visual_map, checkpoints, start_angle = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    cars = [simulation.Car(start_pos, start_angle) for _ in range(80)]
    
    video_path = os.path.join(VIDEO_OUTPUT_DIR, "gen_00000.mp4")
    writer = imageio.get_writer(video_path, fps=FPS)

    running = True
    frame_count = 0
    while running and frame_count <= 900:  # 30 seconds regardless of cars dying
        frame_count += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()
        
        # Update camera with leader if any cars alive
        alive_cars = [c for c in cars if c.alive]
        if alive_cars:
            leader = max(alive_cars, key=lambda c: c.distance_traveled)
            camera.update(leader)
            for c in cars: c.is_leader = (c == leader)
        
        for car in cars:
            if not car.alive: continue
            # Random steering for Gen 0 (original behavior)
            if random.random() < 0.1: 
                car.steering = random.choice([-1, 0, 1])
            car.input_gas()
            car.update(map_mask, cars)
        
        screen.fill(simulation.COL_BG)
        screen.blit(visual_map, (camera.camera.x, camera.camera.y))
        for car in cars: car.draw(screen, camera)
        simulation.draw_text_with_outline(screen, "GEN 0 (NOOB)", (20, 20), size=40, color=simulation.COL_WALL)
        pygame.display.flip()
        
        try:
            pixels = pygame.surfarray.array3d(screen)
            pixels = np.transpose(pixels, (1, 0, 2))
            writer.append_data(pixels)
        except: pass
    
    writer.close()
    print("✅ Gen 0 Saved.")

START_GEN = 0
FINAL_GEN = 0

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n--- 🏁 Gen {GENERATION} ---")

    nets = []
    cars = []
    ge = []

    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    map_gen = simulation.TrackGenerator(seed=THEME["map_seed"])
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
    
    # Record EVERY generation for daily compilation
    should_record = True
    
    if should_record:
        filename = f"gen_{GENERATION:05d}.mp4"
        video_path = os.path.join(VIDEO_OUTPUT_DIR, filename)
        print(f"🎥 Recording Gen {GENERATION}...")
        writer = imageio.get_writer(video_path, fps=FPS)

    running = True
    frame_count = 0
    for car in cars: car.check_radar(map_mask)
    
    # All clips are 30 seconds now
    current_max_frames = MAX_FRAMES_TRAINING

    while running and frame_count <= current_max_frames:
        frame_count += 1
        if frame_count > current_max_frames: break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

        # Handle case where all cars are dead but we still need to record
        if len(cars) > 0:
            leader = max(cars, key=lambda c: c.gates_passed * 1000 + c.distance_traveled)
            camera.update(leader)
            for c in cars: c.is_leader = (c == leader)

        for i, car in enumerate(cars):
            if not car.alive: continue
            
            gps = car.get_data(checkpoints)
            heading_error = gps[0]  # -1 to 1, negative = checkpoint left, positive = right
            
            if len(car.radars) < 5: 
                radar_inputs = [0] * 5
            else: 
                radar_inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]
            
            # Build inputs for NEAT
            inputs = radar_inputs + gps
            output = nets[i].activate(inputs)
            
            # For trained generations (50+), use pure NEAT output
            # For early gens, blend with checkpoint steering
            neat_steering = output[0]
            
            # Hybrid driving: NEAT + hardcoded track following
            # Works on ANY track shape (adapts to different seeds)
            neat_steering = output[0]
            heading_error = gps[0]  # -1 to 1, negative = checkpoint is left
            
            # Hardcoded: steer toward checkpoint (keeps car on track)
            checkpoint_steering = -heading_error
            
            # Blend varies by generation for evolution effect:
            # - Learning/Training: More checkpoint following (stays on track)
            # - Pro: More NEAT (smooth but still track-aware)
            if GENERATION <= 20:
                blend = 0.7  # 70% checkpoint, 30% NEAT
            else:
                blend = 0.4  # 40% checkpoint, 60% NEAT (pro is smoother)
            
            final_steering = checkpoint_steering * blend + neat_steering * (1 - blend)
            
            # Apply steering
            if final_steering > 0.3:
                car.input_steer(right=True)
            elif final_steering < -0.3:
                car.input_steer(left=True)
            
            car.input_gas()
            car.update(map_mask, cars)
            car.check_radar(map_mask)
            
            if car.check_gates(checkpoints):
                ge[i].fitness += 1000  # Major reward for passing gates
                # Pro bonus: maintain speed through gates (pros don't slow down)
                speed_ratio = car.velocity.length() / car.max_speed
                ge[i].fitness += speed_ratio * 200  # Up to 200 bonus for full speed
            
            if car.gates_passed >= len(checkpoints):
                ge[i].fitness += 5000  # Big lap completion bonus
            
            # Distance to next gate (closer = better)
            dist_score = max(0, 1.0 - gps[1])
            ge[i].fitness += dist_score * 2.0
            
            # Pro: Smooth steering (pros drive smoothly, not jerky)
            if not hasattr(car, 'prev_steering'):
                car.prev_steering = 0
            steering_change = abs(car.steering - car.prev_steering)
            if steering_change < 0.15:  # Very smooth
                ge[i].fitness += 2.0
            elif steering_change < 0.3:  # Moderately smooth
                ge[i].fitness += 0.5
            car.prev_steering = car.steering
            
            # Pro: Speed reward (pros go fast)
            speed_ratio = car.velocity.length() / car.max_speed
            ge[i].fitness += speed_ratio * 3.0  # Reward for being fast
            
            # Survival bonus
            ge[i].fitness += 1.0

            if not car.alive:
                 ge[i].fitness -= 500  # Harsh penalty for dying

        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if should_record:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            for car in cars: car.draw(screen, camera)
            
            seconds = int(frame_count / FPS)
            simulation.draw_text_with_outline(screen, f"GEN {GENERATION}", (20, 20), size=40, color=simulation.COL_WALL)
            simulation.draw_text_with_outline(screen, f"{seconds}s", (20, 70), size=40)
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
    
    for f in glob.glob(os.path.join(VIDEO_OUTPUT_DIR, "*.mp4")):
        try: os.remove(f)
        except: pass
    
    checkpoints = [f for f in os.listdir(".") if f.startswith("neat-checkpoint-")]
    
    if checkpoints:
        latest = sorted(checkpoints, key=lambda x: int(x.split('-')[2]))[-1]
        print(f"🧠 RESTORING SUPER-BRAIN FROM: {latest}")
        START_GEN = int(latest.split('-')[2])
        GENERATION = START_GEN
        p = neat.Checkpointer.restore_checkpoint(latest)
    else:
        print("👶 NO BRAIN FOUND. BIRTH OF A NEW SPECIES.")
        run_dummy_generation()
        START_GEN = 0
        GENERATION = 0
        config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                    neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                    config_path)
        p = neat.Population(config)

    FINAL_GEN = START_GEN + DAILY_GENERATIONS
    print(f"🎯 MISSION: Evolve from Gen {START_GEN} -> Gen {FINAL_GEN}")

    p.add_reporter(neat.StdOutReporter(True))
    p.add_reporter(neat.Checkpointer(generation_interval=5, filename_prefix="neat-checkpoint-"))
    
    p.run(run_simulation, DAILY_GENERATIONS)

if __name__ == "__main__":
    create_config_file()
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
