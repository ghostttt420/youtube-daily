import pygame
import neat
import os
import sys
import pickle
import imageio
import numpy as np
import simulation  # Imports your physics/camera classes

# --- CONFIG ---
GENERATION = 0
MAX_GENERATIONS = 50
RECORD_GENS = [1, 5, 10, 20, 30, 49] # Gens to save video for
VIDEO_OUTPUT_DIR = "training_clips"

# Ensure output folder exists
if not os.path.exists(VIDEO_OUTPUT_DIR):
    os.makedirs(VIDEO_OUTPUT_DIR)

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n--- 🏁 Starting Generation {GENERATION} ---")

    nets = []
    cars = []
    ge = []

    # 1. Setup Pygame & Map
    pygame.init()
    # Note: We use the constants from simulation.py to ensure they match
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    clock = pygame.time.Clock()

    # Generate the Map (Seed fixed so AI learns the same track)
    map_gen = simulation.TrackGenerator(seed=42)
    start_pos, track_surface, visual_map = map_gen.generate_track()
    
    # Create Collision Mask (White pixels = Road)
    map_mask = pygame.mask.from_surface(track_surface)

    # Setup Camera
    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    # 2. Spawn Cars & Networks
    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        
        # Create Car
        car = simulation.Car(start_pos)
        cars.append(car)
        
        # Init Fitness
        g.fitness = 0
        ge.append(g)

    # 3. Setup Video Recorder
    writer = None
    if GENERATION in RECORD_GENS:
        print(f"🎥 RECORDING ENABLED for Gen {GENERATION}")
        save_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
        writer = imageio.get_writer(save_path, fps=30) # 30 FPS for smooth Shorts

    # --- THE RACE LOOP ---
    running = True
    frame_count = 0
    # Allow longer races as they get smarter
    max_frames = 1000 + (GENERATION * 50) 
    
    # Pre-calculate sensors once so Frame 0 doesn't crash
    for car in cars:
        car.check_radar(map_mask)

    while running and len(cars) > 0 and frame_count < max_frames:
        frame_count += 1
        
        # A. Handle Pygame Events (Quit)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # B. Camera Tracking (Follow the Leader)
        leader = max(cars, key=lambda c: c.distance_traveled)
        camera.update(leader)
        
        # Visual flair: Only the leader gets the "Hero" color
        for c in cars: c.is_leader = (c == leader)

        # C. AI Logic & Physics
        for i, car in enumerate(cars):
            if not car.alive: continue

            # 1. Get Inputs
            # Safety: If radar somehow failed, fill with 0s
            if len(car.radars) < 5:
                inputs = [0] * 5
            else:
                # Normalize input (0 to 1) for the Neural Net
                inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]

            # 2. Activate Brain
            output = nets[i].activate(inputs)
            
            # 3. Apply Controls
            # Output 0: Steering (Left/Right)
            if output[0] > 0.5: car.rotate(right=True)
            elif output[0] < -0.5: car.rotate(left=True)
            
            # Output 1: Speed (Optional - currently constant)
            # if output[1] > 0.5: car.speed = 15 
            
            # 4. Update Physics (Moves car AND updates Radar for next frame)
            car.update(map_mask)
            
            # 5. Fitness Rewards
            # Reward for distance
            ge[i].fitness += (car.speed / 10) 
            # Tiny reward for existing (encourages not crashing immediately)
            ge[i].fitness += 0.1

        # D. Cleanup Dead Cars
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 5 # Penalty for dying
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        if len(cars) == 0:
            break

        # E. Render (Only if recording or watching)
        # If we are NOT recording and just training, we could skip drawing to speed up
        # But for now, we draw everything to see it.
        
        screen.fill(simulation.COL_BG)
        
        # Draw World (Camera Adjusted)
        screen.blit(visual_map, (camera.camera.x, camera.camera.y))
        
        # Draw Cars
        for car in cars:
            car.draw(screen, camera)
            
        # Draw HUD
        font = pygame.font.SysFont("consolas", 30, bold=True)
        text = font.render(f"GEN: {GENERATION} | ALIVE: {len(cars)}", True, (255, 255, 255))
        screen.blit(text, (20, 20))

        pygame.display.flip()

        # F. Capture Frame for Video
        if writer:
            try:
                # Capture the screen surface
                pixels = pygame.surfarray.array3d(screen)
                # Rotate because surfarray is (width, height, color) but video wants (height, width, color)
                pixels = np.transpose(pixels, (1, 0, 2))
                writer.append_data(pixels)
            except Exception as e:
                print(f"Frame capture failed: {e}")

    # End of Gen Cleanup
    if writer:
        writer.close()
        print(f"✅ Video saved: gen_{GENERATION}.mp4")

def run_neat(config_path):
    # Setup NEAT
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    
    # Create Population
    p = neat.Population(config)
    
    # Add Reporters
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)
    
    # Run!
    winner = p.run(run_simulation, MAX_GENERATIONS)
    
    # Save best AI
    with open("best.pickle", "wb") as f:
        pickle.dump(winner, f)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
