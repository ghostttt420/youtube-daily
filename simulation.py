import pygame
import math
import numpy as np
import sys
import os
import neat
from scipy.interpolate import splprep, splev

# --- CONFIGURATION & CYBERPUNK PALETTE ---
WIDTH, HEIGHT = 1080, 1920  # Vertical Video (Shorts)
WORLD_SIZE = 4000           # Massive Map
CAR_SIZE = 45               
SENSOR_LENGTH = 250
FPS = 60

# Cyberpunk Palette
COL_BG = (10, 10, 18)        # Deep Void Blue
COL_GRID = (30, 30, 50)      # Faint Grid
COL_TRACK = (20, 20, 30)     # Dark Asphalt
COL_WALL = (0, 255, 255)     # Cyan Neon Borders
COL_CAR_LEADER = (255, 0, 110) # Hot Pink (Leader)
COL_CAR_NORM = (50, 100, 255)  # Blue (Normal)
COL_SENSOR = (0, 255, 65)    # Matrix Green

class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height

    def apply(self, entity_rect):
        """Returns a rect shifted by camera coordinates"""
        return entity_rect.move(self.camera.topleft)

    def apply_point(self, pos):
        """Returns a point (x,y) shifted by camera coordinates"""
        return (pos[0] + self.camera.x, pos[1] + self.camera.y)

    def update(self, target):
        """Follow the target (Lead Car)"""
        # Center the target
        x = -target.rect.centerx + int(WIDTH / 2)
        y = -target.rect.centery + int(HEIGHT / 2)

        # Clamp to world bounds
        x = min(0, max(-(self.width - WIDTH), x))
        y = min(0, max(-(self.height - HEIGHT), y))
        
        self.camera = pygame.Rect(x, y, self.width, self.height)

