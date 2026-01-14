import pygame
import neat
import os
import sys
import pickle
import simulation  # Uses the High-Effort V2 simulation
import imageio

# --- CONFIG ---
GENERATION = 0
MAX_GENERATIONS = 30
RECORD_GENS = [1, 5, 10, 20, 29]
VIDEO_OUTPUT_DIR = "training_clips"

if not os.path.exists(VIDEO_OUTPUT_DIR):
    os.makedirs(VIDEO_OUTPUT_DIR)

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n ****** Running generation {GENERATION} ****** \n")

    nets = []
    cars = []
    ge = []

    # Headless setup
    pygame.init()
    # Fixed the WIDTH/HEIGHT reference to match simulation.py
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    # 1. Generate Massive Map
    map_gen = simulation.TrackGenerator(seed=101) # Keep seed fixed for consistency
    start_pos, collision_map, visual_map = map_gen.generate_track()
    
    # Collision Mask
    map_mask = pygame.mask.from_surface(collision_map)

    # 2. Camera Setup
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    # 3. Spawn Cars
    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos))
        g.fitness = 0
        ge.append(g)

    # Recorder
    writer = None
    if GENERATION in RECORD_GENS:
        print(f"🎥 Recording Generation {GENERATION}...")
        save_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
        writer = imageio.get_writer(save_path, fps=30)

    # 4. Race Loop
    running = True
    frame_count = 0
    # Increased frame limit to allow cars to finish the huge track
    max_frames = 2000 if GENERATION > 10 else 1000
    
    while running and len(cars) > 0 and frame_count < max_frames:
        frame_count += 1
        
        # --- A. FIND LEADER & UPDATE CAMERA ---
        # Find car with max distance
        leader = max(cars, key=lambda c: c.distance_traveled)
        for c in cars:
            c.is_leader = False
        leader.is_leader = True
        
        camera.update(leader)

        # --- B. AI LOGIC & PHYSICS ---
        for i, car in enumerate(cars):
            ge[i].fitness += 0.1 # Survive reward
            if not car.alive: continue

            # PASS THE ACTUAL MASK for radar
            car.check_radar(map_mask)
            
            # Normalize inputs based on SENSOR_LENGTH
            inputs = [d[1] / float(simulation.SENSOR_LENGTH) for d in car.radars] 
            output = nets[i].activate(inputs)
            
            # Decisions
            if output[0] > 0.5: car.rotate(right=True)
            if output[0] < -0.5: car.rotate(left=True)
            
            car.speed = 12 # Speed boost
            car.update(map_mask)

        # --- C. CLEANUP DEAD CARS ---
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 2.0 # Heavy crash penalty
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if len(cars) == 0: break

        # --- D. RENDER (Cinematic) ---
        screen.fill(simulation.COL_BG)
        
        # 1. Draw Map (Shifted by Camera)
        screen.blit(visual_map, (camera.camera.x, camera.camera.y))
        
        # 2. Draw Cars
        for car in cars:
            car.draw(screen, camera)

        # 3. HUD (Only draw if recording to save time)
        if writer:
            font = pygame.font.SysFont("Impact", 60)
            status = f"GEN {GENERATION} | ALIVE: {len(cars)}"
            text = font.render(status, True, (255, 255, 255))
            screen.blit(text, (50, 50))

        pygame.display.flip()

        # --- E. RECORD FRAME ---
        if writer:
            try:
                frame = pygame.surfarray.array3d(screen)
                frame = frame.swapaxes(0, 1)
                writer.append_data(frame)
            except Exception as e:
                print(f"Record Error: {e}")

    if writer:
        writer.close()
        print(f"✅ Gen {GENERATION} saved.")

def run_neat(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    p.run(run_simulation, MAX_GENERATIONS)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
