import pygame
import neat
import os
import math
import sys
import pickle
import simulation  # Import your previous script
import imageio

# --- CONFIG ---
GENERATION = 0
MAX_GENERATIONS = 30  # Stop after 30 gens (Usually enough for mastery)
RECORD_GENS = [1, 5, 10, 20, 29] # Which generations to save as video clips
VIDEO_OUTPUT_DIR = "training_clips"

if not os.path.exists(VIDEO_OUTPUT_DIR):
    os.makedirs(VIDEO_OUTPUT_DIR)

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n ****** Running generation {GENERATION} ****** \n")

    # Collections for NEAT
    nets = []
    cars = []
    ge = []

    # Setup Pygame (Headless friendly)
    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    clock = pygame.time.Clock()

    # 1. Generate the Map (Same seed for consistency across a run, or random per day)
    track_seed = 101 # Change this number daily to generate a new map
    map_gen = simulation.TrackGenerator(seed=track_seed)
    start_pos, track_surface = map_gen.generate_track(screen)
    
    # Collision Mask
    map_mask = pygame.mask.from_surface(track_surface)
    map_mask.invert() # Invert so walls are the collision object

    # 2. Spawn Cars (One for each genome)
    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos))
        g.fitness = 0
        ge.append(g)

    # Recorder Setup
    writer = None
    recording = GENERATION in RECORD_GENS
    if recording:
        print(f"🎥 Recording Generation {GENERATION}...")
        save_path = os.path.join(VIDEO_OUTPUT_DIR, f"gen_{GENERATION}.mp4")
        # Record at 30 FPS to save space
        writer = imageio.get_writer(save_path, fps=30)

    # 3. Main Loop
    running = True
    frame_count = 0
    max_frames = 600 if GENERATION < 10 else 1200 # Give them more time as they get smarter

    while running and len(cars) > 0 and frame_count < max_frames:
        frame_count += 1
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        # A. INPUT & DECISION
        for i, car in enumerate(cars):
            # Give fitness for surviving
            ge[i].fitness += 0.1

            # --- THE FIX IS HERE ---
            # Force the car to look at the map BEFORE we ask for inputs
            car.check_radar(map_mask)
            
            # Get inputs (5 Radar Distances)
            inputs = [d[1] / 200.0 for d in car.radars] 
            
            # Brain Output
            output = nets[i].activate(inputs)
            
            # Output 0: Steering (-1 Left, +1 Right)
            if output[0] > 0.5:
                car.rotate(right=True)
            elif output[0] < -0.5:
                car.rotate(left=True)
                
            # Update Physics
            car.speed = 7 # Constant speed
            car.update(map_mask)

        # B. DEATH CHECK
        # We must iterate backwards to safely remove items from a list while looping
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 1 # Punishment
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        # C. DRAWING
        screen.fill(simulation.BG_COLOR)
        
        # Draw Track
        pygame.draw.rect(screen, simulation.TRACK_COLOR, (0,0,simulation.WIDTH,simulation.HEIGHT))
        screen.blit(track_surface, (0,0))
        
        # Draw Cars
        for car in cars:
            car.draw(screen)

        # HUD
        if recording: # Only draw text if we are recording (saves resources)
            font = pygame.font.SysFont("Impact", 50)
            text_gen = font.render(f"GEN: {GENERATION}", True, (255, 255, 255))
            text_alive = font.render(f"ALIVE: {len(cars)}", True, (0, 255, 65))
            screen.blit(text_gen, (50, 50))
            screen.blit(text_alive, (50, 120))

        pygame.display.flip()

        # D. CAPTURE FRAME
        if recording:
            try:
                # Convert Pygame surface to numpy array for video
                frame_data = pygame.surfarray.array3d(screen)
                # Rotate because Pygame uses (width, height) but images use (height, width)
                frame_data = frame_data.swapaxes(0, 1)
                writer.append_data(frame_data)
            except Exception as e:
                print(f"Frame capture error: {e}")
            
        clock.tick(0) # Max speed (training mode)

    if writer:
        writer.close()
        print(f"✅ Saved Gen {GENERATION} video.")

def run_neat(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)

    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    winner = p.run(run_simulation, MAX_GENERATIONS)
    
    print("\nTraining Complete.")
    with open("best.pickle", "wb") as f:
        pickle.dump(winner, f)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