class Car:
    def __init__(self, start_pos):
        self.x, self.y = start_pos
        self.angle = 0
        self.speed = 12 # Constant forward speed
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        self.is_leader = False
        
        # Visuals: Trail Buffer
        self.trail = [] 

        # --- OPTIMIZATION: Pre-render Sprites ---
        # We generate the car graphics ONCE, not every frame.
        self.img_normal = self._create_sprite(COL_CAR_NORM)
        self.img_leader = self._create_sprite(COL_CAR_LEADER)
        
        self.image = self.img_normal
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def _create_sprite(self, color):
        surf = pygame.Surface((CAR_SIZE, CAR_SIZE), pygame.SRCALPHA)
        # Glow (faint outer circle)
        pygame.draw.circle(surf, (*color, 50), (CAR_SIZE//2, CAR_SIZE//2), CAR_SIZE//2)
        # Body (Solid Triangle)
        pts = [(CAR_SIZE, CAR_SIZE//2), (0, 0), (0, CAR_SIZE)]
        pygame.draw.polygon(surf, color, pts)
        return surf

    def update(self, map_mask):
        if not self.alive: return

        # Physics Movement
        self.x += math.cos(math.radians(360 - self.angle)) * self.speed
        self.y += math.sin(math.radians(360 - self.angle)) * self.speed
        
        self.distance_traveled += self.speed
        self.rect.center = (int(self.x), int(self.y))
        
        # Trail Logic
        if self.distance_traveled % 10 == 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 20: self.trail.pop(0)

        # Update Image State if status changed
        if self.is_leader and self.image != self.img_leader:
            self.image = self.img_leader
        elif not self.is_leader and self.image != self.img_normal:
            self.image = self.img_normal

        # Collision & Radar
        self.check_collision(map_mask)
        self.check_radar(map_mask)

    def check_collision(self, map_mask):
        try:
            # Check center point. 0 = Wall (Black/Transparent on mask)
            if map_mask.get_at((int(self.x), int(self.y))) == 0:
                self.alive = False
        except IndexError:
            self.alive = False

    def check_radar(self, map_mask):
        self.radars.clear()
        for degree in [-90, -45, 0, 45, 90]:
            self.cast_ray(degree, map_mask)

    def cast_ray(self, degree, map_mask):
        length = 0
        x, y = int(self.x), int(self.y)
        
        while length < SENSOR_LENGTH:
            length += 15 # Optimization: larger step size
            x = int(self.rect.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.rect.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)
            
            try:
                if map_mask.get_at((x, y)) == 0:
                    break
            except IndexError:
                break
        
        dist = int(math.sqrt(math.pow(x - self.rect.center[0], 2) + math.pow(y - self.rect.center[1], 2)))
        self.radars.append([(x, y), dist])

    def rotate(self, left=False, right=False):
        if left: self.angle += 7 # Snappier turning
        if right: self.angle -= 7

    def draw(self, screen, camera):
        # 1. Draw Trail (World Space -> Camera Space)
        if len(self.trail) > 1 and self.alive:
            # Convert all trail points to camera coordinates
            adjusted_trail = [camera.apply_point(p) for p in self.trail]
            color = COL_CAR_LEADER if self.is_leader else COL_CAR_NORM
            pygame.draw.lines(screen, color, False, adjusted_trail, 2)

        # 2. Draw Car (Rotated & Offset)
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        new_rect = rotated_image.get_rect(center=self.image.get_rect(center=(self.x, self.y)).center)
        screen.blit(rotated_image, camera.apply(new_rect).topleft)
        
        # 3. Draw Sensors (Only for Leader)
        if self.is_leader and self.alive:
            for radar in self.radars:
                pos, dist = radar
                pygame.draw.line(screen, (0, 255, 65, 80), camera.apply_point(self.rect.center), camera.apply_point(pos), 1)
                pygame.draw.circle(screen, COL_SENSOR, camera.apply_point(pos), 3)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self):
        # Create surfaces
        track_surface = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        visual_surface = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        track_surface.fill((0, 0, 0)) # Physics: Black = Wall
        visual_surface.fill(COL_BG)   # Visual: Background
        
        # 1. Generate Random Points
        n_points = 16
        points = []
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
            radius = np.random.randint(900, 1800)
            x = WORLD_SIZE // 2 + radius * math.cos(angle)
            y = WORLD_SIZE // 2 + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0]) 
        
        # 2. Spline Smoothing
        pts = np.array(points)
        try:
            tck, u = splprep(pts.T, u=None, s=0.0, per=1)
            u_new = np.linspace(u.min(), u.max(), 2000)
            x_new, y_new = splev(u_new, tck, der=0)
            smooth_points = list(zip(x_new, y_new))
        except:
            # Fallback if spline fails
            smooth_points = points

        # 3. Draw Physics Mask (White = Safe Road)
        pygame.draw.lines(track_surface, (255, 255, 255), True, smooth_points, 350) 
        
        # 4. Draw Visual Map
        # Grid
        for x in range(0, WORLD_SIZE, 300):
            pygame.draw.line(visual_surface, COL_GRID, (x, 0), (x, WORLD_SIZE))
        for y in range(0, WORLD_SIZE, 300):
            pygame.draw.line(visual_surface, COL_GRID, (0, y), (WORLD_SIZE, y))

        # Road layers
        pygame.draw.lines(visual_surface, COL_WALL, True, smooth_points, 360)  # Cyan Edge
        pygame.draw.lines(visual_surface, COL_TRACK, True, smooth_points, 340) # Tarmac
        
        return (int(x_new[0]), int(y_new[0])), track_surface, visual_surface

def draw_hud(surface, living, distance, gen):
    font = pygame.font.SysFont("consolas", 40, bold=True)
    
    def render_stat(txt, y, color):
        s_surf = font.render(txt, True, (0,0,0)) # Shadow
        t_surf = font.render(txt, True, color)
        surface.blit(s_surf, (32, y+2))
        surface.blit(t_surf, (30, y))

    render_stat(f"GEN: {gen}", 50, COL_WALL)
    render_stat(f"ALIVE: {living}", 100, (255, 255, 255))
    render_stat(f"DIST: {int(distance)}", 150, COL_CAR_LEADER)

# --- MAIN SIMULATION LOOP ---
def run_simulation(genomes, config):
    # Setup
    nets = []
    cars = []
    
    # Generate Map
    map_gen = TrackGenerator(seed=np.random.randint(0, 10000))
    start_pos, track_mask, visual_map = map_gen.generate_track()
    
    # Init Camera
    camera = Camera(WORLD_SIZE, WORLD_SIZE)
    
    # Init Genomes
    for id, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        g.fitness = 0
        cars.append(Car(start_pos))

    # Pygame Init
    pygame.init()
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    
    # Tracking variables
    current_gen = 0 # You can pass this in if needed
    
    run = True
    while run:
        clock.tick(FPS)
        
        # Event Loop
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        # Check Population Status
        alive_cars = [c for c in cars if c.alive]
        if len(alive_cars) == 0:
            break # End generation
            
        # --- CAMERA TRACKING ---
        # Find the best car (furthest distance)
        best_car = max(alive_cars, key=lambda c: c.distance_traveled)
        
        # Mark visual leader
        for car in cars:
            car.is_leader = (car == best_car)
            
        camera.update(best_car)

        # --- AI & LOGIC ---
        for i, car in enumerate(cars):
            if car.alive:
                # 1. Get Inputs (Radar distances)
                input_data = [r[1] for r in car.radars]
                # Pad inputs if sensors hit nothing (rare case but safe)
                while len(input_data) < 5: input_data.append(0)
                
                # 2. Get Output from NEAT
                output = nets[i].activate(input_data)
                
                # 3. Control Car
                # Assuming Output [0] > 0.5 is Left, Output [1] > 0.5 is Right
                if output[0] > 0.5: car.rotate(right=True)
                if output[1] > 0.5: car.rotate(left=True)
                
                # 4. Update Physics
                car.update(track_mask)
                
                # 5. Reward/Penalty
                if car.alive:
                    genomes[i][1].fitness += 1 # Reward for staying alive
                    genomes[i][1].fitness += car.speed / 10 # Reward for speed

        # --- RENDER FRAME ---
        win.fill(COL_BG) # Clear
        
        # 1. Draw World (Camera Offset)
        win.blit(visual_map, (camera.camera.x, camera.camera.y))
        
        # 2. Draw Cars
        for car in cars:
            if car.alive:
                car.draw(win, camera)
                
        # 3. Draw HUD (Static)
        draw_hud(win, len(alive_cars), best_car.distance_traveled, current_gen)
        
        pygame.display.flip()
        
    pygame.quit()

# --- FOR TESTING WITHOUT NEAT (DEBUG MODE) ---
if __name__ == "__main__":
    print("Running in Debug Mode (No AI)...")
    pygame.init()
    
    # Mock config for testing map generation
    map_gen = TrackGenerator(seed=42)
    start_pos, track_mask, visual_map = map_gen.generate_track()
    
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    camera = Camera(WORLD_SIZE, WORLD_SIZE)
    car = Car(start_pos)
    car.is_leader = True
    
    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()
            
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: car.rotate(left=True)
        if keys[pygame.K_RIGHT]: car.rotate(right=True)
        
        car.update(track_mask)
        camera.update(car)
        
        win.fill(COL_BG)
        win.blit(visual_map, (camera.camera.x, camera.camera.y))
        car.draw(win, camera)
        pygame.display.flip()
