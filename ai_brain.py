import pygame
import neat
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
import pickle
import imageio
import numpy as np
import simulation  # Imports your physics engine
from moviepy.editor import VideoFileClip, AudioFileClip

# --- CONFIG ---
GENERATION = 0
MAX_GENERATIONS = 50
RECORD_GENS = [1, 5, 10, 20, 30, 49] # Gens to save
VIDEO_OUTPUT_DIR = "training_clips"
FINAL_OUTPUT_DIR = "ready_to_upload"

# STRICT SHORTS LIMITS
FPS = 30 
MAX_VIDEO_DURATION = 58 # Seconds (Keep under 60!)
MAX_FRAMES = FPS * MAX_VIDEO_DURATION

if not os.path.exists(VIDEO_OUTPUT_DIR): os.makedirs(VIDEO_OUTPUT_DIR)
if not os.path.exists(FINAL_OUTPUT_DIR): os.makedirs(FINAL_OUTPUT_DIR)

def add_sound_and_export(video_path, gen_num):
    """Post-production: Adds music to the silent game clip"""
    print(f"🎵 Processing Sound for Gen {gen_num}...")
    output_path = os.path.join(FINAL_OUTPUT_DIR, f"FactGhost_Gen_{gen_num}.mp4")
    
    try:
        # Load Video
        clip = VideoFileClip(video_path)
        
        # Load Music
        if os.path.exists("music.mp3"):
            audio = AudioFileClip("music.mp3")
            
            # Loop audio if video is longer, or subclip if shorter
            if audio.duration < clip.duration:
                audio = audio.loop(duration=clip.duration)
            else:
                audio = audio.subclip(0, clip.duration)
                
            # Composite
            clip = clip.set_audio(audio)
        else:
            print("⚠️ Warning: 'music.mp3' not found. Video will be silent.")

        # Write
        clip.write_videofile(output_path, codec='libx264', audio_codec='aac', logger=None)
        print(f"🚀 SUCCESS: {output_path} is ready for upload!")
        
    except Exception as e:
        print(f"❌ Video Processing Error: {e}")

def run_simulation(genomes, config):
    global GENERATION
    GENERATION += 1
    print(f"\n--- 🏁 Gen {GENERATION} Start ---")

    nets = []
    cars = []
    ge = []

    # Setup Environment
    pygame.init()
    screen = pygame.display.set_mode((simulation.WIDTH, simulation.HEIGHT))
    
    # Generate Map (Fixed Seed = Fair Comparison)
    map_gen = simulation.TrackGenerator(seed=42)
    start_pos, track_surface, visual_map = map_gen.generate_track()
    map_mask = pygame.mask.from_surface(track_surface)

    camera = simulation.Camera(simulation.WORLD_SIZE, simulation.WORLD_SIZE)

    # Spawn AI
    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(simulation.Car(start_pos)) # New Physics Car
        g.fitness = 0
        ge.append(g)

    # Video Recording Setup
    writer = None
    temp_video_path = os.path.join(VIDEO_OUTPUT_DIR, f"temp_gen_{GENERATION}.mp4")
    recording = (GENERATION in RECORD_GENS)
    
    if recording:
        print("🎥 Recording started...")
        writer = imageio.get_writer(temp_video_path, fps=FPS)

    # Race Loop
    running = True
    frame_count = 0
    
    # Pre-calc radars (Prevent index error on frame 0)
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
            
            # Inputs (Normalized)
            if len(car.radars) < 5: inputs = [0] * 5
            else: inputs = [d[1] / simulation.SENSOR_LENGTH for d in car.radars]

            # Neural Net Decision
            output = nets[i].activate(inputs)
            
            # Output 0: Steering (-1=Left, 1=Right)
            steering_out = output[0]
            if steering_out > 0.5: car.input_steer(right=True)
            elif steering_out < -0.5: car.input_steer(left=True)
            
            # Auto-Gas
            car.input_gas()

            # Physics Update
            car.update(map_mask)
            car.check_radar(map_mask)
            
            # Fitness Rules
            # Reward Distance & Speed
            ge[i].fitness += car.velocity.length()
            
            # Penalize stopping/spinning
            if car.velocity.length() < 1: ge[i].fitness -= 2

        # 5. Cleanup Dead
        for i in range(len(cars) - 1, -1, -1):
            if not cars[i].alive:
                ge[i].fitness -= 10 # Crash Penalty
                cars.pop(i)
                nets.pop(i)
                ge.pop(i)

        # 6. Render
        # Only draw every frame if recording, otherwise skip frames for speed
        if recording or frame_count % 5 == 0:
            screen.fill(simulation.COL_BG)
            screen.blit(visual_map, (camera.camera.x, camera.camera.y))
            
            for car in cars:
                car.draw(screen, camera)
            
            # HUD
            font = pygame.font.SysFont("consolas", 40, bold=True)
            # Timer
            seconds = int(frame_count / FPS)
            time_lbl = font.render(f"{seconds}s / 58s", True, (255, 255, 255))
            gen_lbl = font.render(f"GEN {GENERATION}", True, simulation.COL_WALL)
            
            screen.blit(gen_lbl, (20, 20))
            screen.blit(time_lbl, (20, 60))
            
            pygame.display.flip()

            # Capture Frame
            if recording:
                try:
                    pixels = pygame.surfarray.array3d(screen)
                    pixels = np.transpose(pixels, (1, 0, 2))
                    writer.append_data(pixels)
                except: pass

    # End Generation
    if writer:
        writer.close()
        # Trigger Post-Production
        add_sound_and_export(temp_video_path, GENERATION)
        # Delete temp file to save space
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)

def run_neat(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_path)
    
    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)
    
    winner = p.run(run_simulation, MAX_GENERATIONS)
    with open("best.pickle", "wb") as f:
        pickle.dump(winner, f)

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config.txt")
    run_neat(config_path)
