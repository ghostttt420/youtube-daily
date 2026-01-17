import os
# --- HEADLESS SERVER FIXES ---
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys
import pickle
import imageio
import numpy as np
import neat
import pygame
import simulation  # Imports your physics engine

# --- CONFIG ---
GENERATION = 0
MAX_GENERATIONS = 30  # Reduced to 30 to run faster on GitHub
RECORD_GENS = [1, 5, 10, 20, 29] # Gens to save
VIDEO_OUTPUT_DIR = "training_clips"

# STRICT SHORTS LIMITS
FPS = 30 
MAX_VIDEO_DURATION = 58 # Seconds
MAX_FRAMES = FPS * MAX_VIDEO_DURATION

if not os.path.exists(VIDEO_OUTPUT_DIR): 
    os.makedirs(VIDEO_OUTPUT_DIR)

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n--- 🏁 Gen {GENERATION} Start ---")

    nets = []
    cars = []
    ge = []

    # Setup Environment
    pygame.init()
    # Force 1080x1920 (Vertical)
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    # Generate Map
    map_gen = simulation.TrackGenerator(seed=42)
    start_pos, track_surface, visual_map = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)

    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    # Spawn AI
    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos)) 
        g.fitness = 0
        ge.append(g)

    # Video Recording Setup
    writer = None
    # Save as "gen_X.mp4" so final_render.py can find it
    video_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
    
    # Check if we should record this generation
    should_record = (GENERATION in RECORD_GENS)
    
    if should_record:
        print(f"🎥 Recording Gen {GENERATION} to {video_path}...")
        writer = imageio.get_writer(video_path, fps=FPS)

    # Race Loop
    running = True
    frame_count = 0
    
    # Pre-calc radars
    for car in cars: car.check_radar(map_mask)

    while running and len(cars) > 0:
        frame_count += 1
        
        # 1. SHORTS TIME LIMIT
        if frame_count > MAX_FRAMES:
            print("⏱️ CUT! Max Short duration reached.")
            break

        # 2. Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

        # 3. Camera Logic
        leader = max(cars, key=lambda c: c.distance_traveled)
        camera.update(leader)
        for c in cars: c.is_leader = (c == leader)

        # 4. AI Logic
        for i, car in enumerate(cars):
            if not car.alive: continue
            
            # Inputs
            if len(car.radars) < 5: inputs = [0] * 5
            else: inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]

            # Decision
            output = nets[i].activate(inputs)
            
            # Steering
            if output[0] > 0.5: car.input_steer(right=True)
            elif output[0] < -0.5: car.input_steer(left=True)
            
            car.input_gas()
            car.update(map_mask)
            car.check_radar(map_mask)
            
            # Fitness
            ge[i].fitness += car.velocity.length()
            if car.velocity.length() < 1: ge[i].fitness -= 2

        # 5. Cleanup Dead
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 10
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        # 6. Render
        if should_record or frame_count % 10 == 0:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            
            for car in cars:
                car.draw(screen, camera)
            
            # HUD
            font = pygame.font.SysFont("consolas", 40, bold=True)
            seconds = int(frame_count / FPS)
            time_lbl = font.render(f"{seconds}s / 58s", True, (255, 255, 255))
            gen_lbl = font.render(f"GEN {GENERATION}", True, simulation.COL_WALL)
            
            screen.blit(gen_lbl, (20, 20))
            screen.blit(time_lbl, (20, 60))
            
            pygame.display.flip()

            # Capture Frame
            if writer:
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except Exception as e:
                    print(f"Frame Error: {e}")

    # End Generation
    if writer:
        writer.close()
        print(f"✅ Saved: {video_path}")
        # Note: We do NOT delete the file anymore. final_render.py needs it.

def run_neat(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    
    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    
    # We only run 30 gens to keep it within GitHub Actions time limits
    p.run(run_simulation, MAX_GENERATIONS)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
