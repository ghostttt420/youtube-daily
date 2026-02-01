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
from themes import ThemeManager

# CONFIG
DAILY_GENERATIONS = 50  # Increased from 20
VIDEO_OUTPUT_DIR = "training_clips"
FPS = 30 
MAX_FRAMES_PRO = 900  # 30 seconds for pro level showcase (30s * 30fps)
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
    start_pos, track_surface, visual_map, checkpoints_map, start_angle, wall_mask = map_gen.generate_track()
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
            car.update(map_mask, cars, wall_mask)  # Pass cars and wall_mask for collision detection
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

def draw_basic_hud(screen, leader, generation, frame_count, checkpoints, challenge_name):
    """Simple fallback HUD when the main one fails."""
    font = pygame.font.Font(None, 36)
    
    # Draw generation and challenge info
    gen_text = font.render(f"Gen {generation}: {challenge_name or 'Training'}", True, (255, 255, 255))
    screen.blit(gen_text, (20, 20))
    
    # Draw gates info
    gates_text = font.render(f"Gates: {leader.gates_passed}/{len(checkpoints)}", True, (255, 255, 255))
    screen.blit(gates_text, (20, 60))
    
    # Draw distance
    dist_text = font.render(f"Distance: {int(leader.distance_traveled)}", True, (255, 255, 255))
    screen.blit(dist_text, (20, 100))
    
    # Draw frame count
    frame_text = font.render(f"Frame: {frame_count}", True, (255, 255, 255))
    screen.blit(frame_text, (20, 140))
    
    # Draw simple fitness indicator (use gates * 100 + distance as proxy)
    fitness_bar_width = 200
    estimated_fitness = leader.gates_passed * 500 + leader.distance_traveled * 0.1
    fitness_fill = min(estimated_fitness / 10, fitness_bar_width)  # Scale to bar width
    pygame.draw.rect(screen, (100, 100, 100), (20, 180, fitness_bar_width, 20))
    pygame.draw.rect(screen, (0, 255, 0), (20, 180, int(fitness_fill), 20))
    
    fitness_text = font.render(f"Est. Fitness: {int(estimated_fitness)}", True, (255, 255, 255))
    screen.blit(fitness_text, (20, 210))

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    
    # Check if we need to switch challenges
    if challenge_loader.should_switch_challenge(GENERATION):
        next_challenge = challenge_loader.switch_to_next_challenge(GENERATION)
        if next_challenge:
            challenge_loader.apply_challenge_config(next_challenge)
    
    # Rotate visual theme every 7 days to keep content fresh
    theme_manager = ThemeManager()
    current_day = GENERATION  # Use generation as day counter
    theme = theme_manager.get_theme_for_day(current_day)
    theme_manager.apply_theme_to_config(theme)
    
    # Reload theme after potential changes
    with open("theme.json", "r") as f:
        global THEME
        THEME = json.load(f)
        simulation.THEME = THEME  # Update simulation module too
        # Reload colors
        simulation.COL_BG = tuple(THEME["visuals"]["bg"])
        simulation.COL_WALL = tuple(THEME["visuals"]["wall"])
        simulation.COL_ROAD = tuple(THEME["visuals"]["road"])
        simulation.COL_CENTER = tuple(THEME["visuals"]["center"])
    
    # Get current challenge info
    active_challenge = challenge_loader.get_active_challenge()
    challenge_name = active_challenge['name'] if active_challenge else None
    
    print(f"\n--- 🏁 Gen {GENERATION} {f'({challenge_name})' if challenge_name else ''} ---")
    if theme:
        print(f"🎨 Theme: {theme['name']}")

    nets = []
    cars = []
    ge = []

    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))

    map_gen = simulation.TrackGenerator()
    start_pos, track_surface, visual_map, checkpoints, start_angle, wall_mask = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos, start_angle)) 
        g.fitness = 0
        ge.append(g)

    writer = None
    video_path = None

    # RECORDING LOGIC
    is_challenge_start = False
    is_challenge_end = False
    
    if active_challenge:
        is_challenge_start = (active_challenge['start_gen'] <= GENERATION <= active_challenge['start_gen'] + 5)
        is_challenge_end = (GENERATION >= active_challenge['target_gen'] - 5)
    
    is_milestone = (GENERATION % 50 == 0)
    # RECORD EVERY GENERATION during daily training for maximum content
    # We'll pick the best 3 for YouTube, rest gets discarded
    is_daily_content = True  # Always record for daily compilation
    should_record = is_challenge_start or is_milestone or is_challenge_end or is_daily_content
    
    # Determine challenge info
    challenge_dir_name = "training"  # fallback directory
    display_name = None  # For HUD - None means show "Training"
    
    if active_challenge:
        challenge_dir_name = active_challenge['name'].lower().replace(" ", "_")
        # Only show challenge name in HUD if we're in the challenge period
        if active_challenge['start_gen'] <= GENERATION <= active_challenge['target_gen']:
            display_name = active_challenge['name']
    
    challenge_dir = os.path.join(VIDEO_OUTPUT_DIR, challenge_dir_name)
    if not os.path.exists(challenge_dir):
        os.makedirs(challenge_dir)
    
    print(f"📹 Recording check - Gen {GENERATION}:")
    if active_challenge:
        print(f"   - Active challenge: {active_challenge['name']}")
        print(f"   - Challenge range: {active_challenge['start_gen']} → {active_challenge['target_gen']}")
    print(f"   - Storage dir: {challenge_dir}")
    print(f"   - Display name: {display_name or 'Training'}")
    print(f"   - Challenge start: {is_challenge_start}")
    print(f"   - Milestone (÷50): {is_milestone}")
    print(f"   - Daily content: {is_daily_content}")
    print(f"   - Challenge end: {is_challenge_end}")
    print(f"   - WILL RECORD: {should_record}")

    if should_record:
        filename = f"gen_{GENERATION:05d}.mp4"
        video_path = os.path.join(challenge_dir, filename)
        print(f"🎥 Recording Gen {GENERATION} to {video_path}...")
        writer = imageio.get_writer(video_path, fps=FPS)
    else:
        print(f"⏭️  Skipping recording for Gen {GENERATION}")

    running = True
    frame_count = 0
    for car in cars: 
        car.check_radar(map_mask)

    current_max_frames = MAX_FRAMES_PRO if is_challenge_end else MAX_FRAMES_TRAINING
    
    # Store last leader position for when all cars die
    last_leader_pos = None
    last_leader_angle = 0

    while running and frame_count <= current_max_frames:
        frame_count += 1
        if frame_count > current_max_frames: 
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: 
                sys.exit()

        # Handle case where all cars are dead but we still need to record
        if len(cars) > 0:
            leader = max(cars, key=lambda c: c.gates_passed * 1000 + c.distance_traveled)
            last_leader_pos = leader.position
            last_leader_angle = leader.angle
            camera.update(leader)
            for c in cars: 
                c.is_leader = (c == leader)

        for i, car in enumerate(cars):
            if not car.alive: 
                continue

            if len(car.radars) < 5: 
                inputs = [0] * 5
            else: 
                inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]
            gps = car.get_data(checkpoints)
            inputs.extend(gps)

            output = nets[i].activate(inputs)
            
            # Gradual steering for smoother control (pro driving)
            steering_value = output[0]
            if steering_value > 0.3:  # Lower threshold for smoother control
                car.input_steer(right=True)
                # Scale steering by output magnitude for finer control
                car.steering = min(steering_value, 1.0)
            elif steering_value < -0.3:
                car.input_steer(left=True)
                car.steering = max(steering_value, -1.0)
            else:
                # Small steering values = near straight (pro keeps line)
                car.steering = steering_value * 0.3  # Gentle correction

            car.input_gas()
            car.update(map_mask, cars, wall_mask)  # Pass cars and wall_mask for collision detection
            car.check_radar(map_mask)

            # === PRO FITNESS FUNCTION ===
            
            # Gate passing - major reward
            if car.check_gates(checkpoints):
                # Bonus for speed at gate (pros maintain speed)
                speed_at_gate = car.velocity.length() / car.max_speed
                gate_bonus = 500 + (speed_at_gate * 200)
                ge[i].fitness += gate_bonus
            
            # Survival bonus (stay alive longer = better) - scaled by time
            if car.alive:
                # Increasing bonus the longer they survive (exponential)
                survival_bonus = 2.0 + (frame_count / 300) * 3.0  # 2.0 to 11.0 over 30s
                ge[i].fitness += survival_bonus
            
            # Speed reward (pros go fast)
            speed_ratio = car.velocity.length() / car.max_speed
            ge[i].fitness += speed_ratio * 1.5  # Increased from 0.8
            
            # PRO: Smooth steering reward (less jittery = more pro)
            # Store previous steering to calculate smoothness
            if not hasattr(car, 'prev_steering'):
                car.prev_steering = 0
            steering_change = abs(car.steering - car.prev_steering)
            if steering_change < 0.3:  # Smooth steering
                ge[i].fitness += 0.5  # Bonus for smoothness
            car.prev_steering = car.steering
            
            # PRO: Distance to next gate (closer = better)
            dist_score = max(0, 1.0 - gps[1])
            ge[i].fitness += dist_score * 0.2
            
            # PRO: Heading alignment (facing the right direction)
            heading_bonus = max(0, 1.0 - abs(gps[0]))  # gps[0] is heading error
            ge[i].fitness += heading_bonus * 0.3
            
            # Death penalty - SEVERE to teach cars to stay alive
            if not car.alive:
                ge[i].fitness -= 1000  # Heavy penalty for dying (was -150)
            
            # Stagnation penalty (not progressing) - more lenient for pro driving
            if car.frames_since_gate > 180:  # 6 seconds instead of 3.3 (was 100)
                ge[i].fitness -= 50  # Increased penalty (was 30)
            
            # Lap completion - massive reward
            if car.gates_passed >= len(checkpoints):
                ge[i].fitness += 5000  # Increased from 3000
                # Extra bonus for completing lap quickly (pro speed)
                ge[i].fitness += speed_ratio * 1000

        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if should_record or frame_count % 10 == 0:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            for car in cars: 
                car.draw(screen, camera)

            try:
                # Use leader if available, otherwise use last known position
                hud_leader = leader if len(cars) > 0 else None
                simulation.draw_hud(screen, hud_leader, GENERATION, frame_count, checkpoints, display_name)
            except Exception as e:
                print(f"⚠️  HUD error: {e}, using simple display")
                font = pygame.font.SysFont("arial", 90, bold=True)
                gen_text = font.render(f"GEN {GENERATION}", True, (255, 255, 255))
                screen.blit(gen_text, (30, 30))
                if challenge_name:
                    font_small = pygame.font.SysFont("arial", 60, bold=True)
                    challenge_text = font_small.render(challenge_name.upper(), True, (255, 200, 0))
                    screen.blit(challenge_text, (30, 140))
            
            pygame.display.flip()

            if writer:
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except: 
                    pass

    if writer: 
        writer.close()
        if video_path:
            print(f"✅ Saved recording: {video_path}")


def run_neat(config_path):
    global GENERATION, START_GEN, FINAL_GEN

    # 1. Ensure training clips directory exists (persistent storage)
    if not os.path.exists(VIDEO_OUTPUT_DIR): 
        os.makedirs(VIDEO_OUTPUT_DIR)

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
