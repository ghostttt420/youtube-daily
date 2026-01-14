import pygame
import neat
import os
import sys
import pickle
import simulation  # Uses the new V2 simulation
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
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    # 1. Generate Massive Map
    track_seed = 42 + GENERATION # Change map slightly or keep consistent
    map_gen = simulation.TrackGenerator(seed=101) # Keep seed fixed so we see improvement on SAME track
    start_pos, collision_map, visual_map = map_gen.generate_track()
    
    # Collision Mask (Black = Wall)
    # We use the raw black/white surface for collision logic
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
        save_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
        writer = imageio.get_writer(save_path, fps=30)

    # 4. Race Loop
    running = True
    frame_count = 0
    
    while running and len(cars) > 0 and frame_count < 1000:
        frame_count += 1
        
        # --- A. FIND LEADER ---
        # Find the car that has traveled the furthest to focus camera on it
        leader = max(cars, key=lambda c: c.distance_traveled)
        for c in cars: c.is_leader = False
        leader.is_leader = True
        
        # Update Camera to follow Leader
        camera.update(leader)

        # --- B. AI LOGIC ---
        for i, car in enumerate(cars):
            ge[i].fitness += 0.1
            if not car.alive: continue

            # Check Radar (Pass the collision map)
            car.check_radar(map_mask)
            
            inputs = [d[1] / 300.0 for d in car.radars] # Normalize
            output = nets[i].activate(inputs)
            
            if output[0] > 0.5: car.rotate(right=True)
            if output[0] < -0.5: car.rotate(left=True)
            
            car.speed = 12 # Higher speed for excitement
            car.update(map_mask)

        # --- C. DEATH CHECK ---
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 1
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if len(cars) == 0: break

        # --- D. RENDER (Cinematic) ---
        screen.fill(simulation.COL_BG)
        
        # 1. Draw Map (Shifted by Camera)
        offset_pos = (camera.camera.x, camera.camera.y)
        screen.blit(visual_map, offset_pos)
        
        # 2. Draw Cars
        for car in cars:
            car.draw(screen, camera)

        # 3. HUD
        if writer:
            font = pygame.font.SysFont("Impact", 60)
            status = f"GEN {GENERATION} | ALIVE: {len(cars)}"
            text = font.render(status, True, (255, 255, 255))
            screen.blit(text, (50, 50))

        pygame.display.flip()

        # --- E. RECORD ---
        if writer:
            try:
                frame = pygame.surfarray.array3d(screen)
                frame = frame.swapaxes(0, 1)
                writer.append_data(frame)
            except: pass

    if writer: writer.close()

def run_neat(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    p = neat.Population(config)
    p.run(run_simulation, MAX_GENERATIONS)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
