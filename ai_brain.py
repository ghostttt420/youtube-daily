import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys
import pickle
import imageio
import numpy as np
import neat
import pygame
import json
import random
import simulation 

# CONFIG
MAX_GENERATIONS = 30
VIDEO_OUTPUT_DIR = "training_clips"
FPS = 30 
# We'll only record Gen 0 (fail) and the final generation (success)
MAX_FRAMES = FPS * 120 # Allow pro run to be longer

if not os.path.exists(VIDEO_OUTPUT_DIR): os.makedirs(VIDEO_OUTPUT_DIR)

# LOAD THEME
try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {"map_seed": 42}

def run_dummy_generation():
    """Runs a 'Gen 0' with completely random actions."""
    print("\n--- 🤡 Running Dummy Gen 0 (For Content) ---")
    
    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    map_gen = simulation.TrackGenerator(seed=THEME["map_seed"])
    start_pos, track_surface, visual_map = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    cars = [simulation.Car(start_pos) for _ in range(20)]
    
    video_path = os.path.join(VIDEO_OUTPUT_DIR, "gen_0.mp4")
    writer = imageio.get_writer(video_path, fps=FPS)
    print(f"🎥 Recording Gen 0 to {video_path}...")

    running = True
    frame_count = 0
    
    # Dumb Loop
    while running and len(cars) > 0:
        frame_count += 1
        if frame_count > 300: break # 10s limit for fail clip

        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

        alive_cars = [c for c in cars if c.alive]
        if not alive_cars: break
        
        leader = max(alive_cars, key=lambda c: c.distance_traveled)
        camera.update(leader)
        for c in cars: c.is_leader = (c == leader)

        for car in cars:
            if not car.alive: continue
            # RANDOM ACTIONS (The "Noob" Logic)
            if random.random() < 0.1:
                car.steering = random.choice([-1, 0, 1])
            car.input_gas()
            car.update(map_mask)
            
        screen.fill(simulation.COL_BG)
        screen.blit(visual_map, (camera.camera.x, camera.camera.y))
        for car in cars: car.draw(screen, camera)
        
        font = pygame.font.SysFont("consolas", 40, bold=True)
        screen.blit(font.render("GEN 0 (NOOB)", True, simulation.COL_WALL), (20, 20))
        pygame.display.flip()

        try:
            pixels = pygame.surfarray.array3d(screen)
            pixels = np.transpose(pixels, (1, 0, 2))
            writer.append_data(pixels)
        except: pass

    writer.close()
    print("✅ Gen 0 Saved.")

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n--- 🏁 Gen {GENERATION} Start ---")

    nets = []
    cars = []
    ge = []

    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    map_gen = simulation.TrackGenerator(seed=THEME["map_seed"])
    start_pos, track_surface, visual_map = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos)) 
        g.fitness = 0
        ge.append(g)

    writer = None
    video_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
    # Only record the FINAL generation
    should_record = (GENERATION == MAX_GENERATIONS)
    
    if should_record:
        print(f"🎥 Recording Gen {GENERATION} (The Pro Run)...")
        writer = imageio.get_writer(video_path, fps=FPS)

    running = True
    frame_count = 0
    for car in cars: car.check_radar(map_mask)

    while running and len(cars) > 0:
        frame_count += 1
        if frame_count > MAX_FRAMES: break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

        leader = max(cars, key=lambda c: c.distance_traveled)
        camera.update(leader)
        for c in cars: c.is_leader = (c == leader)

        for i, car in enumerate(cars):
            if not car.alive: continue
            
            if len(car.radars) < 5: inputs = [0] * 5
            else: inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]

            output = nets[i].activate(inputs)
            if output[0] > 0.5: car.input_steer(right=True)
            elif output[0] < -0.5: car.input_steer(left=True)
            
            car.input_gas()
            car.update(map_mask)
            car.check_radar(map_mask)
            
            ge[i].fitness += car.velocity.length()
            if car.velocity.length() < 1: ge[i].fitness -= 2

        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 10
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if should_record or frame_count % 10 == 0:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            for car in cars: car.draw(screen, camera)
            
            font = pygame.font.SysFont("consolas", 40, bold=True)
            seconds = int(frame_count / FPS)
            screen.blit(font.render(f"{seconds}s / {int(MAX_FRAMES/FPS)}s", True, (255, 255, 255)), (20, 60))
            screen.blit(font.render(f"GEN {GENERATION}", True, simulation.COL_WALL), (20, 20))
            pygame.display.flip()

            if writer:
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except: pass

    if writer: writer.close()

def run_neat(config_path):
    global GENERATION
    GENERATION = 0
    
    # 1. RUN THE DUMMY GEN
    run_dummy_generation()
    
    # 2. RUN REAL EVOLUTION
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    
    checkpoints = [f for f in os.listdir(".") if f.startswith("neat-checkpoint-")]
    if checkpoints:
        latest = sorted(checkpoints, key=lambda x: int(x.split('-')[2]))[-1]
        print(f"🔄 RESTORING EVOLUTION FROM: {latest}")
        p = neat.Checkpointer.restore_checkpoint(latest)
    else:
        print("👶 NO BRAIN FOUND. STARTING FRESH.")
        p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    p.add_reporter(neat.Checkpointer(generation_interval=5, filename_prefix="neat-checkpoint-"))
    
    p.run(run_simulation, MAX_GENERATIONS)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
