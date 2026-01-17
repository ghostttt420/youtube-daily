import pygame
import math
import numpy as np
from scipy.interpolate import splprep, splev

# --- CONSTANTS ---
WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 5000  # Massive world for high speed
CAR_SIZE = 50      # Large, visible cars
SENSOR_LENGTH = 300
FPS = 60

# --- COLOR PALETTE (Cyberpunk) ---
COL_BG = (10, 10, 15)
COL_GRID = (25, 25, 40)
COL_ROAD = (20, 20, 25)
COL_NEON_BLUE = (0, 255, 255)
COL_NEON_PINK = (255, 0, 110)
COL_SENSOR = (0, 255, 65)

class Camera:
    def __init__(self):
        self.x = 0
        self.y = 0

    def update(self, target_car):
        # Smoothly follow the leader
        self.x = -target_car.x + WIDTH // 2
        self.y = -target_car.y + HEIGHT // 2

class Car:
    def __init__(self, start_pos):
        self.x, self.y = start_pos
        self.angle = 0
        self.speed = 0
        self.alive = True
        self.distance = 0
        self.is_leader = False
        self.trail = [] # For the 'rolling' fix: shows direction

    def update(self, mask):
        if not self.alive: return
        
        # Physics
        self.x += math.cos(math.radians(360 - self.angle)) * self.speed
        self.y += math.sin(math.radians(360 - self.angle)) * self.speed
        self.distance += self.speed
        
        # Trail (updates every 3rd frame for performance)
        if len(self.trail) > 20: self.trail.pop(0)
        self.trail.append((self.x, self.y))

        # Collision (Black = Death)
        try:
            if mask.get_at((int(self.x), int(self.y))) == 0:
                self.alive = False
        except: self.alive = False

    def draw(self, screen, cam):
        color = COL_NEON_PINK if self.is_leader else (100, 100, 150)
        
        # Draw Trail (Shows path)
        if len(self.trail) > 1:
            points = [(p[0] + cam.x, p[1] + cam.y) for p in self.trail]
            pygame.draw.lines(screen, color, False, points, 3)

        # Draw Glow Car
        surf = pygame.Surface((CAR_SIZE, CAR_SIZE), pygame.SRCALPHA)
        pygame.draw.polygon(surf, color, [(CAR_SIZE, CAR_SIZE//2), (0, 0), (0, CAR_SIZE)])
        rotated = pygame.transform.rotate(surf, self.angle)
        rect = rotated.get_rect(center=(self.x + cam.x, self.y + cam.y))
        screen.blit(rotated, rect)

class TrackGenerator:
    def generate(self, seed):
        np.random.seed(seed)
        n = 12
        angles = np.linspace(0, 2*np.pi, n, endpoint=False)
        radii = np.random.randint(1200, 2000, n)
        pts = np.column_stack([WORLD_SIZE//2 + radii*np.cos(angles), WORLD_SIZE//2 + radii*np.sin(angles)])
        pts = np.vstack([pts, pts[0]])
        
        tck, u = splprep(pts.T, s=0, per=True)
        new_pts = np.column_stack(splev(np.linspace(0, 1, 1000), tck))
        
        # Collision Mask
        mask_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        mask_surf.fill(0)
        pygame.draw.lines(mask_surf, 255, True, new_pts, 400)
        mask = pygame.mask.from_surface(mask_surf)
        
        # Visual Map
        vis = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis.fill(COL_BG)
        # Grid
        for i in range(0, WORLD_SIZE, 250):
            pygame.draw.line(vis, COL_GRID, (i,0), (i,WORLD_SIZE))
            pygame.draw.line(vis, COL_GRID, (0,i), (WORLD_SIZE,i))
        # Road
        pygame.draw.lines(vis, COL_NEON_BLUE, True, new_pts, 410)
        pygame.draw.lines(vis, COL_ROAD, True, new_pts, 395)
        
        return (int(new_pts[0][0]), int(new_pts[0][1])), mask, vis
